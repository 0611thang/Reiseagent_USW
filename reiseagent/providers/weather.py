import httpx
from providers.geocoding import get_coordinates

WMO_TO_CONDITION = {
    0: ("sunny", False),
    1: ("sunny", False),
    2: ("cloudy", False),
    3: ("cloudy", False),
    45: ("cloudy", False),
    48: ("cloudy", False),
    51: ("rain", True),
    53: ("rain", True),
    55: ("rain", True),
    61: ("rain", True),
    63: ("rain", True),
    65: ("rain", True),
    71: ("snow", True),
    73: ("snow", True),
    75: ("snow", True),
    80: ("rain", True),
    81: ("rain", True),
    82: ("rain", True),
    95: ("storm", True),
    96: ("storm", True),
    99: ("storm", True),
}

WMO_DESCRIPTIONS = {
    "sunny": "Sonnig und klar",
    "cloudy": "Bewölkt, aber trocken",
    "rain": "Regen erwartet",
    "snow": "Schnee möglich",
    "storm": "Gewitter möglich",
}

MOCK_WEATHER_CYCLE = ["sunny", "cloudy", "sunny", "rain", "sunny"]


def _mock_weather(duration_days: int) -> list:
    result = []
    for i in range(duration_days):
        condition = MOCK_WEATHER_CYCLE[i % len(MOCK_WEATHER_CYCLE)]
        result.append({
            "day_number": i + 1,
            "condition": condition,
            "description": WMO_DESCRIPTIONS.get(condition, condition),
            "affects_outdoor_activities": condition in ("rain", "storm", "snow"),
        })
    return result


def get_weather_for_trip(request: dict, use_mock: bool = False) -> list:
    destination = request.get("destination", "")
    duration_days = request.get("duration_days", 3)

    if use_mock:
        return _mock_weather(duration_days)

    coords = get_coordinates(destination)
    if not coords:
        return _mock_weather(duration_days)

    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": coords["lat"],
            "longitude": coords["lng"],
            "daily": "weathercode",
            "forecast_days": min(duration_days, 16),
            "timezone": "auto",
        }
        response = httpx.get(url, params=params, timeout=5.0)
        data = response.json()
        codes = data.get("daily", {}).get("weathercode", [])

        result = []
        for i in range(duration_days):
            code = codes[i] if i < len(codes) else 0
            condition, affects = WMO_TO_CONDITION.get(code, ("cloudy", False))
            result.append({
                "day_number": i + 1,
                "condition": condition,
                "description": WMO_DESCRIPTIONS.get(condition, condition),
                "affects_outdoor_activities": affects,
            })
        return result
    except Exception:
        return _mock_weather(duration_days)


def simulate_weather_event(event: dict) -> dict:
    return event
