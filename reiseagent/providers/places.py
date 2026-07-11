import os
import json
import math
import difflib
import unicodedata

import httpx

import llm
import prompts
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
    "parking",
    "parkplatz",
    "apartment",
    "apartments",
    "office",
    "offices",
    "school",
    "büro",
    "buro",
    "facade",
    "building",
    "house no",
    "wohnhaus",
    "schule",
    "lieferhaus",
    "denkmal",
    "mahn",
    "gedenk",
    "brunnen",
    "statue",
    "sculpture",
    "skulptur",
    "friedhof",
    "cemetery",
    "ehemalige",
]

BAD_KIND_WORDS = [
    "accomodations",
    "accommodations",
    "other_hotels",
    "hotels",
    "apartments",
    "banks",
    "offices",
    "parking",
    "car_parkings",
    "industrial_facilities",
    "commemorative_plaques",
    "monuments_and_memorials",
    "fountains",
    "sculptures",
    "burial_places",
    "cemeteries",
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
    "trevi",
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
    "rathaus",
    "nymphenburg",
    "englischer garten",
    "deutsches museum",
    "viktualienmarkt",
    "residenz",
]

def _normalize_text(text: str) -> str:
    return (
        text.lower()
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
        .replace("\u00c3\u00a4", "ae")
        .replace("\u00c3\u00b6", "oe")
        .replace("\u00c3\u00bc", "ue")
        .replace("\u00c3\u009f", "ss")
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

        for radius in [8000, 15000, 25000]:
            for kinds in _build_opentripmap_kinds(interests):
                params = {
                    "radius": radius,
                    "lon": coords["lng"],
                    "lat": coords["lat"],
                    "kinds": kinds,
                    "limit": 25,
                    "format": "json",
                    "rate": 2,
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
                    activity = _place_to_activity(place, destination, interests)
                    if activity:
                        raw_activities.append(activity)

            if len(_rank_and_deduplicate(raw_activities)) >= 18:
                break

        activities = [
            activity
            for activity in _rank_and_deduplicate(raw_activities)
            if activity.get("quality_score", 0) >= 10
        ]

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
        "tourist_facilities",
        "view_points",
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

def _place_to_activity(place: dict, destination: str, interests: list) -> dict | None:
    name = _get_place_name(place).strip()
    kinds_text = _get_place_kinds(place)
    if not name or _is_bad_place(place, name, kinds_text):
        return None

    category = _map_kind(kinds_text)
    if not _category_allowed_by_interests(category, interests):
        return None

    lat, lng = _get_place_coordinates(place)
    quality_score = _quality_score(place, name, kinds_text)

    return {
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
    }

def _place_to_activity_raw(place: dict, destination: str, interests: list) -> dict | None:
    # Wie _place_to_activity, aber ohne Bad-Place-Filter und ohne Quality-Score —
    # die inhaltliche Bewertung (schlechte Namen raus, Duplikate zusammenfassen,
    # sortieren) übernimmt das LLM in _curate_with_llm(). Nur die reine
    # Interessen-Kategorie-Regel bleibt, weil das eine feste Businessregel ist.
    name = _get_place_name(place).strip() or "(kein Name)"
    kinds_text = _get_place_kinds(place)

    category = _map_kind(kinds_text)
    if not _category_allowed_by_interests(category, interests):
        return None

    lat, lng = _get_place_coordinates(place)

    return {
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
        "reasoning": f"Empfehlung via OpenTripMap fuer {destination}.",
        "source": "opentripmap",
    }

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

def _is_bad_place(place: dict, name: str, kinds_text: str) -> bool:
    normalized_kinds = _normalize_text(kinds_text)
    if _is_bad_place_name(name):
        return True
    if any(word in normalized_kinds for word in BAD_KIND_WORDS):
        return True
    return False

def _category_allowed_by_interests(category: str, interests: list) -> bool:
    if category == "food":
        return True  # Essen immer erlauben, unabhängig von Interessen
    interest_text = " ".join(_normalize_text(item) for item in interests)
    if category == "shopping":
        return "shopping" in interest_text
    if category == "nature":
        return "natur" in interest_text or "spaziergaenge" in interest_text or "spaziergang" in interest_text
    return True

def _quality_score(place: dict, name: str, kinds_str: str) -> int:
    normalized_kinds = _normalize_text(kinds_str)
    score = 5

    # Hauptsignal: OpenTripMap-Rate (0–7 → 0–42 Punkte)
    rate = place.get("rate", 0)
    if isinstance(rate, str) and rate.isdigit():
        rate = int(rate)
    if isinstance(rate, (int, float)):
        score += min(int(rate), 7) * 6

    # Kleiner Kategorie-Bonus
    if "museums" in normalized_kinds or "museum" in normalized_kinds:
        score += 10
    if "historic" in normalized_kinds or "architecture" in normalized_kinds:
        score += 8
    if "cultural" in normalized_kinds or "culture" in normalized_kinds:
        score += 6
    if "view_point" in normalized_kinds or "view_points" in normalized_kinds:
        score += 8
    if "interesting_places" in normalized_kinds:
        score += 4
    if "foods" in normalized_kinds or "restaurants" in normalized_kinds:
        score += 6
    if "shops" in normalized_kinds:
        score += 4
    if "natural" in normalized_kinds or "parks" in normalized_kinds:
        score += 4

    return max(0, min(score, 100))

_DEDUP_FILL_WORDS = {"cathedral", "cathedrale", "museum", "the", "de", "la", "of", "musee", "musee"}
_COORD_RADIUS_M = 150
_NAME_SIMILARITY = 0.82

def _ascii_normalize(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()

def _strip_fill_words(name: str) -> str:
    words = _ascii_normalize(name).split()
    return " ".join(w for w in words if w not in _DEDUP_FILL_WORDS)

def _coord_distance_m(lat1, lng1, lat2, lng2) -> float:
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))

def _is_same_place(a: dict, b: dict) -> bool:
    loc_a = a.get("location", {})
    loc_b = b.get("location", {})
    lat1, lng1 = loc_a.get("lat"), loc_a.get("lng")
    lat2, lng2 = loc_b.get("lat"), loc_b.get("lng")
    if lat1 and lng1 and lat2 and lng2:
        if _coord_distance_m(lat1, lng1, lat2, lng2) < _COORD_RADIUS_M:
            return True
    name_a = _strip_fill_words(a.get("name", ""))
    name_b = _strip_fill_words(b.get("name", ""))
    if name_a and name_b:
        if difflib.SequenceMatcher(None, name_a, name_b).ratio() >= _NAME_SIMILARITY:
            return True
    return False

def _rank_and_deduplicate(activities: list) -> list:
    best_by_name = {}

    for activity in activities:
        activity = activity.copy()
        activity["category"] = _normalize_category(activity.get("category", "sightseeing"))
        key = _normalize_text(activity["name"]).strip()
        current = best_by_name.get(key)
        if not current or activity.get("quality_score", 0) > current.get("quality_score", 0):
            best_by_name[key] = activity

    ranked = list(best_by_name.values())
    ranked.sort(key=lambda item: item.get("quality_score", 0), reverse=True)
    ranked = _balance_categories(ranked)

    # Zweite Dedup-Runde: semantisch (Koordinaten-Nähe oder Namens-Ähnlichkeit)
    deduped = []
    for activity in ranked:
        if not any(_is_same_place(activity, kept) for kept in deduped):
            deduped.append(activity)
    ranked = deduped

    return ranked[:50]

def _balance_categories(ranked: list) -> list:
    selected = []
    counts = {}

    for activity in ranked:
        category = activity.get("category", "sightseeing")
        limit = 5 if category == "culture" else 4
        if counts.get(category, 0) < limit:
            selected.append(activity)
            counts[category] = counts.get(category, 0) + 1

    for activity in ranked:
        if activity not in selected:
            selected.append(activity)

    return selected

def _normalize_category(category: str) -> str:
    if category == "museum":
        return "culture"
    if category == "restaurant":
        return "food"
    if category == "walk":
        return "nature"
    return category

def _map_kind(kinds_str: str) -> str:
    kinds = _normalize_text(kinds_str)
    if "food" in kinds or "restaurant" in kinds:
        return "food"
    if "shop" in kinds:
        return "shopping"
    if "natural" in kinds or "park" in kinds:
        return "nature"
    if "museum" in kinds or "cultural" in kinds or "historic" in kinds or "architecture" in kinds:
        return "culture"
    return "sightseeing"

def _estimate_cost(category: str) -> float:
    category = _normalize_category(category)
    if category == "food":
        return 20.0
    if category == "culture":
        return 12.0
    return 0.0

def _guess_indoor_outdoor(kinds_str: str) -> str:
    kinds = _normalize_text(kinds_str)
    if "museum" in kinds or "food" in kinds or "restaurant" in kinds:
        return "indoor"
    if "natural" in kinds or "park" in kinds:
        return "outdoor"
    return "mixed"

def _extract_tags(kinds_str: str, interests: list) -> list:
    tags = []
    kinds = _normalize_text(kinds_str)
    if "museum" in kinds or "cultural" in kinds:
        tags += ["museen", "rain_safe"]
    if "natural" in kinds or "park" in kinds:
        tags += ["spaziergaenge", "natur"]
    if "food" in kinds or "restaurant" in kinds:
        tags += ["gutes essen", "rain_safe"]
    if "shop" in kinds:
        tags += ["shopping"]
    if "historic" in kinds or "architecture" in kinds or "view_point" in kinds:
        tags += ["sehenswuerdigkeiten", "geschichte"]
    return list(set(tags))

def _fetch_raw_places(destination: str, interests: list) -> list:
    # Holt Orte roh von OpenTripMap, ohne Filterung/Score/Dedup, für den
    # LLM-Kurationspfad. Gleiche API-Abfrage-Logik wie _fetch_from_opentripmap,
    # aber ohne den Python-Vorfilter, damit das LLM alle Kandidaten selbst beurteilt.
    api_key = os.getenv("OPENTRIPMAP_API_KEY", "")
    if not api_key:
        return []

    coords = get_coordinates(destination)
    if not coords:
        return []

    try:
        url = "https://api.opentripmap.com/0.1/en/places/radius"
        raw_activities = []

        for radius in [8000, 15000, 25000]:
            for kinds in _build_opentripmap_kinds(interests):
                params = {
                    "radius": radius,
                    "lon": coords["lng"],
                    "lat": coords["lat"],
                    "kinds": kinds,
                    "limit": 25,
                    "format": "json",
                    "rate": 2,
                    "apikey": api_key,
                }
                response = httpx.get(url, params=params, timeout=8.0)
                if response.status_code != 200:
                    continue

                places = response.json()
                if not isinstance(places, list):
                    continue

                for place in places:
                    activity = _place_to_activity_raw(place, destination, interests)
                    if activity:
                        raw_activities.append(activity)

            if len(raw_activities) >= 40:
                break

        return raw_activities
    except Exception:
        return []

def _build_candidates_text(raw_activities: list) -> str:
    lines = []
    for a in raw_activities:
        lines.append(f"- id={a['id']} | {a['name']} | {a['category']}")
    return "\n".join(lines)

def _curate_with_llm(raw_activities: list, destination: str, interests: list) -> list | None:
    # Lässt das LLM die rohe Ortsliste filtern, Duplikate zusammenführen und
    # sortieren. Gibt None zurück, wenn kein API-Key vorhanden ist oder keine
    # gültige Antwort kommt — der Aufrufer nutzt dann den alten deterministischen
    # Filter als Fallback.
    if not raw_activities:
        return None

    prompt = prompts.fill(
        prompts.CURATE_PLACES,
        destination=destination,
        interests=", ".join(interests) if interests else "keine Angabe",
        candidates=_build_candidates_text(raw_activities),
    )

    raw = llm.call("places_curation_agent", prompt, prompt_id="CURATE_PLACES", max_tokens=1500)
    if not raw:
        return None

    try:
        data = json.loads(raw.strip())
        ids = data.get("ids", [])
    except Exception:
        return None

    if not ids:
        return None

    by_id = {a["id"]: a for a in raw_activities}
    curated = []
    for rank, place_id in enumerate(ids):
        activity = by_id.get(place_id)
        if not activity:
            continue
        activity = activity.copy()
        # Absteigender Score statt des alten regelbasierten Quality-Scores — die
        # LLM-Reihenfolge selbst ist die Bewertung, quality_score bleibt als Feld
        # bestehen, weil agents/recommendation.py es als Signal nutzt.
        activity["quality_score"] = max(10, 95 - rank * 2)
        curated.append(activity)

    return curated or None

def get_places(destination: str, interests: list) -> list:
    global LAST_PLACES_STATUS

    raw_activities = _fetch_raw_places(destination, interests)
    curated = _curate_with_llm(raw_activities, destination, interests)

    if curated:
        LAST_PLACES_STATUS = f"LLM hat {len(curated)} Orte aus {len(raw_activities)} Rohtreffern kuratiert."
        return curated

    # Fallback: kein GROQ_API_KEY, LLM-Fehler oder keine gültige Antwort ->
    # alter deterministischer Filter (unverändert, siehe _fetch_from_opentripmap)
    return _fetch_from_opentripmap(destination, interests)
