import os
import httpx
from datetime import datetime, timedelta


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
