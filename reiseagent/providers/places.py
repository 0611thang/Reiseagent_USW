import os
import httpx
from data.mock_berlin import BERLIN_ACTIVITIES
from providers.geocoding import get_coordinates

GENERIC_ACTIVITIES = [
    {
        "id": "city-walk",
        "name": "Stadtspaziergang",
        "category": "walk",
        "description": "Erkundung der Innenstadt zu Fuß.",
        "location": {"name": "Stadtzentrum", "area": "Zentrum", "lat": None, "lng": None},
        "estimated_cost_per_person": 0.0,
        "duration_minutes": 90,
        "indoor_outdoor": "outdoor",
        "tags": ["spaziergaenge", "sehenswuerdigkeiten"],
        "reasoning": "Günstige Erkundungsoption.",
        "source": "generic",
    },
    {
        "id": "local-restaurant",
        "name": "Lokales Restaurant",
        "category": "restaurant",
        "description": "Typisches Restaurant mit regionaler Küche.",
        "location": {"name": "Zentrum", "area": "Zentrum", "lat": None, "lng": None},
        "estimated_cost_per_person": 20.0,
        "duration_minutes": 75,
        "indoor_outdoor": "indoor",
        "tags": ["gutes essen", "rain_safe"],
        "reasoning": "Lokale Küche kennenlernen.",
        "source": "generic",
    },
    {
        "id": "city-museum",
        "name": "Stadtmuseum",
        "category": "museum",
        "description": "Geschichte und Kultur der Stadt.",
        "location": {"name": "Stadtmuseum", "area": "Zentrum", "lat": None, "lng": None},
        "estimated_cost_per_person": 8.0,
        "duration_minutes": 90,
        "indoor_outdoor": "indoor",
        "tags": ["museen", "geschichte", "rain_safe"],
        "reasoning": "Kulturelles Pflichtprogramm.",
        "source": "generic",
    },
    {
        "id": "sightseeing-tour",
        "name": "Stadtführung",
        "category": "sightseeing",
        "description": "Geführte Tour durch die Highlights der Stadt.",
        "location": {"name": "Marktplatz", "area": "Zentrum", "lat": None, "lng": None},
        "estimated_cost_per_person": 15.0,
        "duration_minutes": 120,
        "indoor_outdoor": "mixed",
        "tags": ["sehenswuerdigkeiten", "fuehrung"],
        "reasoning": "Effiziente Stadtentdeckung.",
        "source": "generic",
    },
    {
        "id": "park-relax",
        "name": "Park und Natur",
        "category": "walk",
        "description": "Entspannung im Stadtpark.",
        "location": {"name": "Stadtpark", "area": "Zentrum", "lat": None, "lng": None},
        "estimated_cost_per_person": 0.0,
        "duration_minutes": 60,
        "indoor_outdoor": "outdoor",
        "tags": ["spaziergaenge", "natur", "entspannung"],
        "reasoning": "Günstige Erholung.",
        "source": "generic",
    },
]


def _fetch_from_opentripmap(destination: str, interests: list) -> list:
    api_key = os.getenv("OPENTRIPMAP_API_KEY", "")
    if not api_key:
        return []

    coords = get_coordinates(destination)
    if not coords:
        return []

    interest_to_kinds = {
        "museen": "museums",
        "sehenswuerdigkeiten": "historic",
        "gutes essen": "foods",
        "spaziergaenge": "natural",
    }

    kinds = ",".join({
        interest_to_kinds.get(i.lower(), "interesting_places")
        for i in interests
    })

    try:
        url = "https://api.opentripmap.com/0.1/en/places/radius"
        params = {
            "radius": 5000,
            "lon": coords["lng"],
            "lat": coords["lat"],
            "kinds": kinds,
            "limit": 20,
            "format": "json",
            "apikey": api_key,
        }
        response = httpx.get(url, params=params, timeout=8.0)
        places = response.json()

        activities = []
        for place in places:
            props = place.get("properties", {})
            if not props.get("name"):
                continue
            activities.append({
                "id": f"otm-{place.get('id', props.get('xid', 'unknown'))}",
                "name": props.get("name", "Unbekannt"),
                "category": _map_kind(props.get("kinds", "")),
                "description": props.get("name", "Sehenswürdigkeit in " + destination),
                "location": {
                    "name": props.get("name", ""),
                    "area": destination,
                    "lat": place.get("geometry", {}).get("coordinates", [None, None])[1],
                    "lng": place.get("geometry", {}).get("coordinates", [None, None])[0],
                },
                "estimated_cost_per_person": 10.0,
                "duration_minutes": 90,
                "indoor_outdoor": "mixed",
                "tags": _extract_tags(props.get("kinds", ""), interests),
                "reasoning": f"Empfehlung via OpenTripMap für {destination}.",
                "source": "api",
            })
        return activities
    except Exception:
        return []


def _map_kind(kinds_str: str) -> str:
    if "museum" in kinds_str:
        return "museum"
    if "food" in kinds_str or "restaurant" in kinds_str:
        return "restaurant"
    if "natural" in kinds_str or "park" in kinds_str:
        return "walk"
    return "sightseeing"


def _extract_tags(kinds_str: str, interests: list) -> list:
    tags = list(interests)
    if "museum" in kinds_str:
        tags += ["museen", "rain_safe"]
    if "natural" in kinds_str:
        tags += ["spaziergaenge"]
    if "food" in kinds_str:
        tags += ["gutes essen", "rain_safe"]
    return list(set(tags))


def get_places(destination: str, interests: list) -> list:
    if destination.lower() == "berlin":
        return BERLIN_ACTIVITIES

    api_results = _fetch_from_opentripmap(destination, interests)
    if api_results:
        return api_results

    return GENERIC_ACTIVITIES
