import time
from datetime import date, timedelta

import profile_store
import store
from agents.free_time_detector import detect_and_save_free_days
from agents.suggestion_agent import create_suggestions_for_upcoming_free_days
from providers.telegram import send_suggestion_proposal, send_message

_last_run_date = None

BANK_CHECKIN_MESSAGE = (
    "Monats-Check-in: Wie hoch sind deine Einnahmen und Fixkosten diesen Monat? "
    "Beispiel: Einnahmen 3000 €, Fixkosten 2000 €."
)


def _should_run_today():
    today = date.today()
    return today.weekday() == 5  # Samstag


def run_weekly_suggestions():
    """
    Hauptfunktion: freie Tage erkennen → Vorschläge erstellen → per Telegram senden.
    Wird vom Scheduler-Thread aufgerufen.
    """
    global _last_run_date
    today = date.today()

    if _last_run_date == today:
        return  # Heute schon gelaufen

    _last_run_date = today
    print(f"[scheduler] Wöchentlicher Durchlauf gestartet ({today})")

    profile_store.init_db()

    # Freie Tage erkennen und speichern
    detect_result = detect_and_save_free_days(days_ahead=14)
    free_days = detect_result.get("free_days", [])
    print(f"[scheduler] {len(free_days)} freie Tage erkannt")

    if not free_days:
        print("[scheduler] Keine freien Tage — kein Vorschlag.")
        return

    # Vorschläge erstellen (max. 3)
    home_city = "Berlin"
    suggestion_result = create_suggestions_for_upcoming_free_days(
        home_city=home_city,
        max_suggestions=3,
    )
    suggestions = suggestion_result.get("suggestions", [])
    print(f"[scheduler] {len(suggestions)} Vorschläge erstellt")

    if not suggestions:
        return

    # Vorschläge per Telegram senden
    # Wir brauchen einen Trip-Kontext für die Callback-Tokens.
    # Wir nutzen den neuesten gespeicherten Trip — oder erstellen einen leeren Platzhalter.
    trips = store.list_trips()
    if trips:
        trip = trips[-1]
    else:
        trip = store.create_trip({"destination": home_city, "auto": True})

    for suggestion in suggestions:
        sent = send_suggestion_proposal(trip, suggestion, home_city=home_city)
        if sent:
            print(f"[scheduler] Vorschlag für {suggestion.get('date')} gesendet")
        else:
            print(f"[scheduler] Telegram nicht konfiguriert — Vorschlag nur in DB gespeichert")


def run_monthly_bank_checkin(today=None):
    """
    Monatlicher Bankkonto-Check-in (Modul D Teil 1).

    Sendet nur dann eine Telegram-Frage + legt einen pending_prompt an, wenn:
      - heute der 1. Tag eines Monats ist,
      - fuer diesen Monat noch kein Bankkonto-Eintrag existiert,
      - und aktuell keine andere offene pending_prompt-Frage laeuft.
    `today` ist optional (fuer Tests), sonst wird date.today() verwendet.
    Kein Crash, wenn Telegram nicht konfiguriert ist (send_message ist fail-safe).
    """
    if today is None:
        today = date.today()

    if today.day != 1:
        return {"sent": False, "reason": "not_first_of_month"}

    profile_store.init_db()
    month_str = today.strftime("%Y-%m")

    if profile_store.get_bank_account_for_month(month_str):
        return {"sent": False, "reason": "already_checked_in_this_month"}

    if profile_store.get_open_pending_prompt():
        return {"sent": False, "reason": "pending_prompt_already_open"}

    send_message(BANK_CHECKIN_MESSAGE)
    prompt_id = profile_store.create_pending_prompt("bank_checkin", metadata={"month": month_str})

    return {"sent": True, "month": month_str, "pending_prompt_id": prompt_id}


def _determine_trip_end_date(trip):
    """
    Ermittelt robust das Enddatum einer Reise, oder None wenn nicht sicher
    bestimmbar (dann wird der Trip in run_trip_feedback_check uebersprungen).

    Reihenfolge (erstes gueltiges Feld gewinnt):
      1. request["end_date"] / request["return_date"] (falls im Projekt gesetzt)
      2. letzter Tag des aktiven Plans (active_plan["days"][-1]["date"]) -
         das ist bereits korrekt aus start_date + duration_days berechnet
      3. request["start_date"] + duration_days - 1 (bzw. departure_date als Ersatz)
    """
    request = trip.get("request") or {}

    for field in ("end_date", "return_date"):
        raw = request.get(field)
        if raw:
            try:
                return date.fromisoformat(raw)
            except ValueError:
                pass

    active_plan = trip.get("active_plan") or {}
    days = active_plan.get("days") or []
    if days:
        last_date = days[-1].get("date")
        if last_date:
            try:
                return date.fromisoformat(last_date)
            except ValueError:
                pass

    start_str = request.get("start_date") or request.get("departure_date")
    duration_days = request.get("duration_days")
    if start_str and duration_days:
        try:
            start = date.fromisoformat(start_str)
            return start + timedelta(days=int(duration_days) - 1)
        except (ValueError, TypeError):
            pass

    return None


def run_trip_feedback_check(today=None):
    """
    Taeglicher Trip-Ende-Check (Modul D Teil 2): fragt nach dem Ende einer
    Reise per Telegram nach Feedback - aber nur einmal pro Reise und nie
    parallel zu einer anderen offenen pending_prompt-Frage (z.B. Bankkonto).

    `today` ist optional (fuer Tests), sonst wird date.today() verwendet.
    Kein Crash, wenn Telegram nicht konfiguriert ist oder ein Trip kein
    sicher bestimmbares Enddatum hat (dieser Trip wird dann uebersprungen).
    """
    if today is None:
        today = date.today()

    profile_store.init_db()
    store.init_db()

    asked_trip_id = None
    skipped_no_open_slot = []

    for trip in store.list_trips():
        if trip.get("feedback_requested"):
            continue

        end_date = _determine_trip_end_date(trip)
        if end_date is None or end_date != today:
            continue

        # Keine zweite offene Frage parallel stellen (z.B. laeuft noch der
        # Bankkonto-Check-in) - spaeter (naechster Lauf) erneut versuchen.
        if profile_store.get_open_pending_prompt():
            skipped_no_open_slot.append(trip["id"])
            continue

        destination = (trip.get("request") or {}).get("destination", "deinem Ziel")
        message = (
            f"Deine Reise nach {destination} ist beendet. Wie zufrieden warst du mit "
            "Kultur, Essen, Natur, Sehenswürdigkeiten oder Shopping? "
            "Du kannst z. B. antworten: Museen 5/5, Essen 3/5."
        )
        send_message(message)
        profile_store.create_pending_prompt("feedback", trip_id=trip["id"])
        store.mark_feedback_requested(trip["id"])

        asked_trip_id = trip["id"]
        break  # MVP: pro Lauf nur eine Feedback-Frage stellen (Regel "nur eine offene Frage")

    return {
        "asked_trip_id": asked_trip_id,
        "skipped_no_open_slot": skipped_no_open_slot,
    }


def scheduler_loop():
    """Hintergrundthread: prüft täglich ob es Samstag ist."""
    while True:
        if _should_run_today():
            try:
                run_weekly_suggestions()
            except Exception as exc:
                print(f"[scheduler] Fehler: {exc}")
        try:
            run_monthly_bank_checkin()
        except Exception as exc:
            print(f"[scheduler] Fehler beim Bankkonto-Check-in: {exc}")
        try:
            run_trip_feedback_check()
        except Exception as exc:
            print(f"[scheduler] Fehler beim Trip-Feedback-Check: {exc}")
        time.sleep(3600)  # Jede Stunde prüfen
