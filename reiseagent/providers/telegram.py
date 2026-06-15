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
