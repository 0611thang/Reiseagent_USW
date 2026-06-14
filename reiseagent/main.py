from typing import Optional
import threading
import time
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import store
from agents import coordinator, replanning, budget, monitoring
from agents.navigation import create_navigation_reminder
from agents.daily_brief import create_daily_brief
from agents.profile_learner import run_profile_update
from agents.free_time_detector import detect_and_save_free_days
from agents.suggestion_agent import create_replacement_suggestion, create_suggestions_for_upcoming_free_days
from providers.places import get_places
from providers.weather import get_weather_for_trip
from providers.navigation import get_route
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


def _monitoring_loop():
    while True:
        try:
            monitoring.monitor_all_active_trips()
        except Exception as exc:
            print(f"[monitoring] Fehler im Hintergrundlauf: {exc}")

        time.sleep(MONITORING_INTERVAL_SECONDS)


@app.on_event("startup")
def start_background_monitoring():
    global _monitoring_thread_started

    if _monitoring_thread_started:
        return

    _monitoring_thread_started = True

    thread = threading.Thread(target=_monitoring_loop, daemon=True)
    thread.start()

    print(
        "[monitoring] Hintergrund-Monitoring gestartet: "
        f"alle {MONITORING_INTERVAL_SECONDS} Sekunden"
    )


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
    })

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
    store.update_trip(trip_id, {"chat_messages": trip["chat_messages"]})

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
    telegram_msgs = get_recent_messages(hours=72)
    gmail_emails = get_recent_emails(hours=72)
    return run_profile_update(telegram_messages=telegram_msgs, gmail_emails=gmail_emails)

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
    profile_store.update_suggestion_status(suggestion_id, "accepted")
    return {"status": "accepted"}

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
