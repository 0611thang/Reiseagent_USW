import os
import secrets
import httpx
from datetime import datetime, timedelta

import store

DEFAULT_CHAT_ID = "-1003734288144"  # Bisherige Reiseplaner-Gruppe


def _get_chat_id():
    return os.getenv("TELEGRAM_CHAT_ID", "").strip() or DEFAULT_CHAT_ID


def _create_callback_token(trip: dict, proposal_id: str, action: str, kind: str = "flight") -> str:
    callbacks = trip.setdefault("telegram_callbacks", {})
    token = secrets.token_urlsafe(8)
    while token in callbacks:
        token = secrets.token_urlsafe(8)

    callbacks[token] = {
        "action": action,
        "trip_id": trip["id"],
        "proposal_id": proposal_id,
        "kind": kind,
    }
    return token


def _build_callback_data(action: str, token: str) -> str:
    return f"{action}:{token}"


def send_message(text):
    """Schickt eine Nachricht an die Telegram-Gruppe."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        response = httpx.post(url, json={"chat_id": _get_chat_id(), "text": text}, timeout=5.0)
        success = response.json().get("ok", False)
        if not success:
            print(f"[telegram] Nachricht abgelehnt: HTTP {response.status_code}")
        return success
    except Exception as error:
        print(f"[telegram] Nachricht konnte nicht gesendet werden: {type(error).__name__}")
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

    proposal_id = proposal["id"]
    accept_token = _create_callback_token(trip, proposal_id, "accept")
    reject_token = _create_callback_token(trip, proposal_id, "reject")
    saved_trip = store.update_trip(
        trip["id"],
        {"telegram_callbacks": trip["telegram_callbacks"]},
    )
    if not saved_trip:
        print("[telegram] Callback-Tokens konnten nicht gespeichert werden.")
        return False

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
                    "callback_data": _build_callback_data("accept", accept_token),
                },
                {
                    "text": "❌ Ablehnen",
                    "callback_data": _build_callback_data("reject", reject_token),
                },
            ]
        ]
    }

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        response = httpx.post(
            url,
            json={
                "chat_id": _get_chat_id(),
                "text": text,
                "reply_markup": keyboard,
            },
            timeout=5.0,
        )
        success = response.json().get("ok", False)
        if not success:
            print(f"[telegram] Proposal-Nachricht abgelehnt: HTTP {response.status_code}")
        return success
    except Exception as error:
        print(f"[telegram] Proposal-Nachricht fehlgeschlagen: {type(error).__name__}")
        return False


def send_suggestion_proposal(trip: dict, suggestion: dict, home_city: str = "Berlin") -> bool:
    """Sendet einen Freizeitvorschlag per Telegram mit [Annehmen]/[Ablehnen]-Buttons."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return False

    proposal_id = suggestion.get("date", "unknown")
    accept_token = _create_callback_token(trip, str(proposal_id), "accept", kind="suggestion")
    reject_token = _create_callback_token(trip, str(proposal_id), "reject", kind="suggestion")
    # Vorschlags-Infos in den Tokens ablegen, damit der Callback-Handler
    # daraus einen Plan bauen kann (Datum + Heimatstadt).
    for tok in (accept_token, reject_token):
        trip["telegram_callbacks"][tok]["suggestion_date"] = suggestion.get("date", "")
        trip["telegram_callbacks"][tok]["home_city"] = home_city
    saved_trip = store.update_trip(
        trip["id"],
        {"telegram_callbacks": trip["telegram_callbacks"]},
    )
    if not saved_trip:
        print("[telegram] Suggestion-Tokens konnten nicht gespeichert werden.")
        return False

    date_str = suggestion.get("date", "")
    title = suggestion.get("title", "Freizeitvorschlag")
    description = suggestion.get("description", "")
    activities = suggestion.get("activities", [])
    activities_text = "\n".join(f"• {a}" for a in activities) if activities else ""

    text = (
        f"🗓️ Freizeitvorschlag für {date_str}\n\n"
        f"*{title}*\n"
        f"{description}\n\n"
        f"{activities_text}\n\n"
        f"Soll ich einen vollständigen Reiseplan erstellen?"
    )

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "✅ Ja, planen!",
                    "callback_data": _build_callback_data("accept", accept_token),
                },
                {
                    "text": "❌ Nein, danke",
                    "callback_data": _build_callback_data("reject", reject_token),
                },
            ]
        ]
    }

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        response = httpx.post(
            url,
            json={
                "chat_id": _get_chat_id(),
                "text": text,
                "parse_mode": "Markdown",
                "reply_markup": keyboard,
            },
            timeout=5.0,
        )
        success = response.json().get("ok", False)
        if not success:
            print(f"[telegram] Suggestion-Nachricht abgelehnt: HTTP {response.status_code}")
        return success
    except Exception as error:
        print(f"[telegram] Suggestion-Nachricht fehlgeschlagen: {type(error).__name__}")
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
        data = response.json()
        if not data.get("ok", False):
            print(f"[telegram] Callback-Abfrage abgelehnt: HTTP {response.status_code}")
        return data
    except Exception as error:
        print(f"[telegram] Callback-Abfrage fehlgeschlagen: {type(error).__name__}")
        return {
            "ok": False,
            "result": [],
        }


def get_message_updates(offset: int = None, timeout: int = 0) -> list:
    """
    Holt neue Telegram-Freitextnachrichten (kein Button-Klick).

    Additiv zu get_callback_updates(): nutzt denselben getUpdates-Endpunkt,
    filtert aber auf allowed_updates=["message"] und gibt eine einfache Liste
    von {update_id, message_id, chat_id, text, date, from_user} zurueck
    (statt der rohen Telegram-Antwort wie bei get_callback_updates).

    Fail-safe: gibt bei fehlendem Bot-Token oder Fehlern [] zurueck, kein Crash.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return []

    params = {
        "timeout": timeout,
        "allowed_updates": ["message"],
    }

    if offset is not None:
        params["offset"] = offset

    try:
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        response = httpx.get(url, params=params, timeout=timeout + 10.0)
        data = response.json()

        if not data.get("ok", False):
            print(f"[telegram] Message-Abfrage abgelehnt: HTTP {response.status_code}")
            return []

        messages = []
        for update in data.get("result", []):
            msg = update.get("message")
            if not msg:
                continue
            text = msg.get("text")
            if not text:
                continue  # nur Textnachrichten beruecksichtigen (keine Fotos, Sticker, etc.)

            from_user = msg.get("from", {}) or {}
            messages.append({
                "update_id": update.get("update_id"),
                "message_id": msg.get("message_id"),
                "chat_id": (msg.get("chat", {}) or {}).get("id"),
                "text": text,
                "date": msg.get("date"),
                "from_user": from_user.get("username") or from_user.get("first_name"),
            })
        return messages

    except Exception as error:
        print(f"[telegram] Message-Abfrage fehlgeschlagen: {type(error).__name__}")
        return []


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
    except Exception as error:
        print(f"[telegram] Callback-Antwort fehlgeschlagen: {type(error).__name__}")
        return False
