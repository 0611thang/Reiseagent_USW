import uuid
from datetime import date, timedelta

from agents.recommendation import pick_activities_for_day

DAY_SLOTS = [
    {"start": "09:00", "end": "11:30"},
    {"start": "12:00", "end": "13:30"},
    {"start": "14:00", "end": "16:30"},
    {"start": "19:00", "end": "21:30"},
]

DAY_TITLES = [
    "Ankunft & erste Erkundung",
    "Kultur & Highlights",
    "Letzte Eindrücke & Abreise",
    "Entspannter Reisetag",
    "Stadtleben & Shopping",
    "Ausflug & Natur",
    "Kulinarischer Genuss",
]


def create_plan(request: dict, all_activities: list, weather: list) -> list:
    duration_days = request.get("duration_days", 3)
    used_ids: set = set()
    days = []

    start_date = date.today()

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

        time_slots = []
        for i, activity in enumerate(activities_for_day):
            if i >= len(DAY_SLOTS):
                break
            slot_template = DAY_SLOTS[i]
            time_slots.append({
                "id": str(uuid.uuid4()),
                "start_time": slot_template["start"],
                "end_time": slot_template["end"],
                "activity": activity,
                "notes": None,
            })

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
        "summary": f"Tagesplan für {n_days} Tag(e) mit Zeitfenstern erstellt.",
    }
