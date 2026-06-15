import httpx

KNOWN_CITIES = {
    "berlin": {"lat": 52.52, "lng": 13.405},
    "muenchen": {"lat": 48.1351, "lng": 11.5820},
    "munich": {"lat": 48.1351, "lng": 11.5820},
    "koeln": {"lat": 50.9333, "lng": 6.9500},
    "cologne": {"lat": 50.9333, "lng": 6.9500},
    "duesseldorf": {"lat": 51.2277, "lng": 6.7735},
    "dusseldorf": {"lat": 51.2277, "lng": 6.7735},
    "nuernberg": {"lat": 49.4521, "lng": 11.0767},
    "nuremberg": {"lat": 49.4521, "lng": 11.0767},
    "bruessel": {"lat": 50.8503, "lng": 4.3517},
    "brussels": {"lat": 50.8503, "lng": 4.3517},
    "hamburg": {"lat": 53.5753, "lng": 10.0153},
    "frankfurt": {"lat": 50.1109, "lng": 8.6821},
    "paris": {"lat": 48.8566, "lng": 2.3522},
    "london": {"lat": 51.5074, "lng": -0.1278},
    "amsterdam": {"lat": 52.3676, "lng": 4.9041},
    "rome": {"lat": 41.9028, "lng": 12.4964},
    "rom": {"lat": 41.9028, "lng": 12.4964},
    "barcelona": {"lat": 41.3851, "lng": 2.1734},
}


def _normalize_city_name(destination: str) -> str:
    return (
        destination.lower()
        .strip()
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
        .replace("\u00c3\u00a4", "ae")
        .replace("\u00c3\u00b6", "oe")
        .replace("\u00c3\u00bc", "ue")
        .replace("\u00c3\u009f", "ss")
    )


def get_coordinates(destination: str) -> dict | None:
    key = _normalize_city_name(destination)
    if key in KNOWN_CITIES:
        return KNOWN_CITIES[key]

    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": destination, "format": "json", "limit": 1}
        headers = {"User-Agent": "ReiseAgent/1.0 (HTW Berlin project)"}
        response = httpx.get(url, params=params, headers=headers, timeout=5.0)
        results = response.json()
        if results:
            return {"lat": float(results[0]["lat"]), "lng": float(results[0]["lon"])}
    except Exception:
        pass

    return None
