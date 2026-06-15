import os
from datetime import datetime, timedelta

import httpx


AVIATIONSTACK_DEFAULT_URL = "https://api.aviationstack.com/v1/flights"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _mock_flight_updates(request: dict) -> dict:
    origin_airport = request.get("origin_airport") or request.get("from_airport") or "BER"
    destination_airport = request.get("destination_airport") or request.get("to_airport") or "JFK"
    flight_number = request.get("flight_number") or "MOCK123"

    departure_date = request.get("departure_date")

    if departure_date:
        scheduled_departure = f"{departure_date}T09:30:00"
        scheduled_arrival = f"{departure_date}T12:45:00"
    else:
        departure = datetime.now() + timedelta(days=1, hours=2)
        arrival = departure + timedelta(hours=3, minutes=15)

        scheduled_departure = departure.isoformat(timespec="seconds")
        scheduled_arrival = arrival.isoformat(timespec="seconds")

    return {
        "source": "mock",
        "checked_at": _now_iso(),
        "flight_number": flight_number,
        "status": "scheduled",
        "origin_airport": origin_airport,
        "destination_airport": destination_airport,
        "scheduled_departure": scheduled_departure,
        "estimated_departure": scheduled_departure,
        "scheduled_arrival": scheduled_arrival,
        "estimated_arrival": scheduled_arrival,
        "delay_minutes": 0,
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
    departure_date = request.get("departure_date")

    if flight_number:
        params["flight_iata"] = flight_number

    if origin_airport:
        params["dep_iata"] = origin_airport

    if destination_airport:
        params["arr_iata"] = destination_airport

    if departure_date:
        params["flight_date"] = departure_date

    return params


def _normalize_aviationstack_response(data: dict, request: dict) -> dict:
    if data.get("error"):
        return {
            "source": "api_error",
            "checked_at": _now_iso(),
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
        "departure_delay_minutes": departure.get("delay"),

        "scheduled_arrival": arrival.get("scheduled"),
        "estimated_arrival": arrival.get("estimated"),
        "actual_arrival": arrival.get("actual"),
        "arrival_delay_minutes": arrival.get("delay"),

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
        fallback = _mock_flight_updates(request)
        fallback["message"] = "Kein FLIGHT_API_KEY gefunden. Mock-Flugdaten verwendet."
        return fallback

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
        fallback = _mock_flight_updates(request)
        fallback["source"] = "mock_after_api_error"
        fallback["api_error"] = str(exc)
        fallback["message"] = "Aviationstack konnte nicht geladen werden. Mock-Daten wurden verwendet."
        return fallback


def get_flight_times_for_trip(request: dict) -> dict:
    return get_flight_status_for_trip(request)


def get_flights_for_trip(request: dict) -> dict:
    return get_flight_status_for_trip(request)


def get_flight_updates(request: dict) -> dict:
    return get_flight_status_for_trip(request)