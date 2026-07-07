from typing import Optional
import threading
import time
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import store
from agents import coordinator, replanning, budget, monitoring, bank_agent, feedback_agent
from agents.navigation import create_navigation_reminder
from agents.daily_brief import create_daily_brief
from agents.profile_learner import run_profile_update
from agents.free_time_detector import detect_and_save_free_days
from agents.suggestion_agent import create_replacement_suggestion, create_suggestions_for_upcoming_free_days
from providers.places import get_places
from providers.weather import get_weather_for_trip
from providers.navigation import get_route, get_both_routes
from providers.telegram import (
    send_navigation_reminder,
    send_plan_update,
    send_message,
    get_callback_updates,
    get_message_updates,
    answer_callback_query,
    send_suggestion_proposal,
    set_bot_commands,
)
import scheduler
from providers.calendar import create_calendar_event, sync_full_plan_to_calendar
import profile_store

app = FastAPI(title="Reiseplanungs-Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MONITORING_INTERVAL_SECONDS = int(os.getenv("MONITORING_INTERVAL_SECONDS", "1800"))
_monitoring_thread_started = False
_navigation_thread_started = False
_telegram_thread_started = False
_scheduler_thread_started = False


def _monitoring_loop():
    last_weather_check = 0.0

    while True:
        now = time.time()

        # Wetter: weiterhin im alten festen Intervall für alle aktiven Trips
        if now - last_weather_check >= MONITORING_INTERVAL_SECONDS:
            try:
                monitoring.monitor_all_active_trips()
            except Exception as exc:
                print(f"[monitoring] Wetter-Fehler: {exc}")
            last_weather_check = now

        # Flüge: pro Trip individuell, abhängig von Zeit bis Abflug
        for trip in store.list_trips():
            interval = monitoring.required_interval_seconds(trip)
            if interval is None:
                continue

            last_update = trip.get("last_flight_update")
            if last_update is None:
                should_check = True
            else:
                try:
                    elapsed = (datetime.now() - datetime.fromisoformat(last_update)).total_seconds()
                    should_check = elapsed >= interval
                except ValueError:
                    should_check = True

            if should_check:
                try:
                    monitoring.monitor_trip(trip["id"])
                    print(f"[monitoring] Flug-Check für Trip {trip['id']} (Intervall {interval}s)")
                except Exception as exc:
                    print(f"[monitoring] Flug-Fehler für Trip {trip['id']}: {exc}")

        time.sleep(60)


@app.on_event("startup")
def start_background_threads():
    global _monitoring_thread_started, _navigation_thread_started, _telegram_thread_started, _scheduler_thread_started

    store.init_db()

    if not _monitoring_thread_started:
        _monitoring_thread_started = True
        thread = threading.Thread(target=_monitoring_loop, daemon=True)
        thread.start()
        print(
            "[monitoring] Hintergrund-Monitoring gestartet: "
            f"alle {MONITORING_INTERVAL_SECONDS} Sekunden"
        )

    if not _navigation_thread_started:
        _navigation_thread_started = True
        nav_thread = threading.Thread(target=_navigation_reminder_loop, daemon=True)
        nav_thread.start()
        print("[navigation_reminder] Automatische Erinnerungen gestartet.")

    if not _telegram_thread_started:
        _telegram_thread_started = True
        telegram_thread = threading.Thread(target=_telegram_callback_loop, daemon=True)
        telegram_thread.start()
        print("[telegram_callback] Telegram Proposal Buttons gestartet.")

    if not _scheduler_thread_started:
        _scheduler_thread_started = True
        scheduler_thread = threading.Thread(target=scheduler.scheduler_loop, daemon=True)
        scheduler_thread.start()
        print("[scheduler] Wöchentlicher Vorschlags-Scheduler gestartet (läuft samstags).")

    try:
        if set_bot_commands():
            print("[telegram] Bot-Kommandos gesetzt (/bank, /bank_status, /bank_reset).")
        else:
            print("[telegram] Bot-Kommandos nicht gesetzt (kein Token oder Telegram nicht erreichbar).")
    except Exception as exc:
        print(f"[telegram] Bot-Kommandos setzen fehlgeschlagen: {exc}")


class TripRequestBody(BaseModel):
    destination: str
    duration_days: int
    budget_total: float
    currency: str = "EUR"
    number_of_people: int
    travel_type: str
    interests: list[str]

    origin_airport: Optional[str] = None
    destination_airport: Optional[str] = None
    departure_date: Optional[str] = None
    return_date: Optional[str] = None
    flight_number: Optional[str] = None


class ChatBody(BaseModel):
    message: str


class WeatherSimulateBody(BaseModel):
    day_number: int
    condition: str = "rain"
    severity: str = "medium"
    description: str = ""


class ChecklistItemUpdateBody(BaseModel):
    completed: bool


def _build_trip_response(trip: dict) -> dict:
    return {
        "id": trip["id"],
        "request": trip["request"],
        "active_plan": trip["active_plan"],
        "proposals": trip["proposals"],
        "checklist": trip["checklist"],
        "agent_insights": trip["agent_insights"],
        "chat_messages": trip["chat_messages"],
        "weather_updates": trip.get("weather_updates", []),
        "flight_updates": trip.get("flight_updates"),
        "last_weather_update": trip.get("last_weather_update"),
        "last_flight_update": trip.get("last_flight_update"),
        "last_notified_flight_delay_minutes": trip.get("last_notified_flight_delay_minutes", 0),
    }


@app.post("/api/trips/demo")
def create_demo_trip():
    demo_request = {
        "destination": "Berlin",
        "duration_days": 3,
        "budget_total": 600.0,
        "currency": "EUR",
        "number_of_people": 2,
        "travel_type": "couple",
        "interests": ["Museen", "gutes Essen", "Sehenswürdigkeiten", "Spaziergänge"],
    }
    return _create_trip(demo_request, use_mock_weather=True)


@app.post("/api/trips/plan")
def plan_trip(body: TripRequestBody):
    request = body.model_dump()
    if not request.get("flight_number"):
        request["flight_number"] = os.getenv("FLIGHT_NUMBER", "").strip() or None
    return _create_trip(request)


def _create_trip(request: dict, use_mock_weather: bool = False) -> dict:
    trip = store.create_trip(request)

    result = coordinator.handle_plan_request(request, use_mock_weather=use_mock_weather)

    checklist_data = result["checklist"]
    checklist_data["trip_id"] = trip["id"]

    store.update_trip(trip["id"], {
        "active_plan": result["active_plan"],
        "checklist": checklist_data,
        "agent_insights": result["agent_insights"],
        "flight_updates": result.get("flight_updates"),
    })

    bank_agent.maybe_deduct_trip_cost(trip["id"], result["active_plan"], reason="trip_created")

    calendar_result = sync_full_plan_to_calendar(result["active_plan"], trip["id"])
    send_plan_update(result["active_plan"], calendar_synced=calendar_result.get("updated", False))

    return _build_trip_response(store.get_trip(trip["id"]))


@app.get("/api/trips/{trip_id}")
def get_trip(trip_id: str):
    trip = store.get_trip(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip nicht gefunden.")
    return _build_trip_response(trip)


@app.post("/api/trips/{trip_id}/chat")
def chat(trip_id: str, body: ChatBody):
    trip = store.get_trip(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip nicht gefunden.")

    trip["chat_messages"].append({"role": "user", "content": body.message})

    result = coordinator.handle_chat_message(trip, body.message)
    assistant_msg = result["message"]

    trip["chat_messages"].append({"role": "assistant", "content": assistant_msg})
    store.update_trip(trip_id, {
        "chat_messages": trip["chat_messages"],
        "active_plan": trip.get("active_plan"),
        "agent_insights": trip.get("agent_insights", []),
        "last_suggestions": trip.get("last_suggestions", []),
        "last_suggestion_context": trip.get("last_suggestion_context", {}),
    })

    return {"message": assistant_msg, "agent_insights": result.get("agent_insights", [])}


@app.post("/api/trips/{trip_id}/simulate-weather")
def simulate_weather(trip_id: str, body: WeatherSimulateBody):
    trip = store.get_trip(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip nicht gefunden.")
    if not trip.get("active_plan"):
        raise HTTPException(status_code=400, detail="Kein aktiver Plan vorhanden.")

    weather_event = {
        "day_number": body.day_number,
        "condition": body.condition,
        "severity": body.severity,
        "description": body.description or f"{body.condition.capitalize()} an Tag {body.day_number}",
    }

    all_activities = get_places(
        trip["request"]["destination"],
        trip["request"].get("interests", []),
    )

    proposal = replanning.create_replanning_proposal(trip, weather_event, all_activities)

    trip["proposals"].append(proposal)
    store.update_trip(trip_id, {"proposals": trip["proposals"]})

    insight = replanning.get_agent_insight(len(proposal["changes"]))
    trip["agent_insights"].append(insight)
    store.update_trip(trip_id, {"agent_insights": trip["agent_insights"]})
    send_plan_update(trip["active_plan"], warning_text=f"Wetterwarnung: {weather_event['description']}")

    return _build_trip_response(store.get_trip(trip_id))


@app.post("/api/trips/{trip_id}/proposals/{proposal_id}/accept")
def accept_proposal(trip_id: str, proposal_id: str):
    trip = store.get_trip(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip nicht gefunden.")

    proposal = next((p for p in trip["proposals"] if p["id"] == proposal_id), None)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal nicht gefunden.")
    if proposal["status"] != "pending":
        raise HTTPException(status_code=400, detail="Proposal ist nicht mehr ausstehend.")

    proposal["status"] = "accepted"
    new_plan = proposal["proposed_plan"]
    new_plan["status"] = "active"

    store.update_trip(trip_id, {
        "active_plan": new_plan,
        "proposals": trip["proposals"],
    })
    bank_agent.maybe_deduct_trip_cost(trip_id, new_plan, reason="proposal_accepted")
    calendar_result = sync_full_plan_to_calendar(new_plan, trip_id)
    send_plan_update(new_plan, calendar_synced=calendar_result.get("updated", False))

    return _build_trip_response(store.get_trip(trip_id))


@app.post("/api/trips/{trip_id}/proposals/{proposal_id}/reject")
def reject_proposal(trip_id: str, proposal_id: str):
    trip = store.get_trip(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip nicht gefunden.")

    proposal = next((p for p in trip["proposals"] if p["id"] == proposal_id), None)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal nicht gefunden.")

    proposal["status"] = "rejected"
    store.update_trip(trip_id, {"proposals": trip["proposals"]})

    return _build_trip_response(store.get_trip(trip_id))


@app.patch("/api/trips/{trip_id}/checklist/items/{item_id}")
def update_checklist_item(trip_id: str, item_id: str, body: ChecklistItemUpdateBody):
    trip = store.get_trip(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip nicht gefunden.")
    if not trip.get("checklist"):
        raise HTTPException(status_code=404, detail="Keine Checkliste gefunden.")

    item = next((i for i in trip["checklist"]["items"] if i["id"] == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Checklist-Item nicht gefunden.")

    item["completed"] = body.completed
    store.update_trip(trip_id, {"checklist": trip["checklist"]})

    return {"id": item_id, "completed": body.completed}


@app.get("/api/trips/{trip_id}/navigation/{day_number}/{slot_index}")
def get_navigation(trip_id: str, day_number: int, slot_index: int):
    trip = store.get_trip(trip_id)
    if not trip or not trip.get("active_plan"):
        raise HTTPException(status_code=404, detail="Trip oder Plan nicht gefunden.")

    day = next((d for d in trip["active_plan"]["days"] if d["day_number"] == day_number), None)
    if not day:
        raise HTTPException(status_code=404, detail="Tag nicht gefunden.")

    slots = day.get("time_slots", [])
    if slot_index >= len(slots):
        raise HTTPException(status_code=404, detail="Slot nicht gefunden.")

    activity = slots[slot_index]["activity"]
    loc = activity.get("location", {})
    lat = loc.get("lat")
    lng = loc.get("lng")

    route = None
    if lat and lng and slot_index > 0:
        prev_loc = slots[slot_index - 1]["activity"].get("location", {})
        prev_lat = prev_loc.get("lat")
        prev_lng = prev_loc.get("lng")
        if prev_lat and prev_lng:
            route = get_route(prev_lat, prev_lng, lat, lng)

    reminder = create_navigation_reminder(activity["name"], route)
    return {"activity": activity["name"], "route": route, "reminder": reminder}


@app.get("/api/trips/{trip_id}/daily-brief/{day_number}")
def get_daily_brief(trip_id: str, day_number: int):
    trip = store.get_trip(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip nicht gefunden.")
    brief = create_daily_brief(trip, day_number)
    return {"brief": brief, "day_number": day_number}


@app.post("/api/profile/update")
def update_profile():
    from providers.telegram import get_recent_messages
    from providers.gmail import get_recent_emails
    from providers.imap_mail import get_recent_emails as get_imap_emails
    telegram_msgs = get_recent_messages(hours=72)
    gmail_emails = get_recent_emails(hours=72)
    imap_emails = get_imap_emails(limit=20)
    return run_profile_update(
        telegram_messages=telegram_msgs,
        gmail_emails=gmail_emails,
        imap_emails=imap_emails,
    )

@app.post("/api/profile/detect-free-days")
def detect_free_days():
    return detect_and_save_free_days(days_ahead=21)

@app.get("/api/profile/interests")
def get_interests():
    profile_store.init_db()
    return {"interests": profile_store.get_top_interests(limit=15)}

@app.post("/api/suggestions/generate")
def generate_suggestions(home_city: str = "Berlin"):
    return create_suggestions_for_upcoming_free_days(home_city=home_city, max_suggestions=3)

@app.get("/api/suggestions/pending")
def get_pending_suggestions():
    profile_store.init_db()
    return {"suggestions": profile_store.get_pending_suggestions()}

@app.post("/api/suggestions/{suggestion_id}/accept")
def accept_suggestion(suggestion_id: int):
    suggestion = profile_store.get_suggestion(suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Vorschlag nicht gefunden.")

    profile_store.update_suggestion_status(suggestion_id, "accepted")

    activities = suggestion.get("activities", [])
    description = suggestion.get("description") or "Angenommener Vorschlag aus dem Reiseagenten."
    if activities:
        description += "\n\nAktivitaeten:\n" + "\n".join(f"- {a}" for a in activities)

    calendar_result = create_calendar_event(
        title=suggestion["title"],
        description=description,
        date_str=suggestion["date"],
    )

    return {"status": "accepted", "calendar": calendar_result}

@app.post("/api/suggestions/{suggestion_id}/reject")
def reject_suggestion(suggestion_id: int, home_city: str = "Berlin"):
    profile_store.update_suggestion_status(suggestion_id, "rejected")
    replacement = create_replacement_suggestion(suggestion_id, home_city=home_city)
    return {"status": "rejected", "replacement": replacement}

@app.post("/api/trips/{trip_id}/monitor")
def run_monitoring_for_trip(trip_id: str):
    result = monitoring.monitor_trip(trip_id)

    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@app.post("/api/monitoring/run")
def run_monitoring_now():
    return monitoring.monitor_all_active_trips()


@app.post("/api/scheduler/run")
def run_scheduler_now():
    """Manueller Trigger für den wöchentlichen Vorschlags-Scheduler (für Tests)."""
    try:
        scheduler.run_weekly_suggestions()
        pending = profile_store.get_pending_suggestions()
        return {"status": "ok", "suggestions_created": len(pending)}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


class PendingPromptTestBody(BaseModel):
    prompt_type: str = "feedback"
    trip_id: Optional[str] = None


@app.post("/api/pending-prompts/test")
def create_test_pending_prompt(body: PendingPromptTestBody):
    """
    Manueller Test-Endpunkt (für Tests, kein echter Seiteneffekt/Telegram-Versand):
    legt testweise eine offene pending_prompt-Frage an und zeigt alle aktuell
    offenen Fragen. Existiert bereits eine offene Frage, wird keine zweite
    erzeugt (siehe profile_store.create_pending_prompt).
    """
    profile_store.init_db()
    prompt_id = profile_store.create_pending_prompt(body.prompt_type, trip_id=body.trip_id)
    return {
        "pending_prompt_id": prompt_id,
        "open_pending_prompts": profile_store.list_open_pending_prompts(),
    }


@app.get("/api/pending-prompts")
def list_pending_prompts():
    profile_store.init_db()
    return {"open_pending_prompts": profile_store.list_open_pending_prompts()}


@app.post("/api/scheduler/bank-checkin/run")
def run_bank_checkin_now(today: Optional[str] = None):
    """
    Manueller Trigger fuer den monatlichen Bankkonto-Check-in (für Tests).
    today optional als 'YYYY-MM-DD' um ein bestimmtes Datum zu simulieren.
    """
    parsed_today = None
    if today:
        try:
            parsed_today = datetime.fromisoformat(today).date()
        except ValueError:
            raise HTTPException(status_code=400, detail="today muss im Format YYYY-MM-DD sein.")
    try:
        result = scheduler.run_monthly_bank_checkin(today=parsed_today)
        return {"status": "ok", **result}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@app.post("/api/bank/reset-demo")
def reset_bank_demo():
    """Setzt nur die Bankkonto-Daten zurück (für einen sauberen Demo-Start). Andere Profildaten bleiben unberührt."""
    profile_store.init_db()
    profile_store.reset_bank_account_for_demo()
    return {"status": "ok", "reset": True}


@app.post("/api/scheduler/feedback/run")
def run_feedback_check_now(today: Optional[str] = None):
    """
    Manueller Trigger für den täglichen Trip-Ende-Feedback-Check (für Tests).
    today optional als 'YYYY-MM-DD' um ein bestimmtes Datum zu simulieren.
    """
    parsed_today = None
    if today:
        try:
            parsed_today = datetime.fromisoformat(today).date()
        except ValueError:
            raise HTTPException(status_code=400, detail="today muss im Format YYYY-MM-DD sein.")
    try:
        result = scheduler.run_trip_feedback_check(today=parsed_today)
        return {"status": "ok", **result}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}

_telegram_update_offset = None


def _find_telegram_callback(token: str):
    for trip in store.list_trips():
        callback = trip.get("telegram_callbacks", {}).get(token)
        if callback:
            return callback
    return None


def _remove_telegram_callbacks(trip_id: str, proposal_id: str):
    trip = store.get_trip(trip_id)
    if not trip:
        return

    callbacks = trip.get("telegram_callbacks", {})
    remaining = {
        token: data
        for token, data in callbacks.items()
        if data.get("proposal_id") != proposal_id
    }
    store.update_trip(trip_id, {"telegram_callbacks": remaining})


def _handle_telegram_proposal_decision(action: str, trip_id: str, proposal_id: str) -> str:
    trip = store.get_trip(trip_id)

    if not trip:
        return "Trip nicht gefunden."

    proposal = next((p for p in trip.get("proposals", []) if p.get("id") == proposal_id), None)

    if not proposal:
        return "Vorschlag nicht gefunden."

    if proposal.get("status") != "pending":
        return "Dieser Vorschlag wurde bereits bearbeitet."

    if action == "accept":
        proposal["status"] = "accepted"

        new_plan = proposal["proposed_plan"]
        new_plan["status"] = "active"

        store.update_trip(trip_id, {
            "active_plan": new_plan,
            "proposals": trip["proposals"],
        })

        bank_agent.maybe_deduct_trip_cost(trip_id, new_plan, reason="proposal_accepted")

        calendar_result = sync_full_plan_to_calendar(new_plan, trip_id)
        send_plan_update(new_plan, calendar_synced=calendar_result.get("updated", False))

        return "Neuer Reiseplan wurde angenommen."

    if action == "reject":
        proposal["status"] = "rejected"
        store.update_trip(trip_id, {"proposals": trip["proposals"]})

        return "Neuer Reiseplan wurde abgelehnt."

    return "Unbekannte Aktion."


def _handle_telegram_suggestion_decision(action: str, callback_data: dict) -> str:
    date_str = callback_data.get("suggestion_date", "")
    home_city = callback_data.get("home_city", "Berlin")

    if action == "reject":
        for s in profile_store.get_suggestions_for_date(date_str):
            profile_store.update_suggestion_status(s["id"], "rejected")
        return "Vorschlag abgelehnt. Vielleicht beim nächsten Mal!"

    if action == "accept":
        request = {
            "destination": home_city,
            "duration_days": 1,
            "budget_total": 200.0,
            "currency": "EUR",
            "number_of_people": 1,
            "travel_type": "solo",
            "interests": [],
            "start_date": date_str,
            "departure_date": date_str,
            "day_start_time": "09:00",
            "auto": True,
        }
        result = coordinator.handle_plan_request(request)
        trip = store.create_trip(request)
        new_plan = result["active_plan"]
        store.update_trip(trip["id"], {
            "active_plan": new_plan,
            "agent_insights": result["agent_insights"],
        })
        bank_agent.maybe_deduct_trip_cost(trip["id"], new_plan, reason="trip_created")
        calendar_result = sync_full_plan_to_calendar(new_plan, trip["id"])
        send_plan_update(new_plan, calendar_synced=calendar_result.get("updated", False))
        for s in profile_store.get_suggestions_for_date(date_str):
            profile_store.update_suggestion_status(s["id"], "accepted")
        return "Super! Ich habe einen Plan erstellt und schicke ihn dir."

    return "Unbekannte Aktion."


def _handle_bank_checkin_reply(prompt: dict, message: dict) -> bool:
    """
    Interpretiert die Freitextantwort auf den monatlichen Bankkonto-Check-in.

    Gibt True zurück, wenn die Antwort erfolgreich erkannt und gespeichert wurde
    (die pending_prompt-Frage darf dann als resolved markiert werden).
    Gibt False zurück bei unklarer Antwort — die Frage bleibt bewusst offen,
    damit der Nutzer nochmal antworten kann.
    """
    result = bank_agent.interpret_bank_checkin(message.get("text", ""))

    if not result.get("success"):
        send_message(
            "Ich konnte die Zahlen nicht eindeutig erkennen. "
            "Bitte antworte z. B.: Einnahmen 3000 €, Fixkosten 2000 €."
        )
        print(f"[pending_prompt] bank_checkin unklar: '{message.get('text')}'")
        return False

    month = datetime.now().strftime("%Y-%m")
    saved = profile_store.save_bank_checkin(
        month,
        result["income"],
        result["fixed_costs"],
        travel_reserve=result["travel_reserve"],
    )
    send_message(
        f"Danke, gespeichert. Freier Betrag: {saved['free_amount']:.0f} €, "
        f"vorgeschlagene Reise-Rücklage: {saved['travel_reserve']:.0f} €."
    )
    print(f"[pending_prompt] bank_checkin gespeichert: {saved}")
    return True


def _handle_feedback_reply(prompt: dict, message: dict) -> bool:
    """
    Interpretiert die Freitextantwort auf die Feedback-Frage am Ende einer Reise.

    Gibt True zurück, wenn Feedback erfolgreich erkannt und gespeichert wurde
    (die pending_prompt-Frage darf dann als resolved markiert werden), oder
    wenn der zugehörige Trip nicht mehr existiert (dann wird die Frage sauber
    abgebrochen statt haengen zu bleiben). Gibt False zurück bei unklarer
    Antwort — die Frage bleibt offen, damit der Nutzer nochmal antworten kann.
    """
    trip_id = prompt.get("trip_id")
    trip = store.get_trip(trip_id) if trip_id else None

    if trip_id and not trip:
        send_message("Die zugehörige Reise wurde nicht mehr gefunden. Die Feedback-Frage wird geschlossen.")
        print(f"[pending_prompt] feedback: Trip {trip_id} nicht mehr vorhanden - Frage wird abgebrochen.")
        return True

    feedback_items = feedback_agent.interpret_feedback(trip or {}, message.get("text", ""))

    if not feedback_items:
        send_message(
            "Ich konnte noch keine klare Bewertung erkennen. "
            "Bitte antworte z. B.: Museen 5/5, Essen 3/5."
        )
        print(f"[pending_prompt] feedback unklar: '{message.get('text')}'")
        return False

    destination = (trip or {}).get("request", {}).get("destination", "")
    saved = profile_store.save_trip_feedback(trip_id, destination, feedback_items)
    send_message("Danke für dein Feedback. Ich habe deine Bewertung gespeichert.")
    print(f"[pending_prompt] feedback gespeichert: {saved}")
    return True


def _route_pending_prompt_message(message: dict) -> None:
    """
    Ordnet eine Telegram-Freitextnachricht einer offenen pending_prompts-Frage zu.

    Gibt es keine offene Frage, passiert nichts - bestehendes Verhalten
    (generische Profil-/Message-Pipeline) bleibt unveraendert, die Nachricht
    wird hier nicht fälschlich als Bankkonto/Feedback interpretiert.
    """
    prompt = profile_store.get_open_pending_prompt()
    if not prompt:
        return

    prompt_type = prompt.get("type")

    if prompt_type == "bank_checkin":
        success = _handle_bank_checkin_reply(prompt, message)
        if success:
            profile_store.resolve_pending_prompt(prompt["id"])
        # bei unklarer Antwort bleibt die Frage bewusst offen
        return

    if prompt_type == "feedback":
        success = _handle_feedback_reply(prompt, message)
        if success:
            profile_store.resolve_pending_prompt(prompt["id"])
        # bei unklarer Antwort bleibt die Frage bewusst offen
        return

    print(f"[pending_prompt] Unbekannter Prompt-Typ '{prompt_type}' - keine Aktion.")
    profile_store.resolve_pending_prompt(prompt["id"])


# ─────────────────────── Telegram Bankkonto-Kommandos ─────────────────────
# Additiv zur bestehenden pending_prompt-Logik: erlaubt /bank, /bank_status,
# /bank_reset auch OHNE offene Frage, sowie eindeutige spontane
# Bankkonto-Nachrichten (bank_agent.is_spontaneous_bank_message).

BANK_STATUS_COMMANDS = {"/bank_status", "/konto_status"}
BANK_RESET_COMMANDS = {"/bank_reset", "/konto_reset"}


def _first_word(text: str) -> str:
    stripped = (text or "").strip()
    if not stripped:
        return ""
    return stripped.split(maxsplit=1)[0].lower()


def _handle_bank_status_command() -> None:
    account = profile_store.get_current_bank_account()
    if not account:
        send_message("Noch keine Bankkonto-Daten gespeichert.")
        return
    send_message(
        f"Simuliertes Bankkonto ({account['month']}):\n"
        f"Einnahmen: {account['income']:.0f} €\n"
        f"Fixkosten: {account['fixed_costs']:.0f} €\n"
        f"Freier Betrag: {account['free_amount']:.0f} €\n"
        f"Reise-Rücklage: {account['travel_reserve']:.0f} €\n"
        f"Aktueller Kontostand: {account['current_balance']:.0f} €"
    )


def _handle_bank_reset_command() -> None:
    profile_store.reset_bank_account_for_demo()
    send_message("Simuliertes Bankkonto wurde für die Demo zurückgesetzt.")


def _handle_bank_open_question_command() -> None:
    if profile_store.get_open_pending_prompt():
        send_message("Es ist bereits eine Frage offen. Bitte beantworte diese zuerst.")
        return

    profile_store.create_pending_prompt("bank_checkin", metadata={"source": "manual_command"})
    send_message(
        "Okay, ich aktualisiere dein simuliertes Bankkonto.\n"
        "Bitte antworte mit deinen Zahlen, z. B.:\n\n"
        "Einnahmen: 603, Fixkosten: 500\n\n"
        "Optional mit eigener Reise-Rücklage:\n\n"
        "Einnahmen: 603, Fixkosten: 500, Reiserücklage: 50\n\n"
        "Du kannst auch nur Zahlen schicken, z. B.:\n"
        "603 500"
    )


def _handle_spontaneous_bank_message(text: str) -> None:
    """Speichert eine eindeutige Bankkonto-Nachricht direkt, ohne vorher eine
    pending_prompt-Frage zu oeffnen (z.B. '/bank Einnahmen 1000, Fixkosten 500')."""
    result = bank_agent.interpret_bank_checkin(text)

    if not result.get("success"):
        send_message(
            "Ich konnte die Bankdaten nicht eindeutig erkennen. "
            "Bitte schreibe z. B.: /bank Einnahmen 1000, Fixkosten 500."
        )
        print(f"[bank] Spontane Nachricht unklar: '{text}'")
        return

    month = datetime.now().strftime("%Y-%m")
    saved = profile_store.save_bank_checkin(
        month,
        result["income"],
        result["fixed_costs"],
        travel_reserve=result["travel_reserve"],
    )
    send_message(
        f"Bankkonto aktualisiert. Freier Betrag: {saved['free_amount']:.0f} €, "
        f"Reise-Rücklage: {saved['travel_reserve']:.0f} €."
    )
    print(f"[bank] Spontane Nachricht gespeichert: {saved}")


def _route_incoming_telegram_message(message: dict) -> None:
    """
    Erster Anlaufpunkt fuer jede eingehende Telegram-Freitextnachricht.

    Reihenfolge (wichtig fuer Eindeutigkeit):
      1. Feste Bankkonto-Kommandos (/bank_status, /bank_reset, ...) - immer
         direkt verarbeitet, unabhaengig von offenen Fragen.
      2. Ist eine pending_prompt-Frage offen: /bank erneut -> freundlicher
         Hinweis statt als unklare Antwort gezaehlt zu werden. Sonst
         unveraendert an die bestehende _route_pending_prompt_message.
      3. Keine offene Frage + alleinstehendes /bank|/konto|/budget -> oeffnet
         eine gefuehrte Bankkonto-Frage (noch kein Speichern).
      4. Keine offene Frage + eindeutige spontane Bankkonto-Nachricht ->
         direkt speichern.
      5. Alles andere: unveraendertes Verhalten (keine Aktion, wie bisher).
    """
    profile_store.init_db()
    text = message.get("text", "")
    first_word = _first_word(text)

    if first_word in BANK_STATUS_COMMANDS:
        _handle_bank_status_command()
        return

    if first_word in BANK_RESET_COMMANDS:
        _handle_bank_reset_command()
        return

    if profile_store.get_open_pending_prompt():
        if bank_agent.is_bare_bank_command(text):
            send_message("Es ist bereits eine Frage offen. Bitte beantworte diese zuerst.")
            return
        _route_pending_prompt_message(message)
        return

    if bank_agent.is_bare_bank_command(text):
        _handle_bank_open_question_command()
        return

    if bank_agent.is_spontaneous_bank_message(text):
        _handle_spontaneous_bank_message(text)
        return

    # Kein Bankkonto-Kommando, keine spontane Bankkonto-Nachricht, keine offene
    # Frage -> keine Aktion, bestehendes Verhalten bleibt unveraendert.


def _telegram_callback_loop():
    global _telegram_update_offset

    while True:
        try:
            # Beide Abfragen starten bewusst vom selben (noch nicht vorgerueckten)
            # Offset, damit keine Nachricht uebersprungen wird, nur weil der
            # Callback-Teil seinen Offset zuerst weiterschiebt. Vorgerueckt wird
            # erst am Ende, auf den hoechsten tatsaechlich gesehenen update_id.
            current_offset = _telegram_update_offset
            highest_seen_update_id = None

            updates = get_callback_updates(offset=current_offset)

            for update in updates.get("result", []):
                update_id = update["update_id"]
                if highest_seen_update_id is None or update_id > highest_seen_update_id:
                    highest_seen_update_id = update_id

                callback = update.get("callback_query")
                if not callback:
                    continue

                data = callback.get("data", "")
                callback_id = callback.get("id")

                parts = data.split(":", 1)
                if len(parts) != 2:
                    continue

                action, token = parts
                callback_data = _find_telegram_callback(token)
                if not callback_data:
                    if callback_id:
                        answer_callback_query(callback_id, "Dieser Button ist nicht mehr gültig.")
                    continue

                if action != callback_data.get("action"):
                    if callback_id:
                        answer_callback_query(callback_id, "Ungültige Aktion.")
                    continue

                trip_id = callback_data["trip_id"]
                proposal_id = callback_data["proposal_id"]
                kind = callback_data.get("kind", "flight")

                if kind == "suggestion":
                    message = _handle_telegram_suggestion_decision(action, callback_data)
                else:
                    message = _handle_telegram_proposal_decision(
                        action,
                        trip_id,
                        proposal_id,
                    )
                _remove_telegram_callbacks(trip_id, proposal_id)

                if callback_id:
                    answer_callback_query(callback_id, message)

            # --- Freitext-Nachrichten (neu, additiv) ---
            # Nur relevant fuer Nachrichten, die eine offene pending_prompts-Frage
            # beantworten. Ohne offene Frage passiert hier nichts.
            text_messages = get_message_updates(offset=current_offset)
            for text_message in text_messages:
                update_id = text_message["update_id"]
                if highest_seen_update_id is None or update_id > highest_seen_update_id:
                    highest_seen_update_id = update_id
                _route_incoming_telegram_message(text_message)

            if highest_seen_update_id is not None:
                _telegram_update_offset = highest_seen_update_id + 1

        except Exception as exc:
            print(f"[telegram_callback] Fehler: {exc}")

        time.sleep(5)


def _navigation_reminder_loop():
    """Läuft im Hintergrund, prüft jede Minute ob eine Erinnerung gesendet werden soll."""
    sent_reminders = set()

    while True:
        try:
            now = datetime.now()
            current_time = now.strftime("%H:%M")

            for trip in store.list_trips():
                plan = trip.get("active_plan")
                if not plan:
                    continue

                for day in plan.get("days", []):
                    slots = day.get("time_slots", [])
                    for i, slot in enumerate(slots):
                        activity = slot["activity"]
                        activity_id = activity["id"]
                        start_time = slot["start_time"]

                        loc = activity.get("location", {})
                        lat = loc.get("lat")
                        lng = loc.get("lng")

                        routes = {"foot": None, "car": None}
                        if i > 0 and lat and lng:
                            prev_loc = slots[i - 1]["activity"].get("location", {})
                            prev_lat = prev_loc.get("lat")
                            prev_lng = prev_loc.get("lng")
                            if prev_lat and prev_lng:
                                routes = get_both_routes(prev_lat, prev_lng, lat, lng)

                        foot = routes.get("foot")
                        minutes_buffer = (foot["duration_minutes"] + 15) if foot else 30

                        h, m = map(int, start_time.split(":"))
                        total_minutes = h * 60 + m - minutes_buffer
                        send_hour = total_minutes // 60
                        send_minute = total_minutes % 60
                        send_time = f"{send_hour:02d}:{send_minute:02d}"

                        reminder_key = f"{trip['id']}_{activity_id}_{now.date()}"

                        if current_time == send_time and reminder_key not in sent_reminders:
                            send_navigation_reminder(activity["name"], start_time, routes)
                            sent_reminders.add(reminder_key)

        except Exception as e:
            print(f"[navigation_reminder] Fehler: {e}")

        time.sleep(60)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
