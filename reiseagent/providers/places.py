import os
import random

import httpx

from data.mock_berlin import BERLIN_ACTIVITIES
from providers.geocoding import get_coordinates

LAST_PLACES_STATUS = "not_loaded"

BAD_NAME_WORDS = [
    "siege of",
    "battle of",
    "bataille",
    "fountain",
    "the science",
    "the art",
    "memorial plaque",
    "commemorative plaque",
    "fassade",
    "mietshaus",
    "hotel",
    "rue ",
    "strasse",
    "straße",
    "street",
    "road",
    "avenue",
]

IMPORTANT_NAME_WORDS = [
    "louvre",
    "eiffel",
    "triomphe",
    "notre-dame",
    "notre dame",
    "orsay",
    "montmartre",
    "sainte-chapelle",
    "pantheon",
    "versailles",
    "sagrada",
    "guell",
    "buckingham",
    "tower bridge",
    "hagia",
    "sophia",
    "blue mosque",
    "dom",
    "rijksmuseum",
    "statue of liberty",
    "central park",
    "marienplatz",
    "nymphenburg",
    "englischer garten",
    "deutsches museum",
    "viktualienmarkt",
    "residenz",
]

# Kleine Demo-Ergaenzung: OpenTripMap bleibt die Hauptquelle, aber diese
# bekannten Highlights verhindern schwache Plaene fuer Praesentationsstaedte.
CITY_HIGHLIGHTS = {
    "paris": [
        ("Eiffel Tower", "sightseeing", 48.8584, 2.2945),
        ("Louvre Museum", "museum", 48.8606, 2.3376),
        ("Arc de Triomphe", "sightseeing", 48.8738, 2.2950),
        ("Notre-Dame Cathedral", "sightseeing", 48.8530, 2.3499),
        ("Musee d'Orsay", "museum", 48.8600, 2.3266),
        ("Montmartre", "walk", 48.8867, 2.3431),
    ],
    "rom": [
        ("Colosseum", "sightseeing", 41.8902, 12.4922),
        ("Pantheon", "sightseeing", 41.8986, 12.4769),
        ("Roman Forum", "sightseeing", 41.8925, 12.4853),
        ("Trevi Fountain", "sightseeing", 41.9009, 12.4833),
        ("Vatican Museums", "museum", 41.9065, 12.4536),
        ("Piazza Navona", "walk", 41.8992, 12.4731),
    ],
    "rome": [
        ("Colosseum", "sightseeing", 41.8902, 12.4922),
        ("Pantheon", "sightseeing", 41.8986, 12.4769),
        ("Roman Forum", "sightseeing", 41.8925, 12.4853),
        ("Trevi Fountain", "sightseeing", 41.9009, 12.4833),
        ("Vatican Museums", "museum", 41.9065, 12.4536),
        ("Piazza Navona", "walk", 41.8992, 12.4731),
    ],
    "berlin": [
        ("Brandenburg Gate", "sightseeing", 52.5163, 13.3777),
        ("Museum Island", "museum", 52.5169, 13.4010),
        ("East Side Gallery", "sightseeing", 52.5050, 13.4397),
        ("Reichstag Building", "sightseeing", 52.5186, 13.3762),
        ("Berlin Cathedral", "sightseeing", 52.5191, 13.4010),
        ("Tiergarten", "walk", 52.5145, 13.3501),
    ],
    "barcelona": [
        ("Sagrada Familia", "sightseeing", 41.4036, 2.1744),
        ("Park Guell", "walk", 41.4145, 2.1527),
        ("Casa Batllo", "sightseeing", 41.3917, 2.1649),
        ("La Rambla", "walk", 41.3809, 2.1730),
        ("Gothic Quarter", "walk", 41.3839, 2.1762),
        ("Picasso Museum", "museum", 41.3852, 2.1809),
    ],
    "london": [
        ("Tower Bridge", "sightseeing", 51.5055, -0.0754),
        ("British Museum", "museum", 51.5194, -0.1270),
        ("Buckingham Palace", "sightseeing", 51.5014, -0.1419),
        ("Big Ben", "sightseeing", 51.5007, -0.1246),
        ("Tower of London", "sightseeing", 51.5081, -0.0759),
        ("Hyde Park", "walk", 51.5073, -0.1657),
    ],
    "istanbul": [
        ("Hagia Sophia", "sightseeing", 41.0086, 28.9802),
        ("Blue Mosque", "sightseeing", 41.0054, 28.9768),
        ("Topkapi Palace", "museum", 41.0115, 28.9834),
        ("Grand Bazaar", "shopping", 41.0107, 28.9680),
        ("Galata Tower", "sightseeing", 41.0256, 28.9742),
        ("Basilica Cistern", "sightseeing", 41.0084, 28.9779),
    ],
    "koeln": [
        ("Cologne Cathedral", "sightseeing", 50.9413, 6.9583),
        ("Museum Ludwig", "museum", 50.9409, 6.9598),
        ("Hohenzollern Bridge", "walk", 50.9418, 6.9660),
        ("Old Town Cologne", "walk", 50.9386, 6.9603),
        ("Chocolate Museum Cologne", "museum", 50.9319, 6.9642),
        ("Rheinauhafen", "walk", 50.9255, 6.9654),
    ],
    "cologne": [
        ("Cologne Cathedral", "sightseeing", 50.9413, 6.9583),
        ("Museum Ludwig", "museum", 50.9409, 6.9598),
        ("Hohenzollern Bridge", "walk", 50.9418, 6.9660),
        ("Old Town Cologne", "walk", 50.9386, 6.9603),
        ("Chocolate Museum Cologne", "museum", 50.9319, 6.9642),
        ("Rheinauhafen", "walk", 50.9255, 6.9654),
    ],
    "mallorca": [
        ("Palma Cathedral", "sightseeing", 39.5679, 2.6489),
        ("Serra de Tramuntana", "walk", 39.7300, 2.8500),
        ("Bellver Castle", "sightseeing", 39.5636, 2.6196),
        ("Alcudia Old Town", "walk", 39.8532, 3.1214),
        ("Cuevas del Drach", "sightseeing", 39.5356, 3.3304),
        ("Cap de Formentor", "walk", 39.9619, 3.2124),
    ],
    "amsterdam": [
        ("Rijksmuseum", "museum", 52.3600, 4.8852),
        ("Van Gogh Museum", "museum", 52.3584, 4.8811),
        ("Anne Frank House", "museum", 52.3752, 4.8840),
        ("Canal Ring", "walk", 52.3702, 4.8952),
        ("Vondelpark", "walk", 52.3579, 4.8686),
        ("Dam Square", "sightseeing", 52.3731, 4.8922),
    ],
    "new york": [
        ("Statue of Liberty", "sightseeing", 40.6892, -74.0445),
        ("Central Park", "walk", 40.7829, -73.9654),
        ("Metropolitan Museum of Art", "museum", 40.7794, -73.9632),
        ("Times Square", "sightseeing", 40.7580, -73.9855),
        ("Empire State Building", "sightseeing", 40.7484, -73.9857),
        ("Brooklyn Bridge", "walk", 40.7061, -73.9969),
    ],
    "nyc": [
        ("Statue of Liberty", "sightseeing", 40.6892, -74.0445),
        ("Central Park", "walk", 40.7829, -73.9654),
        ("Metropolitan Museum of Art", "museum", 40.7794, -73.9632),
        ("Times Square", "sightseeing", 40.7580, -73.9855),
        ("Empire State Building", "sightseeing", 40.7484, -73.9857),
        ("Brooklyn Bridge", "walk", 40.7061, -73.9969),
    ],
    "muenchen": [
        ("Marienplatz", "sightseeing", 48.1374, 11.5755),
        ("Neues Rathaus", "sightseeing", 48.1376, 11.5752),
        ("Viktualienmarkt", "restaurant", 48.1351, 11.5764),
        ("Englischer Garten", "walk", 48.1642, 11.6055),
        ("Deutsches Museum", "museum", 48.1299, 11.5834),
        ("Schloss Nymphenburg", "sightseeing", 48.1583, 11.5033),
        ("Muenchner Residenz", "museum", 48.1419, 11.5787),
        ("Olympiapark", "walk", 48.1733, 11.5516),
        ("BMW Welt", "museum", 48.1768, 11.5562),
        ("Pinakothek der Moderne", "museum", 48.1472, 11.5720),
        ("Hofbraeuhaus Muenchen", "restaurant", 48.1376, 11.5799),
        ("Asamkirche", "sightseeing", 48.1351, 11.5698),
        ("Frauenkirche", "sightseeing", 48.1386, 11.5736),
        ("Odeonsplatz", "sightseeing", 48.1428, 11.5774),
        ("Eisbachwelle", "sightseeing", 48.1437, 11.5877),
        ("Maxvorstadt Cafes", "restaurant", 48.1490, 11.5680),
        ("Kaufingerstrasse", "shopping", 48.1371, 11.5709),
        ("Sendlinger Strasse", "shopping", 48.1346, 11.5693),
        ("Isarspaziergang", "walk", 48.1255, 11.5804),
        ("Glockenbachviertel", "walk", 48.1269, 11.5738),
        ("Allianz Arena", "sightseeing", 48.2188, 11.6247),
        ("Lenbachhaus", "museum", 48.1467, 11.5633),
        ("Stachus", "shopping", 48.1390, 11.5655),
        ("Gaertnerplatzviertel", "walk", 48.1319, 11.5769),
        ("Augustiner-Keller", "restaurant", 48.1432, 11.5518),
        ("Elisabethmarkt", "restaurant", 48.1577, 11.5747),
        ("Theresienwiese", "walk", 48.1316, 11.5497),
        ("Alter Botanischer Garten", "walk", 48.1418, 11.5622),
    ],
    "munich": [
        ("Marienplatz", "sightseeing", 48.1374, 11.5755),
        ("Neues Rathaus", "sightseeing", 48.1376, 11.5752),
        ("Viktualienmarkt", "restaurant", 48.1351, 11.5764),
        ("Englischer Garten", "walk", 48.1642, 11.6055),
        ("Deutsches Museum", "museum", 48.1299, 11.5834),
        ("Schloss Nymphenburg", "sightseeing", 48.1583, 11.5033),
        ("Muenchner Residenz", "museum", 48.1419, 11.5787),
        ("Olympiapark", "walk", 48.1733, 11.5516),
        ("BMW Welt", "museum", 48.1768, 11.5562),
        ("Pinakothek der Moderne", "museum", 48.1472, 11.5720),
        ("Hofbraeuhaus Muenchen", "restaurant", 48.1376, 11.5799),
        ("Asamkirche", "sightseeing", 48.1351, 11.5698),
        ("Frauenkirche", "sightseeing", 48.1386, 11.5736),
        ("Odeonsplatz", "sightseeing", 48.1428, 11.5774),
        ("Eisbachwelle", "sightseeing", 48.1437, 11.5877),
        ("Maxvorstadt Cafes", "restaurant", 48.1490, 11.5680),
        ("Kaufingerstrasse", "shopping", 48.1371, 11.5709),
        ("Sendlinger Strasse", "shopping", 48.1346, 11.5693),
        ("Isarspaziergang", "walk", 48.1255, 11.5804),
        ("Glockenbachviertel", "walk", 48.1269, 11.5738),
        ("Allianz Arena", "sightseeing", 48.2188, 11.6247),
        ("Lenbachhaus", "museum", 48.1467, 11.5633),
        ("Stachus", "shopping", 48.1390, 11.5655),
        ("Gaertnerplatzviertel", "walk", 48.1319, 11.5769),
        ("Augustiner-Keller", "restaurant", 48.1432, 11.5518),
        ("Elisabethmarkt", "restaurant", 48.1577, 11.5747),
        ("Theresienwiese", "walk", 48.1316, 11.5497),
        ("Alter Botanischer Garten", "walk", 48.1418, 11.5622),
    ],
}

GENERIC_ACTIVITIES = [
    {
        "id": "city-walk",
        "name": "Stadtspaziergang",
        "category": "walk",
        "description": "Erkundung der Innenstadt zu Fuss.",
        "location": {"name": "Stadtzentrum", "area": "Zentrum", "lat": None, "lng": None},
        "estimated_cost_per_person": 0.0,
        "duration_minutes": 90,
        "indoor_outdoor": "outdoor",
        "tags": ["spaziergaenge", "sehenswuerdigkeiten"],
        "reasoning": "Guenstige Erkundungsoption.",
        "source": "generic",
    },
    {
        "id": "local-restaurant",
        "name": "Lokales Restaurant",
        "category": "restaurant",
        "description": "Typisches Restaurant mit regionaler Kueche.",
        "location": {"name": "Zentrum", "area": "Zentrum", "lat": None, "lng": None},
        "estimated_cost_per_person": 20.0,
        "duration_minutes": 75,
        "indoor_outdoor": "indoor",
        "tags": ["gutes essen", "rain_safe"],
        "reasoning": "Lokale Kueche kennenlernen.",
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
        "name": "Stadtfuehrung",
        "category": "sightseeing",
        "description": "Gefuehrte Tour durch die Highlights der Stadt.",
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
        "reasoning": "Guenstige Erholung.",
        "source": "generic",
    },
]


def _normalize_text(text: str) -> str:
    return (
        text.lower()
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )


def _fetch_from_opentripmap(destination: str, interests: list) -> list:
    global LAST_PLACES_STATUS

    api_key = os.getenv("OPENTRIPMAP_API_KEY", "")
    if not api_key:
        LAST_PLACES_STATUS = "OpenTripMap nicht genutzt: OPENTRIPMAP_API_KEY fehlt."
        return []

    coords = get_coordinates(destination)
    if not coords:
        LAST_PLACES_STATUS = f"OpenTripMap nicht genutzt: keine Koordinaten fuer {destination}."
        return []

    try:
        url = "https://api.opentripmap.com/0.1/en/places/radius"
        raw_activities = []
        errors = []

        for kinds in _build_opentripmap_kinds(interests):
            params = {
                "radius": 12000,
                "lon": coords["lng"],
                "lat": coords["lat"],
                "kinds": kinds,
                "limit": 20,
                "format": "json",
                "apikey": api_key,
            }
            response = httpx.get(url, params=params, timeout=8.0)
            if response.status_code != 200:
                errors.append(f"{kinds}:{response.status_code}")
                continue

            places = response.json()
            if not isinstance(places, list):
                errors.append(f"{kinds}:invalid_response")
                continue

            for place in places:
                name = _get_place_name(place)
                if not name or _is_bad_place_name(name):
                    continue

                kinds_text = _get_place_kinds(place)
                category = _map_kind(kinds_text)
                lat, lng = _get_place_coordinates(place)
                quality_score = _quality_score(place, name, kinds_text)

                raw_activities.append({
                    "id": f"otm-{place.get('xid') or place.get('id') or name}",
                    "name": name,
                    "category": category,
                    "description": f"{name} in {destination}.",
                    "location": {
                        "name": name,
                        "area": destination,
                        "lat": lat,
                        "lng": lng,
                    },
                    "estimated_cost_per_person": _estimate_cost(category),
                    "duration_minutes": 90,
                    "indoor_outdoor": _guess_indoor_outdoor(kinds_text),
                    "tags": _extract_tags(kinds_text, interests),
                    "quality_score": quality_score,
                    "reasoning": f"Empfehlung via OpenTripMap fuer {destination}.",
                    "source": "opentripmap",
                })

        activities = _rank_and_deduplicate(raw_activities)

        if activities:
            LAST_PLACES_STATUS = f"OpenTripMap hat {len(activities)} gute Orte geliefert."
            if errors:
                LAST_PLACES_STATUS += f" Teilfehler: {', '.join(errors[:3])}."
        else:
            LAST_PLACES_STATUS = "OpenTripMap lieferte keine geeigneten Orte."
            if errors:
                LAST_PLACES_STATUS += f" Fehler: {', '.join(errors[:3])}."

        return activities
    except Exception as error:
        LAST_PLACES_STATUS = f"OpenTripMap Fehler: {type(error).__name__}"
        return []


def _build_opentripmap_kinds(interests: list) -> list:
    kinds = [
        "interesting_places",
        "cultural",
        "architecture",
        "historic",
        "museums",
    ]

    interest_to_kinds = {
        "museen": ["museums"],
        "sehenswuerdigkeiten": ["interesting_places", "cultural", "architecture", "historic"],
        "gutes essen": ["foods"],
        "spaziergaenge": ["natural"],
        "natur": ["natural"],
        "shopping": ["shops"],
    }

    for interest in interests:
        normalized = _normalize_text(interest)
        for kind in interest_to_kinds.get(normalized, []):
            if kind not in kinds:
                kinds.append(kind)

    return kinds[:8]


def _get_place_name(place: dict) -> str:
    if place.get("name"):
        return place["name"]
    return place.get("properties", {}).get("name", "")


def _get_place_kinds(place: dict) -> str:
    if place.get("kinds"):
        return place["kinds"]
    return place.get("properties", {}).get("kinds", "")


def _get_place_coordinates(place: dict) -> tuple:
    point = place.get("point", {})
    if point:
        return point.get("lat"), point.get("lon")

    coordinates = place.get("geometry", {}).get("coordinates", [])
    if len(coordinates) >= 2:
        return coordinates[1], coordinates[0]

    return None, None


def _is_bad_place_name(name: str) -> bool:
    normalized = _normalize_text(name)
    if len(normalized) < 4:
        return True
    if any(char.isdigit() for char in normalized):
        if not any(word in normalized for word in IMPORTANT_NAME_WORDS):
            return True
    return any(word in normalized for word in BAD_NAME_WORDS)


def _quality_score(place: dict, name: str, kinds_str: str) -> int:
    normalized_name = _normalize_text(name)
    score = 30

    if any(word in normalized_name for word in IMPORTANT_NAME_WORDS):
        score += 50

    if "museums" in kinds_str or "museum" in kinds_str:
        score += 25
    if "architecture" in kinds_str or "historic_architecture" in kinds_str:
        score += 20
    if "interesting_places" in kinds_str:
        score += 15
    if "cultural" in kinds_str or "historic" in kinds_str:
        score += 10
    if "foods" in kinds_str or "restaurants" in kinds_str:
        score += 8
    if "natural" in kinds_str or "parks" in kinds_str:
        score += 5

    rate = place.get("rate")
    if isinstance(rate, (int, float)):
        score += int(rate) * 5

    if any(word in normalized_name for word in BAD_NAME_WORDS):
        score -= 80

    return max(0, min(score, 100))


def _rank_and_deduplicate(activities: list) -> list:
    best_by_name = {}

    for activity in activities:
        key = _normalize_text(activity["name"]).strip()
        current = best_by_name.get(key)
        if not current or activity.get("quality_score", 0) > current.get("quality_score", 0):
            best_by_name[key] = activity

    ranked = list(best_by_name.values())
    ranked.sort(key=lambda item: item.get("quality_score", 0), reverse=True)

    stable_highlights = ranked[:4]
    variable_pool = ranked[4:24]
    random.shuffle(variable_pool)

    return (stable_highlights + variable_pool)[:30]


def _get_city_key(destination: str) -> str:
    normalized = _normalize_text(destination).strip()
    if normalized in CITY_HIGHLIGHTS:
        return normalized

    if "new york" in normalized:
        return "new york"
    if "mallorca" in normalized or "palma" in normalized:
        return "mallorca"
    if "koeln" in normalized or "cologne" in normalized:
        return "koeln"
    if "muenchen" in normalized or "munich" in normalized:
        return "muenchen"

    return normalized


def _get_city_highlight_activities(destination: str) -> list:
    city_key = _get_city_key(destination)
    highlights = CITY_HIGHLIGHTS.get(city_key, [])

    activities = []
    for index, item in enumerate(highlights):
        name, category, lat, lng = item
        activities.append({
            "id": f"highlight-{city_key}-{index}",
            "name": name,
            "category": category,
            "description": f"Bekanntes Highlight in {destination}: {name}.",
            "location": {
                "name": name,
                "area": destination,
                "lat": lat,
                "lng": lng,
            },
            "estimated_cost_per_person": _estimate_cost(category),
            "duration_minutes": 90,
            "indoor_outdoor": "indoor" if category == "museum" else "mixed",
            "tags": _tags_for_category(category),
            "quality_score": 100,
            "reasoning": f"Bekanntes Stadt-Highlight fuer {destination}.",
            "source": "city_highlight",
        })

    return activities


def _tags_for_category(category: str) -> list:
    if category == "museum":
        return ["museen", "geschichte", "sehenswuerdigkeiten", "rain_safe"]
    if category == "restaurant":
        return ["gutes essen", "rain_safe"]
    if category == "walk":
        return ["spaziergaenge", "natur", "sehenswuerdigkeiten"]
    if category == "shopping":
        return ["shopping", "sehenswuerdigkeiten"]
    return ["sehenswuerdigkeiten", "geschichte"]


def _map_kind(kinds_str: str) -> str:
    if "museum" in kinds_str:
        return "museum"
    if "food" in kinds_str or "restaurant" in kinds_str:
        return "restaurant"
    if "natural" in kinds_str or "park" in kinds_str:
        return "walk"
    return "sightseeing"


def _estimate_cost(category: str) -> float:
    if category == "restaurant":
        return 20.0
    if category == "museum":
        return 12.0
    return 0.0


def _guess_indoor_outdoor(kinds_str: str) -> str:
    if "museum" in kinds_str or "food" in kinds_str or "restaurant" in kinds_str:
        return "indoor"
    if "natural" in kinds_str or "park" in kinds_str:
        return "outdoor"
    return "mixed"


def _extract_tags(kinds_str: str, interests: list) -> list:
    tags = []
    if "museum" in kinds_str:
        tags += ["museen", "rain_safe"]
    if "natural" in kinds_str or "park" in kinds_str:
        tags += ["spaziergaenge", "natur"]
    if "food" in kinds_str or "restaurant" in kinds_str:
        tags += ["gutes essen", "rain_safe"]
    if "historic" in kinds_str or "architecture" in kinds_str:
        tags += ["sehenswuerdigkeiten", "geschichte"]
    return list(set(tags))


def get_places(destination: str, interests: list) -> list:
    global LAST_PLACES_STATUS

    city_highlights = _get_city_highlight_activities(destination)

    if destination.lower() == "berlin":
        LAST_PLACES_STATUS = "Berlin Demo-Daten und Stadt-Highlights verwendet."
        return _rank_and_deduplicate(city_highlights + BERLIN_ACTIVITIES)

    api_results = _fetch_from_opentripmap(destination, interests)

    if len(api_results) >= 12:
        return api_results

    combined_results = _rank_and_deduplicate(api_results + city_highlights)
    if combined_results:
        if city_highlights and api_results:
            LAST_PLACES_STATUS = f"{LAST_PLACES_STATUS} Mit Stadt-Highlights aufgefuellt."
        elif city_highlights:
            LAST_PLACES_STATUS = f"{LAST_PLACES_STATUS} Fallback: Stadt-Highlights verwendet."
        return combined_results

    LAST_PLACES_STATUS = f"{LAST_PLACES_STATUS} Fallback: generische Aktivitaeten verwendet."
    return GENERIC_ACTIVITIES
