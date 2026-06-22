import uuid
from datetime import date, timedelta

from agents.recommendation import pick_activities_for_day
from providers.navigation import get_route

DAY_TITLES = [
    "Ankunft & erste Erkundung",
    "Kultur & Highlights",
    "Letzte Eindrücke & Abreise",
    "Entspannter Reisetag",
    "Stadtleben & Shopping",
    "Ausflug & Natur",
    "Kulinarischer Genuss",
]

DURATION_BY_CATEGORY = {
    "restaurant": 75,
    "essen": 75,
    "museum": 120,
    "sehenswuerdigkeit": 90,
    "sehenswürdigkeiten": 90,
    "sightseeing": 90,
    "park": 60,
    "walk": 60,
    "shopping": 90,
    "activity": 90,
}

DEFAULT_TRAVEL_MINUTES = 20


def _get_duration(activity):
    category = activity.get("category", "").lower()
    return DURATION_BY_CATEGORY.get(category, activity.get("duration_minutes", 90))


def _get_travel_minutes(from_activity, to_activity):
    from_loc = from_activity.get("location", {})
    to_loc = to_activity.get("location", {})
    lat1 = from_loc.get("lat")
    lng1 = from_loc.get("lng")
    lat2 = to_loc.get("lat")
    lng2 = to_loc.get("lng")

    if not (lat1 and lng1 and lat2 and lng2):
        return DEFAULT_TRAVEL_MINUTES

    result = get_route(lat1, lng1, lat2, lng2, "foot-walking")
    if result and result.get("duration_minutes"):
        return int(result["duration_minutes"])

    return DEFAULT_TRAVEL_MINUTES


def _time_to_minutes(time_str):
    parts = time_str.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def _minutes_to_time(minutes):
    minutes = max(0, min(minutes, 23 * 60 + 59))
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


def create_plan(request: dict, all_activities: list, weather: list) -> list:
    duration_days = request.get("duration_days", 3)
    day_start_time = request.get("day_start_time", "09:00")

    start_date_str = request.get("start_date")
    start_date = date.fromisoformat(start_date_str) if start_date_str else date.today()

    used_ids: set = set()
    days = []

    for day_num in range(1, duration_days + 1):
        day_weather = next((w for w in weather if w["day_number"] == day_num), None)

        activities_for_day = pick_activities_for_day(
            all_activities=all_activities,
            day_number=day_num,
            request=request,
            weather=day_weather,
            used_ids=used_ids,
        )

        for a in activities_for_day:
            used_ids.add(a["id"])

        # Aktivitäten dynamisch takten: Start → +Dauer → +Fahrtzeit → nächste Aktivität
        time_slots = []
        current_minutes = _time_to_minutes(day_start_time)

        for i, activity in enumerate(activities_for_day):
            duration = _get_duration(activity)
            end_minutes = current_minutes + duration

            # Fahrtzeit zur nächsten Aktivität berechnen
            travel_to_next = 0
            if i < len(activities_for_day) - 1:
                travel_to_next = _get_travel_minutes(activity, activities_for_day[i + 1])

            time_slots.append({
                "id": str(uuid.uuid4()),
                "start_time": _minutes_to_time(current_minutes),
                "end_time": _minutes_to_time(end_minutes),
                "activity": activity,
                "notes": None,
                "travel_to_next_minutes": travel_to_next,
            })

            current_minutes = end_minutes + travel_to_next

        title_idx = (day_num - 1) % len(DAY_TITLES)
        days.append({
            "day_number": day_num,
            "title": DAY_TITLES[title_idx],
            "date": (start_date + timedelta(days=day_num - 1)).isoformat(),
            "weather": day_weather,
            "time_slots": time_slots,
        })

    return days


def get_agent_insight(n_days: int) -> dict:
    return {
        "agent_name": "planning_agent",
        "display_label": "Planungs Agent",
        "status": "completed",
        "summary": f"Dynamischer Tagesplan für {n_days} Tag(e) mit echten Dauern und Fahrtzeiten erstellt.",
    }
