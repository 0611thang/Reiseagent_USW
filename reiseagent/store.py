import uuid
import json
import sqlite3
import os
from datetime import datetime
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "trips.db")


def _get_conn():
    # check_same_thread=False, weil der Monitoring-Thread auch zugreift
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = _get_conn()
    conn.execute("CREATE TABLE IF NOT EXISTS trips (id TEXT PRIMARY KEY, data TEXT)")
    conn.commit()
    conn.close()


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
        "last_notified_flight_delay_minutes": 0,
        "telegram_callbacks": {},
    }

    conn = _get_conn()
    conn.execute("INSERT INTO trips (id, data) VALUES (?, ?)", (trip_id, json.dumps(trip)))
    conn.commit()
    conn.close()
    return trip


def get_trip(trip_id: str) -> Optional[dict]:
    conn = _get_conn()
    row = conn.execute("SELECT data FROM trips WHERE id=?", (trip_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return json.loads(row[0])


def update_trip(trip_id: str, updates: dict) -> Optional[dict]:
    trip = get_trip(trip_id)
    if not trip:
        return None

    trip.update(updates)

    conn = _get_conn()
    conn.execute("UPDATE trips SET data=? WHERE id=?", (json.dumps(trip), trip_id))
    conn.commit()
    conn.close()
    return trip


def list_trips() -> list:
    conn = _get_conn()
    rows = conn.execute("SELECT data FROM trips").fetchall()
    conn.close()
    return [json.loads(row[0]) for row in rows]


def mark_feedback_requested(trip_id: str) -> Optional[dict]:
    """
    Setzt feedback_requested=True + feedback_requested_at auf dem Trip-JSON-Blob.
    Kein Schema-Feld, keine Migration noetig - trip.get("feedback_requested")
    ist bei allen aelteren Trips einfach None/falsy.
    Kein Crash, wenn der Trip nicht existiert (update_trip gibt dann None zurueck).
    """
    return update_trip(trip_id, {
        "feedback_requested": True,
        "feedback_requested_at": datetime.now().isoformat(timespec="seconds"),
    })


def delete_trip(trip_id: str) -> bool:
    if not trip_id:
        return False

    conn = _get_conn()
    cursor = conn.execute("DELETE FROM trips WHERE id=?", (trip_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted
