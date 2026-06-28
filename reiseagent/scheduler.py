import time
from datetime import date

import profile_store
import store
from agents.free_time_detector import detect_and_save_free_days
from agents.suggestion_agent import create_suggestions_for_upcoming_free_days
from providers.telegram import send_suggestion_proposal

_last_run_date = None


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


def scheduler_loop():
    """Hintergrundthread: prüft täglich ob es Samstag ist."""
    while True:
        if _should_run_today():
            try:
                run_weekly_suggestions()
            except Exception as exc:
                print(f"[scheduler] Fehler: {exc}")
        time.sleep(3600)  # Jede Stunde prüfen
