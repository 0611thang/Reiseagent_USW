import uuid
from typing import Optional

trips: dict = {}


def create_trip(request: dict) -> dict:
    trip_id = str(uuid.uuid4())

    trip = {
        "id": trip_id,
        "request": request,
        "active_plan": None,
        "proposals": [],
        "checklist": None,
        "agent_insights": [],
        "chat_messages": [],
        "weather_updates": [],
        "flight_updates": None,
        "last_weather_update": None,
        "last_flight_update": None,
    }

    trips[trip_id] = trip
    return trip


def get_trip(trip_id: str) -> Optional[dict]:
    return trips.get(trip_id)


def update_trip(trip_id: str, updates: dict) -> Optional[dict]:
    if trip_id not in trips:
        return None

    trips[trip_id].update(updates)
    return trips[trip_id]


def list_trips() -> list:
    return list(trips.values())