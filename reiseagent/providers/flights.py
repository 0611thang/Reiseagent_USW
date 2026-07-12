import os
from datetime import datetime, timedelta

import httpx


AVIATIONSTACK_DEFAULT_URL = "https://api.aviationstack.com/v1/flights"

def _mock_airport(value):
    if isinstance(value, dict):
        return value
    if value:
        return {"name": None, "iata": str(value).upper()}
    return None


def _unavailable_flight(request: dict, reason: str, message: str) -> dict:
    return {
        "source": "api_unavailable",
        "checked_at": _now_iso(),
        "found": False,
        "flight_number": request.get("flight_number"),
        "status": "unknown",
        "error_reason": reason,
        "message": message,
    }


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _mock_flight_updates(request: dict) -> dict:
    origin_airport = request.get("origin_airport") or request.get("from_airport")
    destination_airport = request.get("destination_airport") or request.get("to_airport")
    origin_airport = _mock_airport(origin_airport)
    destination_airport = _mock_airport(destination_airport)
    flight_number = request.get("flight_number") or "MOCK123"

    flight_date = request.get("departure_date") or (datetime.now() + timedelta(days=1)).date().isoformat()
    arrival_time = os.getenv("MOCK_FLIGHT_ARRIVAL_TIME", "12:45").strip() or "12:45"
    try:
        arrival = datetime.fromisoformat(f"{flight_date}T{arrival_time}:00")
    except ValueError:
        arrival = datetime.fromisoformat(f"{flight_date}T12:45:00")

    departure = arrival - timedelta(hours=3, minutes=15)
    scheduled_departure = departure.isoformat(timespec="seconds")
    scheduled_arrival = arrival.isoformat(timespec="seconds")

    try:
        delay_minutes = int(os.getenv("MOCK_FLIGHT_DELAY_MINUTES", "0"))
    except ValueError:
        delay_minutes = 0

    estimated_departure = scheduled_departure
    estimated_arrival = scheduled_arrival

    if delay_minutes > 0:
        estimated_departure = (
                datetime.fromisoformat(scheduled_departure) + timedelta(minutes=delay_minutes)
        ).isoformat(timespec="seconds")

        estimated_arrival = (
                datetime.fromisoformat(scheduled_arrival) + timedelta(minutes=delay_minutes)
        ).isoformat(timespec="seconds")

    return {
        "source": "mock",
        "checked_at": _now_iso(),
        "found": True,
        "flight_number": flight_number,
        "status": "delayed" if delay_minutes > 0 else "scheduled",
        "origin_airport": origin_airport,
        "destination_airport": destination_airport,
        "scheduled_departure": scheduled_departure,
        "estimated_departure": estimated_departure,
        "scheduled_arrival": scheduled_arrival,
        "estimated_arrival": estimated_arrival,
        "delay_minutes": delay_minutes,
        "departure_delay_minutes": delay_minutes,
        "arrival_delay_minutes": delay_minutes,
        "gate": None,
        "terminal": None,
        "message": "Mock-Flugdaten verwendet.",
    }


def _build_aviationstack_params(request: dict) -> dict:
    params = {
        "limit": 1,
    }

    flight_number = request.get("flight_number")
    origin_airport = request.get("origin_airport") or request.get("from_airport")
    destination_airport = request.get("destination_airport") or request.get("to_airport")

    if flight_number:
        params["flight_iata"] = str(flight_number).replace(" ", "").upper()

    if origin_airport:
        params["dep_iata"] = origin_airport

    if destination_airport:
        params["arr_iata"] = destination_airport

    return params


def _normalize_aviationstack_response(data: dict, request: dict) -> dict:
    if data.get("error"):
        return {
            "source": "api_error",
            "checked_at": _now_iso(),
            "found": False,
            "error": data["error"],
            "message": "Aviationstack hat einen Fehler zurückgegeben.",
        }

    flights = data.get("data", [])

    if not flights:
        return {
            "source": "api",
            "checked_at": _now_iso(),
            "found": False,
            "message": "Keine passenden Flugdaten gefunden.",
            "search_request": {
                "flight_number": request.get("flight_number"),
                "origin_airport": request.get("origin_airport") or request.get("from_airport"),
                "destination_airport": request.get("destination_airport") or request.get("to_airport"),
                "departure_date": request.get("departure_date"),
            },
        }

    item = flights[0]

    flight = item.get("flight") or {}
    departure = item.get("departure") or {}
    arrival = item.get("arrival") or {}
    airline = item.get("airline") or {}
    aircraft = item.get("aircraft") or {}

    departure_delay = departure.get("delay") or 0
    arrival_delay = arrival.get("delay") or 0

    return {
        "source": "aviationstack",
        "checked_at": _now_iso(),
        "found": True,

        "flight_date": item.get("flight_date"),
        "status": item.get("flight_status"),

        "flight_number": (
                flight.get("iata")
                or flight.get("icao")
                or request.get("flight_number")
        ),

        "airline": {
            "name": airline.get("name"),
            "iata": airline.get("iata"),
            "icao": airline.get("icao"),
        },

        "origin_airport": {
            "name": departure.get("airport"),
            "iata": departure.get("iata"),
            "icao": departure.get("icao"),
            "timezone": departure.get("timezone"),
            "terminal": departure.get("terminal"),
            "gate": departure.get("gate"),
        },

        "destination_airport": {
            "name": arrival.get("airport"),
            "iata": arrival.get("iata"),
            "icao": arrival.get("icao"),
            "timezone": arrival.get("timezone"),
            "terminal": arrival.get("terminal"),
            "gate": arrival.get("gate"),
        },

        "scheduled_departure": departure.get("scheduled"),
        "estimated_departure": departure.get("estimated"),
        "actual_departure": departure.get("actual"),
        "departure_delay_minutes": departure_delay,

        "scheduled_arrival": arrival.get("scheduled"),
        "estimated_arrival": arrival.get("estimated"),
        "actual_arrival": arrival.get("actual"),
        "arrival_delay_minutes": arrival_delay,

        "delay_minutes": max(
            int(departure_delay or 0),
            int(arrival_delay or 0),
        ),

        "aircraft": {
            "registration": aircraft.get("registration"),
            "iata": aircraft.get("iata"),
            "icao": aircraft.get("icao"),
        },

        "raw": item,
    }


def get_flight_status_for_trip(request: dict, use_mock: bool = False) -> dict:
    if use_mock:
        return _mock_flight_updates(request)

    api_key = os.getenv("FLIGHT_API_KEY")
    api_url = os.getenv("FLIGHT_API_URL", AVIATIONSTACK_DEFAULT_URL)

    if not api_key:
        return _unavailable_flight(
            request,
            "missing_api_key",
            "Kein FLIGHT_API_KEY gefunden. Der Plan wurde ohne Flugdaten erstellt.",
        )

    params = _build_aviationstack_params(request)
    params["access_key"] = api_key

    try:
        response = httpx.get(
            api_url,
            params=params,
            timeout=10.0,
        )
        response.raise_for_status()

        data = response.json()
        return _normalize_aviationstack_response(data, request)

    except Exception as exc:
        reason = type(exc).__name__
        if isinstance(exc, httpx.HTTPStatusError):
            reason += f"_http_{exc.response.status_code}"
        return _unavailable_flight(
            request,
            reason,
            "Aviationstack konnte nicht geladen werden. Der Plan wurde ohne erfundene Flugdaten erstellt.",
        )


def get_flight_times_for_trip(request: dict) -> dict:
    return get_flight_status_for_trip(request)


def get_flights_for_trip(request: dict) -> dict:
    return get_flight_status_for_trip(request)


def get_flight_updates(request: dict) -> dict:
    return get_flight_status_for_trip(request)
