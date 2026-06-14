import copy

INTEREST_KEYWORDS = {
    "museen": ["museum", "museen", "kunst", "geschichte", "galerie"],
    "gutes essen": ["restaurant", "essen", "food", "kulinarisch", "gutes essen"],
    "sehenswuerdigkeiten": ["sightseeing", "sehenswuerdigkeiten", "architektur", "fotos"],
    "sehenswürdigkeiten": ["sightseeing", "sehenswuerdigkeiten", "architektur", "fotos"],
    "spaziergaenge": ["walk", "spaziergaenge", "natur", "park", "entspannung"],
    "spaziergänge": ["walk", "spaziergaenge", "natur", "park", "entspannung"],
}


def _normalize(s: str) -> str:
    return s.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")

TIME_SLOTS_TEMPLATE = [
    {"start": "09:00", "end": "11:30"},
    {"start": "12:00", "end": "13:30"},
    {"start": "14:00", "end": "16:30"},
    {"start": "17:00", "end": "19:00"},
    {"start": "19:30", "end": "21:30"},
]

PREFERRED_MORNING = ("sightseeing", "walk", "museum")
PREFERRED_LUNCH = ("restaurant",)
PREFERRED_AFTERNOON = ("museum", "activity", "sightseeing", "walk")
PREFERRED_EVENING = ("restaurant", "activity")


def score_activity(activity: dict, request: dict, weather: dict | None) -> dict:
    interests = [_normalize(i) for i in request.get("interests", [])]
    budget_total = request.get("budget_total", 500.0)
    n_people = request.get("number_of_people", 2)
    duration_days = request.get("duration_days", 3)

    budget_per_activity = budget_total / max(n_people, 1) / max(duration_days * 4, 1)

    tags = [_normalize(t) for t in activity.get("tags", [])]

    interest_hits = 0
    for interest in interests:
        keywords = INTEREST_KEYWORDS.get(interest, [interest])
        keywords_normalized = [_normalize(k) for k in keywords]
        if any(kw in tags for kw in keywords_normalized):
            interest_hits += 1
    interest_match = min(interest_hits / max(len(interests), 1), 1.0)

    cost = activity.get("estimated_cost_per_person", 0.0)
    if cost <= budget_per_activity:
        budget_match = 1.0
    elif cost <= budget_per_activity * 2:
        budget_match = 1.0 - (cost - budget_per_activity) / budget_per_activity * 0.5
    else:
        budget_match = 0.2

    indoor_outdoor = activity.get("indoor_outdoor", "mixed")
    condition = weather.get("condition", "sunny") if weather else "sunny"
    affects = weather.get("affects_outdoor_activities", False) if weather else False

    if not affects:
        weather_match = 1.0
    elif indoor_outdoor == "indoor":
        weather_match = 1.0
    elif indoor_outdoor == "outdoor":
        weather_match = 0.1
    else:
        weather_match = 0.6

    location_match = 0.8
    quality_match = activity.get("quality_score", 50) / 100
    highlight_bonus = 0.12 if activity.get("source") == "city_highlight" else 0

    overall = (
        interest_match * 0.30
        + budget_match * 0.20
        + weather_match * 0.20
        + location_match * 0.10
        + quality_match * 0.20
        + highlight_bonus
    )
    overall = min(overall, 1.0)

    explanation_parts = []
    if interest_match >= 0.5:
        explanation_parts.append("passt zu Interessen")
    if weather_match < 0.5:
        explanation_parts.append("ungünstig bei aktuellem Wetter")
    if budget_match < 0.5:
        explanation_parts.append("etwas über Budget")
    if not explanation_parts:
        explanation_parts.append("gute Gesamtbewertung")

    return {
        "activity_id": activity["id"],
        "interest_match": round(interest_match, 3),
        "budget_match": round(budget_match, 3),
        "weather_match": round(weather_match, 3),
        "location_match": round(location_match, 3),
        "quality_match": round(quality_match, 3),
        "highlight_bonus": round(highlight_bonus, 3),
        "overall_score": round(overall, 3),
        "explanation": ", ".join(explanation_parts),
    }


def pick_activities_for_day(
    all_activities: list,
    day_number: int,
    request: dict,
    weather: dict | None,
    used_ids: set,
) -> list:
    available = [a for a in all_activities if a["id"] not in used_ids]

    scored = []
    for activity in available:
        sc = score_activity(activity, request, weather)
        act = copy.deepcopy(activity)
        act["score"] = sc
        act["estimated_cost_total"] = (
            activity.get("estimated_cost_per_person", 0.0)
            * request.get("number_of_people", 2)
        )
        scored.append(act)

    scored.sort(
        key=lambda a: (
            a["score"]["overall_score"],
            a.get("quality_score", 0),
        ),
        reverse=True,
    )

    selected = []
    used_categories: list[str] = []

    slots_needed = [PREFERRED_MORNING, PREFERRED_LUNCH, PREFERRED_AFTERNOON, PREFERRED_EVENING]

    for preferred_cats in slots_needed:
        candidates = [
            a for a in scored
            if a["id"] not in {s["id"] for s in selected}
            and a["category"] in preferred_cats
        ]
        if candidates:
            selected.append(candidates[0])
        elif scored:
            fallback = next(
                (a for a in scored if a["id"] not in {s["id"] for s in selected}), None
            )
            if fallback:
                selected.append(fallback)

    return selected


def get_agent_insight(n_activities: int) -> dict:
    return {
        "agent_name": "recommendation_agent",
        "display_label": "Empfehlungs Agent",
        "status": "completed",
        "summary": f"{n_activities} Aktivitäten nach Interessen, Wetter und Budget bewertet.",
    }
