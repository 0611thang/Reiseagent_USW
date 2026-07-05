import copy
import json
import uuid
from datetime import date, timedelta

import llm
import prompts
import memory
from agents import time_route_agent
from agents.recommendation import pick_activities_for_day, MIN_ACTIVITIES_PER_DAY
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

# Kategorien kommen aus places.py bereits normalisiert an:
# culture, food, nature, sightseeing, shopping
DURATION_BY_CATEGORY = {
    "food": 75,
    "culture": 120,
    "sightseeing": 90,
    "nature": 60,
    "shopping": 90,
}

DEFAULT_TRAVEL_MINUTES = 20
LUNCH_TIME = "12:30"
DINNER_TIME = "19:00"


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


def _build_candidate_text(activities: list) -> str:
    lines = []
    for a in activities:
        lines.append(
            f"- id={a['id']} | {a['name']} | {a.get('category', '?')} "
            f"| {a.get('indoor_outdoor', '?')} | {a.get('estimated_cost_per_person', 0)} EUR"
        )
    return "\n".join(lines)


def _build_weather_summary(weather: list) -> str:
    if not weather:
        return "unbekannt"
    parts = []
    for w in weather:
        desc = w.get("description", "?")
        parts.append(f"Tag {w.get('day_number', '?')}: {desc}")
    return ", ".join(parts)


def _validate_curate_response(plan_by_day: dict, id_set: set, duration_days: int) -> str | None:
    """Gibt None zurück wenn valide, sonst eine Fehlerbeschreibung."""
    if not isinstance(plan_by_day, dict):
        return "Kein dict zurückgegeben"
    seen_ids = set()
    for day_num in range(1, duration_days + 1):
        ids = plan_by_day.get(str(day_num), [])
        if len(ids) < MIN_ACTIVITIES_PER_DAY:
            return f"Tag {day_num} hat nur {len(ids)} Aktivitäten (min. {MIN_ACTIVITIES_PER_DAY})"
        for aid in ids:
            if aid not in id_set:
                return f"Unbekannte ID: {aid}"
            if aid in seen_ids:
                return f"Doppelte Aktivität: {aid}"
            seen_ids.add(aid)
    return None


def _parse_curate_response(raw: str) -> dict | None:
    if not raw:
        return None
    try:
        data = json.loads(raw.strip())
        return data.get("tage") or data.get("days") or data
    except Exception:
        return None


def _curate_plan(request: dict, all_activities: list, weather: list, duration_days: int, budget_hint: str = None) -> dict | None:
    """LLM kuratiert den gesamten Plan. Gibt {day_str: [id,...]} oder None (→ Fallback) zurück."""
    candidates = all_activities[:50]
    candidate_text = _build_candidate_text(candidates)
    weather_summary = _build_weather_summary(weather)
    id_set = {a["id"] for a in candidates}

    destination = request.get("destination", "")
    hits = memory.retrieve_context(destination, k=4)
    llm.log_step("memory", f"{len(hits)} relevante Nachrichten gefunden")
    if hits:
        context_block = "Nutzer-Kontext (aus Nachrichten):\n" + "\n".join(f"- {h}" for h in hits) + "\n\n"
    else:
        context_block = ""

    budget_hint_block = f"Wichtiger Hinweis: {budget_hint}\n\n" if budget_hint else ""

    prompt = prompts.fill(
        prompts.CURATE_PLAN,
        destination=destination,
        duration_days=duration_days,
        interests=", ".join(request.get("interests", [])),
        weather_summary=weather_summary,
        candidates=candidate_text,
        context_block=context_block,
        budget_hint_block=budget_hint_block,
    )

    raw = llm.call("planning_agent", prompt, prompt_id="CURATE_PLAN", max_tokens=1000)
    plan = _parse_curate_response(raw)
    error = _validate_curate_response(plan, id_set, duration_days) if plan else "Kein JSON"

    if error:
        llm.log_step("planning_agent", f"Kurator-Antwort ungültig ({error}) — starte Repair")
        repair_prompt = prompt + f"\n\nFehler in vorheriger Antwort: {error}. Bitte korrektes JSON zurückgeben."
        raw2 = llm.call("planning_agent", repair_prompt, prompt_id="CURATE_PLAN_REPAIR", max_tokens=1000)
        plan = _parse_curate_response(raw2)
        error2 = _validate_curate_response(plan, id_set, duration_days) if plan else "Kein JSON"
        if error2:
            llm.log_step("planning_agent", f"Repair fehlgeschlagen ({error2}) — Fallback auf pick_activities_for_day")
            return None

    return plan


def _resolve_activities(activity_ids: list, all_activities: list, request: dict) -> list:
    """IDs → vollständige Activity-Dicts mit cost_total und score."""
    id_map = {a["id"]: a for a in all_activities}
    result = []
    for aid in activity_ids:
        if aid not in id_map:
            continue
        act = copy.deepcopy(id_map[aid])
        act["estimated_cost_total"] = (
            act.get("estimated_cost_per_person", 0.0) * request.get("number_of_people", 2)
        )
        if "score" not in act:
            act["score"] = {"overall_score": 0.5}
        result.append(act)
    return result


def _deterministic_slots(activities_for_day: list, day_start_time: str) -> list:
    """Deterministisches Fallback-Zeitslotting (aus Phase 0, bleibt als Sicherheitsnetz)."""
    time_slots = []
    current_minutes = _time_to_minutes(day_start_time)
    meals_done = 0

    for i, activity in enumerate(activities_for_day):
        if activity.get("category") == "food":
            meal_time = LUNCH_TIME if meals_done == 0 else DINNER_TIME
            current_minutes = max(current_minutes, _time_to_minutes(meal_time))
            meals_done += 1

        duration = _get_duration(activity)
        end_minutes = current_minutes + duration

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

    return time_slots


def create_plan(request: dict, all_activities: list, weather: list, budget_hint: str = None) -> list:
    duration_days = request.get("duration_days", 3)
    day_start_time = request.get("day_start_time", "09:00")

    start_date_str = request.get("start_date")
    start_date = date.fromisoformat(start_date_str) if start_date_str else date.today()

    # LLM kuratiert den gesamten Plan auf einmal
    plan_by_day = _curate_plan(request, all_activities, weather, duration_days, budget_hint=budget_hint)

    used_ids: set = set()
    days = []

    for day_num in range(1, duration_days + 1):
        day_weather = next((w for w in weather if w["day_number"] == day_num), None)

        if plan_by_day and str(day_num) in plan_by_day:
            activities_for_day = _resolve_activities(plan_by_day[str(day_num)], all_activities, request)
        else:
            # Fallback: deterministisch per Tag
            activities_for_day = pick_activities_for_day(
                all_activities=all_activities,
                day_number=day_num,
                request=request,
                weather=day_weather,
                used_ids=used_ids,
            )

        for a in activities_for_day:
            used_ids.add(a["id"])

        # Zeit-/Routen-Agent legt Uhrzeiten fest
        time_slots = time_route_agent.schedule_times_and_routes(activities_for_day, day_start_time)

        # Wenn LLM-Zeitslotting komplett leer → deterministisches Fallback
        if not time_slots:
            time_slots = _deterministic_slots(activities_for_day, day_start_time)

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
        "summary": f"LLM-kuratierter Tagesplan für {n_days} Tag(e) mit KI-Uhrzeiten erstellt.",
    }
