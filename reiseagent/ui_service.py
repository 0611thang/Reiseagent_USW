"""
ui_service.py — Business-Logik die aus streamlit_app.py ausgelagert wurde.
Kein st.* hier. Nimmt Inputs, ruft Coordinator/Store/Provider, gibt Ergebnisse zurück.
"""

import store
from agents import coordinator, bank_agent
from providers.calendar import delete_trip_from_calendar


def create_trip(req: dict) -> tuple:
    """Erstellt einen Trip, plant ihn und speichert alles im Store.
    Gibt (trip_id, active_plan) zurück."""
    trip_obj = store.create_trip(req)
    result = coordinator.handle_plan_request(req)

    cl = result["checklist"]
    cl["trip_id"] = trip_obj["id"]

    store.update_trip(trip_obj["id"], {
        "active_plan": result["active_plan"],
        "checklist": cl,
        "agent_insights": result["agent_insights"],
        "flight_updates": result.get("flight_updates"),
    })

    bank_agent.maybe_deduct_trip_cost(trip_obj["id"], result["active_plan"], reason="trip_created")

    return trip_obj["id"], result["active_plan"]


def create_demo_trip() -> tuple:
    """Erstellt die vorgefertigte Berlin-Demo-Reise.
    Gibt (trip_id, active_plan) zurück."""
    demo_request = {
        "destination": "Berlin",
        "duration_days": 3,
        "budget_total": 600.0,
        "currency": "EUR",
        "number_of_people": 2,
        "travel_type": "couple",
        "interests": ["Museen", "gutes Essen", "Sehenswürdigkeiten", "Spaziergänge"],
    }

    trip_obj = store.create_trip(demo_request)
    result = coordinator.handle_plan_request(demo_request, use_mock_weather=True)

    cl = result["checklist"]
    cl["trip_id"] = trip_obj["id"]

    store.update_trip(trip_obj["id"], {
        "active_plan": result["active_plan"],
        "checklist": cl,
        "agent_insights": result["agent_insights"],
    })

    bank_agent.maybe_deduct_trip_cost(trip_obj["id"], result["active_plan"], reason="trip_created")

    return trip_obj["id"], result["active_plan"]


def delete_trip(trip: dict) -> dict:
    """Löscht zuerst sichere Kalender-Einträge und danach den SQLite-Trip."""
    calendar_result = delete_trip_from_calendar(trip)
    trip_deleted = store.delete_trip(trip.get("id"))
    return {
        "trip_deleted": trip_deleted,
        "calendar": calendar_result,
    }


def send_chat_command(trip: dict, prompt: str, chat_messages: list) -> dict:
    """Sendet einen Chat-Befehl an den Coordinator und speichert das Ergebnis.
    chat_messages ist die Liste aus st.session_state — wird direkt befüllt.
    Gibt das Coordinator-Ergebnis zurück."""
    chat_messages.append({"role": "user", "content": prompt})
    trip["chat_messages"] = list(chat_messages)

    result = coordinator.handle_chat_message(trip, prompt)

    chat_messages.append({"role": "assistant", "content": result["message"]})
    trip["chat_messages"] = list(chat_messages)

    store.update_trip(trip["id"], {
        "chat_messages": trip["chat_messages"],
        "active_plan": trip.get("active_plan"),
        "agent_insights": trip.get("agent_insights", []),
        "last_suggestions": trip.get("last_suggestions", []),
        "last_suggestion_context": trip.get("last_suggestion_context", {}),
    })

    return result
