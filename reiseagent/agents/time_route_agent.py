import json
import uuid

import llm
import prompts


def _time_to_minutes(t):
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _minutes_to_time(minutes):
    minutes = max(0, min(minutes, 23 * 60 + 59))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _validate_slots(slots, activity_ids):
    if not isinstance(slots, list) or len(slots) != len(activity_ids):
        return False
    prev_end = 0
    for slot in slots:
        if slot.get("id") not in activity_ids:
            return False
        try:
            start = _time_to_minutes(slot["start_time"])
            end = _time_to_minutes(slot["end_time"])
        except (KeyError, ValueError):
            return False
        if end <= start:
            return False
        if end > 23 * 60 + 59:
            return False
        if start < prev_end:
            return False
        prev_end = end
    return True


def _parse_slots(raw):
    if not raw:
        return None
    try:
        data = json.loads(raw.strip())
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return None


def _build_activities_text(ordered_activities):
    lines = []
    for a in ordered_activities:
        lines.append(
            f"- id={a['id']} | {a['name']} | {a.get('category', '?')} | {a.get('indoor_outdoor', '?')} | {a.get('duration_minutes', 90)} Min"
        )
    return "\n".join(lines)


def schedule_times_and_routes(ordered_activities: list, day_start: str = "09:00") -> list:
    """
    LLM legt Uhrzeiten und Fahrtzeiten für die übergebenen Aktivitäten fest.
    1x Repair bei ungültiger Antwort, dann LLM-Ausgabe übernehmen (kein det. Fallback).
    Gibt eine Liste von time_slot-Dicts zurück.
    """
    if not ordered_activities:
        return []

    activity_ids = {a["id"] for a in ordered_activities}
    activities_text = _build_activities_text(ordered_activities)
    prompt = prompts.fill(prompts.SCHEDULE_DAY, day_start=day_start, activities=activities_text)

    raw = llm.call("time_route_agent", prompt, prompt_id="SCHEDULE_DAY", max_tokens=800)
    slots = _parse_slots(raw)

    if slots is None or not _validate_slots(slots, activity_ids):
        llm.log_step("time_route_agent", "Ungültige Antwort — starte Repair")
        repair_prompt = prompt + "\n\nFehler in vorheriger Antwort. Bitte gültiges JSON zurückgeben."
        raw2 = llm.call("time_route_agent", repair_prompt, prompt_id="SCHEDULE_DAY_REPAIR", max_tokens=800)
        slots = _parse_slots(raw2)
        if slots is None or not _validate_slots(slots, activity_ids):
            llm.log_step("time_route_agent", "Repair fehlgeschlagen — LLM-Ausgabe wird so übernommen")
            slots = slots or []

    id_to_activity = {a["id"]: a for a in ordered_activities}
    result = []
    for slot in slots:
        activity = id_to_activity.get(slot.get("id"))
        if not activity:
            continue
        result.append({
            "id": str(uuid.uuid4()),
            "start_time": slot.get("start_time", "09:00"),
            "end_time": slot.get("end_time", "10:00"),
            "activity": activity,
            "notes": None,
            "travel_to_next_minutes": slot.get("travel_to_next_minutes", 15),
        })

    return result


def get_agent_insight() -> dict:
    return {
        "agent_name": "time_route_agent",
        "display_label": "Zeit- & Routen-Agent",
        "status": "completed",
        "summary": "Uhrzeiten und Fahrtzeiten vom LLM zugewiesen.",
    }
