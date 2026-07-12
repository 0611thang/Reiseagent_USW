import copy
import uuid
from datetime import datetime

from agents.recommendation import score_activity
from agents.budget import calculate_budget


def create_replanning_proposal(trip: dict, weather_event: dict, all_activities: list) -> dict:
    active_plan = trip.get("active_plan")
    if not active_plan:
        raise ValueError("Kein aktiver Plan vorhanden.")

    request = trip["request"]
    day_number = weather_event.get("day_number", 1)
    condition = weather_event.get("condition", "rain")
    description = weather_event.get("description", f"{condition} an Tag {day_number}")

    affected_day = next(
        (d for d in active_plan["days"] if d["day_number"] == day_number), None
    )
    if not affected_day:
        raise ValueError(f"Tag {day_number} nicht im Plan gefunden.")

    used_ids_all = {
        slot["activity"]["id"]
        for day in active_plan["days"]
        for slot in day.get("time_slots", [])
    }

    severity = weather_event.get("severity", "medium")
    replace_types = {"outdoor"}
    if severity in ("high", "severe") or condition in ("storm", "snow"):
        replace_types.add("mixed")

    outdoor_slots = [
        slot for slot in affected_day.get("time_slots", [])
        if slot["activity"].get("indoor_outdoor") in replace_types
    ]

    synthetic_weather = {
        "day_number": day_number,
        "condition": condition,
        "description": description,
        "affects_outdoor_activities": True,
    }

    indoor_candidates = [
        a for a in all_activities
        if a.get("indoor_outdoor") == "indoor"
        and a["id"] not in used_ids_all
    ]

    scored_candidates = sorted(
        indoor_candidates,
        key=lambda a: score_activity(a, request, synthetic_weather)["overall_score"],
        reverse=True,
    )

    changes = []
    replacement_map: dict[str, dict] = {}

    for i, old_slot in enumerate(outdoor_slots):
        if i < len(scored_candidates):
            new_act_base = scored_candidates[i]
            new_act = copy.deepcopy(new_act_base)
            new_act["estimated_cost_total"] = (
                new_act.get("estimated_cost_per_person", 0.0)
                * request.get("number_of_people", 2)
            )
            new_act["score"] = score_activity(new_act, request, synthetic_weather)
            replacement_map[old_slot["id"]] = new_act

            cost_delta = (
                new_act["estimated_cost_total"]
                - old_slot["activity"].get("estimated_cost_total", 0.0)
            )
            changes.append({
                "type": "replace",
                "day_number": day_number,
                "original_activity_id": old_slot["activity"]["id"],
                "new_activity_id": new_act["id"],
                "explanation": f"'{old_slot['activity']['name']}' (outdoor) durch '{new_act['name']}' (indoor) ersetzt wegen {condition}.",
                "cost_delta": round(cost_delta, 2),
            })

    proposed_plan = copy.deepcopy(active_plan)
    proposed_plan["id"] = str(uuid.uuid4())
    proposed_plan["status"] = "proposal_pending"
    proposed_plan["updated_at"] = datetime.now().isoformat()

    for day in proposed_plan["days"]:
        if day["day_number"] == day_number:
            day["weather"] = synthetic_weather
            for slot in day["time_slots"]:
                if slot["id"] in replacement_map:
                    slot["activity"] = replacement_map[slot["id"]]

    budget_after = calculate_budget(proposed_plan["days"], request)
    proposed_plan["budget_summary"] = budget_after

    proposal = {
        "id": str(uuid.uuid4()),
        "plan_id": active_plan["id"],
        "reason": f"Schlechtes Wetter ('{condition}') an Tag {day_number}: {description}",
        "affected_day_numbers": [day_number],
        "changes": changes,
        "proposed_plan": proposed_plan,
        "budget_before": active_plan["budget_summary"],
        "budget_after": budget_after,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    }
    return proposal


def get_agent_insight(n_changes: int) -> dict:
    return {
        "agent_name": "replanning_agent",
        "display_label": "Umplanungs Agent",
        "status": "completed",
        "summary": f"{n_changes} Aktivität(en) durch wettergeeignete Alternativen ersetzt (Vorschlag).",
    }

def _plan_changes_for_day(
        active_plan: dict,
        proposed_plan: dict,
        day_number: int = 1,
) -> list[dict]:
    """
    Vergleicht den aktiven und vorgeschlagenen Tagesplan.

    Daraus werden die Änderungen erzeugt, die später im Proposal und in
    Telegram angezeigt werden.
    """
    old_day = next(
        (
            day
            for day in active_plan.get("days", [])
            if day.get("day_number") == day_number
        ),
        None,
    )

    new_day = next(
        (
            day
            for day in proposed_plan.get("days", [])
            if day.get("day_number") == day_number
        ),
        None,
    )

    if not old_day or not new_day:
        return []

    def index_slots(day: dict) -> dict[str, dict]:
        indexed = {}

        for index, slot in enumerate(day.get("time_slots", [])):
            key = str(
                slot.get("id")
                or f"index:{index}"
            )
            indexed[key] = slot

        return indexed

    old_slots = index_slots(old_day)
    new_slots = index_slots(new_day)

    changes: list[dict] = []

    # Vorhandene alte Slots untersuchen.
    for slot_id, old_slot in old_slots.items():
        new_slot = new_slots.get(slot_id)
        old_activity = old_slot.get("activity", {})

        # Slot wurde vollständig entfernt.
        if not new_slot:
            changes.append({
                "type": "remove_activity",
                "day_number": day_number,
                "activity_id": old_activity.get("id"),
                "activity_name": old_activity.get("name"),
                "explanation": (
                    f"'{old_activity.get('name', 'Aktivität')}' "
                    f"wurde aus Tag {day_number} entfernt."
                ),
                "cost_delta": -float(
                    old_activity.get("estimated_cost_total", 0) or 0
                ),
            })
            continue

        new_activity = new_slot.get("activity", {})

        old_activity_key = (
                old_activity.get("id")
                or old_activity.get("name")
        )

        new_activity_key = (
                new_activity.get("id")
                or new_activity.get("name")
        )

        # Aktivität im Slot wurde ersetzt.
        if old_activity_key != new_activity_key:
            changes.append({
                "type": "replace_activity",
                "day_number": day_number,
                "original_activity_id": old_activity.get("id"),
                "original_activity_name": old_activity.get("name"),
                "new_activity_id": new_activity.get("id"),
                "new_activity_name": new_activity.get("name"),
                "explanation": (
                    f"'{old_activity.get('name', 'Aktivität')}' wurde durch "
                    f"'{new_activity.get('name', 'eine Alternative')}' ersetzt."
                ),
                "cost_delta": round(
                    float(
                        new_activity.get(
                            "estimated_cost_total",
                            0,
                        ) or 0
                    )
                    - float(
                        old_activity.get(
                            "estimated_cost_total",
                            0,
                        ) or 0
                    ),
                    2,
                    ),
            })

        old_start = old_slot.get("start_time")
        old_end = old_slot.get("end_time")
        new_start = new_slot.get("start_time")
        new_end = new_slot.get("end_time")

        # Zeit des Slots wurde verändert.
        if (old_start, old_end) != (new_start, new_end):
            changes.append({
                "type": "change_time",
                "day_number": day_number,
                "activity_id": new_activity.get("id"),
                "activity_name": new_activity.get("name"),
                "explanation": (
                    f"'{new_activity.get('name', 'Aktivität')}' wurde von "
                    f"{old_start}-{old_end} auf "
                    f"{new_start}-{new_end} verschoben."
                ),
                "old_start_time": old_start,
                "old_end_time": old_end,
                "new_start_time": new_start,
                "new_end_time": new_end,
                "cost_delta": 0,
            })

    # Neu hinzugefügte Slots erkennen.
    for slot_id, new_slot in new_slots.items():
        if slot_id in old_slots:
            continue

        new_activity = new_slot.get("activity", {})

        changes.append({
            "type": "add_activity",
            "day_number": day_number,
            "activity_id": new_activity.get("id"),
            "activity_name": new_activity.get("name"),
            "explanation": (
                f"'{new_activity.get('name', 'Aktivität')}' "
                f"wurde zu Tag {day_number} hinzugefügt."
            ),
            "cost_delta": float(
                new_activity.get("estimated_cost_total", 0) or 0
            ),
        })

    return changes

def create_orchestrated_flight_delay_proposal(
        trip: dict,
        proposed_plan: dict,
        flight_updates: dict,
        delay_minutes: int,
        orchestrator_message: str,
        orchestrator_reply: str = "",
) -> dict:
    """
    Verpackt den vom normalen Chat-Orchestrator geänderten Plan als
    Flight-Delay-Proposal.
    """
    active_plan = trip.get("active_plan")

    if not active_plan:
        raise ValueError("Kein aktiver Plan vorhanden.")

    if not proposed_plan:
        raise ValueError(
            "Der Orchestrator hat keinen vorgeschlagenen Plan geliefert."
        )

    proposal_plan = copy.deepcopy(proposed_plan)

    changes = _plan_changes_for_day(
        active_plan,
        proposal_plan,
        day_number=1,
    )

    if not changes:
        raise ValueError(
            "Der Orchestrator hat keine Änderung für den "
            "ersten Reisetag erzeugt."
        )

    # Der Vorschlag erhält eine eigene Plan-ID und ist noch nicht aktiv.
    proposal_plan["id"] = str(uuid.uuid4())
    proposal_plan["status"] = "proposal_pending"
    proposal_plan["updated_at"] = datetime.now().isoformat()

    budget_before = active_plan.get("budget_summary", {})

    budget_after = calculate_budget(
        proposal_plan.get("days", []),
        trip["request"],
    )

    proposal_plan["budget_summary"] = budget_after

    flight_number = (
            trip.get("request", {}).get("flight_number")
            or flight_updates.get("flight_number")
            or "unbekannter Flug"
    )

    return {
        "id": str(uuid.uuid4()),
        "plan_id": active_plan["id"],
        "reason": (
            f"Flugverspätung bei {flight_number}: "
            f"{delay_minutes} Minuten. "
            "Der Orchestrator hat die Auswirkungen auf den "
            "ersten Reisetag geprüft."
        ),
        "affected_day_numbers": [1],
        "changes": changes,
        "proposed_plan": proposal_plan,
        "budget_before": budget_before,
        "budget_after": budget_after,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "trigger": "flight_delay",
        "proposal_source": "llm_orchestrator",
        "flight_updates": flight_updates,
        "delay_minutes": delay_minutes,
        "orchestrator_message": orchestrator_message,
        "orchestrator_reply": orchestrator_reply,
    }

def _shift_time(time_str: str, minutes: int) -> str:
    hour, minute = map(int, time_str.split(":"))
    total = hour * 60 + minute + minutes

    # Nicht über 23:59 hinausgehen
    total = min(total, 23 * 60 + 59)

    new_hour = total // 60
    new_minute = total % 60

    return f"{new_hour:02d}:{new_minute:02d}"


def create_flight_delay_proposal(trip: dict, flight_updates: dict, delay_minutes: int) -> dict:
    """
    Erstellt einen Neuplanungsvorschlag bei Flugverspätung.

    Idee:
    - Wenn der Flug verspätet ist, wird der erste Reisetag zeitlich nach hinten verschoben.
    - Budget vorher/nachher wird verglichen.
    - Der Proposal-Flow bleibt derselbe wie bei Wetter-Proposals.
    """
    active_plan = trip.get("active_plan")
    if not active_plan:
        raise ValueError("Kein aktiver Plan vorhanden.")

    request = trip["request"]

    proposed_plan = copy.deepcopy(active_plan)
    proposed_plan["id"] = str(uuid.uuid4())
    proposed_plan["status"] = "proposal_pending"
    proposed_plan["updated_at"] = datetime.now().isoformat()

    affected_day = None
    for day in proposed_plan.get("days", []):
        if day.get("day_number") == 1:
            affected_day = day
            break

    if not affected_day:
        raise ValueError("Tag 1 nicht im Plan gefunden.")

    changes = []

    for slot in affected_day.get("time_slots", []):
        old_start = slot.get("start_time")
        old_end = slot.get("end_time")
        activity = slot.get("activity", {})

        if not old_start or not old_end:
            continue

        new_start = _shift_time(old_start, delay_minutes)
        new_end = _shift_time(old_end, delay_minutes)

        slot["start_time"] = new_start
        slot["end_time"] = new_end

        changes.append({
            "type": "shift_time",
            "day_number": 1,
            "activity_id": activity.get("id"),
            "activity_name": activity.get("name"),
            "explanation": (
                f"'{activity.get('name', 'Aktivität')}' wurde wegen Flugverspätung "
                f"von {old_start}-{old_end} auf {new_start}-{new_end} verschoben."
            ),
            "time_delta_minutes": delay_minutes,
            "cost_delta": 0,
        })

    budget_before = active_plan.get("budget_summary", {})
    budget_after = calculate_budget(proposed_plan.get("days", []), request)
    proposed_plan["budget_summary"] = budget_after

    flight_number = request.get("flight_number") or flight_updates.get("flight_number") or "unbekannter Flug"

    proposal = {
        "id": str(uuid.uuid4()),
        "plan_id": active_plan["id"],
        "reason": (
            f"Flugverspätung bei {flight_number}: "
            f"{delay_minutes} Minuten Verspätung. "
            "Der erste Reisetag sollte angepasst werden."
        ),
        "affected_day_numbers": [1],
        "changes": changes,
        "proposed_plan": proposed_plan,
        "budget_before": budget_before,
        "budget_after": budget_after,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "trigger": "flight_delay",
        "proposal_source": "legacy_shift_fallback",
        "flight_updates": flight_updates,
        "delay_minutes": delay_minutes,
    }

    return proposal
