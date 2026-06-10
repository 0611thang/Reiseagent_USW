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
