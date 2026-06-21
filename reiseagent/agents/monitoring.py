from __future__ import annotations

from datetime import datetime
from importlib import import_module
from typing import Any

import store
from agents import replanning
from providers.places import get_places
from providers.weather import get_weather_for_trip
from providers.telegram import send_flight_delay_proposal

BAD_WEATHER = {"rain", "storm", "snow"}
FLIGHT_DELAY_THRESHOLD_MINUTES = 30


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _severity_for_weather(condition: str) -> str:
    if condition == "storm":
        return "severe"
    if condition in {"snow", "rain"}:
        return "medium"
    return "low"


def _weather_changed(old_weather: dict | None, new_weather: dict | None) -> bool:
    if not old_weather or not new_weather:
        return bool(new_weather)

    keys = ("condition", "description", "affects_outdoor_activities")
    return any(old_weather.get(k) != new_weather.get(k) for k in keys)


def _has_pending_weather_proposal(trip: dict, day_number: int, condition: str) -> bool:
    for proposal in trip.get("proposals", []):
        if proposal.get("status") != "pending":
            continue

        reason = proposal.get("reason", "")
        affected_days = proposal.get("affected_day_numbers", [])

        same_day = day_number in affected_days
        same_condition = condition in reason

        if same_day and same_condition:
            return True

    return False


def _append_insight(trip: dict, summary: str, status: str = "completed") -> None:
    insights = trip.get("agent_insights", [])

    insights.append({
        "agent_name": "monitoring_agent",
        "display_label": "Monitoring Agent",
        "status": status,
        "summary": summary,
    })

    store.update_trip(trip["id"], {"agent_insights": insights})


def _refresh_weather(trip: dict, use_mock_weather: bool = False) -> dict[str, Any]:
    request = trip.get("request", {})
    active_plan = trip.get("active_plan")

    if not active_plan:
        return {
            "updated": False,
            "proposals_created": 0,
            "reason": "Kein aktiver Plan.",
        }

    new_weather = get_weather_for_trip(request, use_mock=use_mock_weather)
    weather_by_day = {w.get("day_number"): w for w in new_weather}

    changed_days: list[int] = []

    for day in active_plan.get("days", []):
        day_number = day.get("day_number")
        latest = weather_by_day.get(day_number)

        if latest and _weather_changed(day.get("weather"), latest):
            day["weather"] = latest
            changed_days.append(day_number)

    active_plan["updated_at"] = _now_iso()

    store.update_trip(trip["id"], {
        "active_plan": active_plan,
        "last_weather_update": _now_iso(),
        "weather_updates": new_weather,
    })

    proposals_created = 0

    for weather_event in new_weather:
        condition = weather_event.get("condition")
        day_number = weather_event.get("day_number")
        affects_outdoor = weather_event.get("affects_outdoor_activities", False)

        if condition not in BAD_WEATHER or not affects_outdoor:
            continue

        if _has_pending_weather_proposal(trip, day_number, condition):
            continue

        try:
            all_activities = get_places(
                request.get("destination", ""),
                request.get("interests", []),
            )

            proposal = replanning.create_replanning_proposal(
                store.get_trip(trip["id"]),
                {
                    "day_number": day_number,
                    "condition": condition,
                    "severity": _severity_for_weather(condition),
                    "description": weather_event.get("description", condition),
                },
                all_activities,
            )

            current_trip = store.get_trip(trip["id"])
            proposals = current_trip.get("proposals", [])
            proposals.append(proposal)

            store.update_trip(trip["id"], {"proposals": proposals})
            proposals_created += 1

        except Exception as exc:
            _append_insight(
                trip,
                f"Wetter-Monitoring konnte keinen Replanning-Vorschlag erstellen: {exc}",
                "warning",
            )

    if changed_days or proposals_created:
        _append_insight(
            store.get_trip(trip["id"]),
            (
                "Wetter automatisch aktualisiert. "
                f"Geänderte Tage: {changed_days or 'keine'}, "
                f"neue Vorschläge: {proposals_created}."
            ),
        )

    return {
        "updated": True,
        "changed_days": changed_days,
        "proposals_created": proposals_created,
        "weather": new_weather,
    }


def _call_flight_provider(request: dict) -> Any:
    try:
        flights = import_module("providers.flights")
    except ModuleNotFoundError:
        return None

    for function_name in (
            "get_flight_status_for_trip",
            "get_flight_times_for_trip",
            "get_flights_for_trip",
            "get_flight_updates",
    ):
        func = getattr(flights, function_name, None)

        if callable(func):
            return func(request)

    return None

def _extract_delay_minutes(flight_updates: dict) -> int:
    """
    Liest die Verspätung aus der Flight-API-Antwort.

    Aviationstack liefert meistens:
    - departure_delay_minutes
    - arrival_delay_minutes
    """
    if not flight_updates:
        return 0

    possible_values = [
        flight_updates.get("departure_delay_minutes"),
        flight_updates.get("arrival_delay_minutes"),
        flight_updates.get("delay_minutes"),
    ]

    delays = []
    for value in possible_values:
        try:
            if value is not None:
                delays.append(int(value))
        except (TypeError, ValueError):
            pass

    if delays:
        return max(delays)

    status = str(flight_updates.get("status", "")).lower()
    if status in {"delayed", "diverted", "cancelled", "canceled"}:
        return FLIGHT_DELAY_THRESHOLD_MINUTES

    return 0


def _has_pending_flight_delay_proposal(trip: dict) -> bool:
    for proposal in trip.get("proposals", []):
        if proposal.get("status") == "pending" and proposal.get("trigger") == "flight_delay":
            return True

    return False


def _refresh_flights(trip: dict) -> dict[str, Any]:
    request = trip.get("request", {})

    if not request.get("flight_number"):
        return {
            "updated": False,
            "reason": "Keine Flugnummer im Trip gespeichert.",
        }

    old_notified_delay = trip.get("last_notified_flight_delay_minutes", 0) or 0

    flight_updates = _call_flight_provider(request)

    if flight_updates is None:
        return {
            "updated": False,
            "reason": "Kein providers.flights-Modul oder keine passende Flight-Funktion gefunden.",
        }

    delay_minutes = _extract_delay_minutes(flight_updates)

    update_data = {
        "flight_updates": flight_updates,
        "last_flight_update": _now_iso(),
    }

    proposals_created = 0
    telegram_sent = False

    if (
            delay_minutes >= FLIGHT_DELAY_THRESHOLD_MINUTES
            and delay_minutes > old_notified_delay
            and not _has_pending_flight_delay_proposal(trip)
    ):
        try:
            current_trip = store.get_trip(trip["id"])

            proposal = replanning.create_flight_delay_proposal(
                current_trip,
                flight_updates,
                delay_minutes,
            )

            proposals = current_trip.get("proposals", [])
            proposals.append(proposal)

            update_data["proposals"] = proposals
            update_data["last_notified_flight_delay_minutes"] = delay_minutes

            updated_trip = store.update_trip(trip["id"], update_data)

            telegram_sent = send_flight_delay_proposal(
                updated_trip,
                proposal,
                flight_updates,
            )

            proposals_created = 1

            _append_insight(
                updated_trip,
                (
                    f"Flugverspätung erkannt: {delay_minutes} Minuten. "
                    "Ein Neuplanungsvorschlag wurde erstellt und per Telegram gesendet."
                ),
            )

        except Exception as exc:
            store.update_trip(trip["id"], update_data)
            _append_insight(
                trip,
                f"Flug-Monitoring konnte keinen Neuplanungsvorschlag erstellen: {exc}",
                "warning",
            )

            return {
                "updated": True,
                "flight_updates": flight_updates,
                "delay_minutes": delay_minutes,
                "proposals_created": 0,
                "telegram_sent": False,
                "error": str(exc),
            }

    else:
        store.update_trip(trip["id"], update_data)

        _append_insight(
            store.get_trip(trip["id"]),
            "Flugzeiten/Flugstatus automatisch aktualisiert.",
        )

    return {
        "updated": True,
        "flight_updates": flight_updates,
        "delay_minutes": delay_minutes,
        "proposals_created": proposals_created,
        "telegram_sent": telegram_sent,
    }


def monitor_trip(trip_id: str, use_mock_weather: bool = False) -> dict[str, Any]:
    trip = store.get_trip(trip_id)

    if not trip:
        return {
            "trip_id": trip_id,
            "error": "Trip nicht gefunden.",
        }

    return {
        "trip_id": trip_id,
        "checked_at": _now_iso(),
        "weather": _refresh_weather(trip, use_mock_weather=use_mock_weather),
        "flights": _refresh_flights(store.get_trip(trip_id)),
    }


def monitor_all_active_trips(use_mock_weather: bool = False) -> dict[str, Any]:
    results = []

    for trip in store.list_trips():
        if trip.get("active_plan") and trip["active_plan"].get("status") == "active":
            results.append(
                monitor_trip(trip["id"], use_mock_weather=use_mock_weather)
            )

    return {
        "checked_at": _now_iso(),
        "count": len(results),
        "results": results,
    }
