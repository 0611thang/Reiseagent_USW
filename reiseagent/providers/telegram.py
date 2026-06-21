import os
import httpx
from datetime import datetime, timedelta

CHAT_ID = -1003734288144  # Reiseplaner Gruppe


def send_message(text):
    """Schickt eine Nachricht an die Telegram-Gruppe."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        response = httpx.post(url, json={"chat_id": CHAT_ID, "text": text}, timeout=5.0)
        return response.json().get("ok", False)
    except Exception:
        return False


def send_navigation_reminder(activity_name, start_time, routes):
    """Schickt eine Abfahrts-Erinnerung mit Fuß- und Autoroute."""
    foot = routes.get("foot")
    car = routes.get("car")

    lines = [
        f"🗺️ Reiseplaner Erinnerung",
        f"",
        f"Nächste Aktivität: {activity_name} um {start_time} Uhr",
    ]

    if foot:
        lines.append(f"👟 Zu Fuß: {foot['duration_minutes']} Min ({foot['distance_km']} km)")
    if car:
        lines.append(f"🚗 Auto: {car['duration_minutes']} Min ({car['distance_km']} km)")

    if foot:
        aufbruch = foot["duration_minutes"] + 15
        lines.append(f"⏰ Bitte in {aufbruch} Minuten aufbrechen!")
    else:
        lines.append(f"⏰ Bitte rechtzeitig aufbrechen!")

    return send_message("\n".join(lines))


def send_plan_update(plan, calendar_synced=False, warning_text=""):
    """Schickt eine kurze Plan-Zusammenfassung, wenn Telegram eingerichtet ist."""
    request = plan.get("request", {})
    destination = request.get("destination", "deiner Reise")
    days = plan.get("days", [])

    lines = [f"Dein Reiseplan fuer {destination} wurde aktualisiert."]
    for day in days[:3]:
        names = []
        for slot in day.get("time_slots", [])[:3]:
            activity = slot.get("activity", {})
            if activity.get("name"):
                names.append(activity["name"])
        if names:
            lines.append(f"Tag {day.get('day_number')}: {', '.join(names)}")

    if calendar_synced:
        lines.append("Kalender wurde synchronisiert.")
    if warning_text:
        lines.append(warning_text)

    return send_message("\n".join(lines[:6]))


def get_recent_messages(hours=24):
    """Holt Nachrichten der letzten X Stunden via Telegram Bot API."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return []

    try:
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        response = httpx.get(url, params={"limit": 100}, timeout=5.0)
        updates = response.json().get("result", [])

        cutoff = datetime.now() - timedelta(hours=hours)
        messages = []
        for update in updates:
            msg = update.get("message", {})
            text = msg.get("text", "")
            date = datetime.fromtimestamp(msg.get("date", 0))
            if date > cutoff and text:
                messages.append({"text": text, "date": date.strftime("%H:%M")})
        return messages
    except Exception:
        return []


def find_trip_relevant_messages(messages, destination):
    """Filtert Nachrichten nach reisebezogenen Keywords."""
    keywords = [
        destination.lower(),
        "hotel", "flug", "bahn", "bus", "zug",
        "reservierung", "buchung", "absage", "abgesagt",
        "restaurant", "museum", "ticket", "treffen", "uhrzeit",
    ]
    return [m for m in messages if any(kw in m["text"].lower() for kw in keywords)]

def send_flight_delay_proposal(trip: dict, proposal: dict, flight_updates: dict) -> bool:
    """
    Sendet eine Telegram-Nachricht mit Inline-Buttons:
    - neuen Plan annehmen
    - neuen Plan ablehnen
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return False

    trip_id = trip["id"]
    proposal_id = proposal["id"]

    request = trip.get("request", {})
    destination = request.get("destination", "deiner Reise")
    flight_number = request.get("flight_number") or flight_updates.get("flight_number") or "unbekannter Flug"

    delay = proposal.get("delay_minutes", 0)

    budget_before = proposal.get("budget_before", {})
    budget_after = proposal.get("budget_after", {})

    before_total = budget_before.get("planned_total", 0)
    after_total = budget_after.get("planned_total", 0)
    delta = after_total - before_total

    text = (
        f"✈️ Flugverspätung erkannt\n\n"
        f"Flug: {flight_number}\n"
        f"Reiseziel: {destination}\n"
        f"Verspätung: {delay} Minuten\n\n"
        f"Ich habe einen neuen Reiseplan vorgeschlagen.\n"
        f"Alter Plan: {before_total:.0f} €\n"
        f"Neuer Plan: {after_total:.0f} €\n"
        f"Preisdifferenz: {delta:+.0f} €\n\n"
        f"Möchtest du den neuen Plan übernehmen?"
    )

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "✅ Neuen Plan annehmen",
                    "callback_data": f"proposal:accept:{trip_id}:{proposal_id}",
                },
                {
                    "text": "❌ Ablehnen",
                    "callback_data": f"proposal:reject:{trip_id}:{proposal_id}",
                },
            ]
        ]
    }

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        response = httpx.post(
            url,
            json={
                "chat_id": CHAT_ID,
                "text": text,
                "reply_markup": keyboard,
            },
            timeout=5.0,
        )
        return response.json().get("ok", False)
    except Exception:
        return False


def get_callback_updates(offset: int = None) -> dict:
    """
    Holt Telegram-Button-Klicks.
    Wird später in main.py im Hintergrund gepollt.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return {
            "ok": False,
            "result": [],
        }

    params = {
        "timeout": 5,
        "allowed_updates": ["callback_query"],
    }

    if offset is not None:
        params["offset"] = offset

    try:
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        response = httpx.get(url, params=params, timeout=10.0)
        return response.json()
    except Exception:
        return {
            "ok": False,
            "result": [],
        }


def answer_callback_query(callback_query_id: str, text: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return False

    try:
        url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
        response = httpx.post(
            url,
            json={
                "callback_query_id": callback_query_id,
                "text": text,
                "show_alert": False,
            },
            timeout=5.0,
        )
        return response.json().get("ok", False)
    except Exception:
        return False
