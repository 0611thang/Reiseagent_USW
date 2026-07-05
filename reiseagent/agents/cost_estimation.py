import json

import llm
import prompts

MAX_BUDGET_ATTEMPTS = 3


def _build_activities_text(activities: list) -> str:
    lines = []
    for a in activities:
        lines.append(f"- id={a['id']} | {a['name']} | {a.get('category', '?')}")
    return "\n".join(lines)


def _parse_cost_response(raw: str) -> dict | None:
    if not raw:
        return None
    try:
        data = json.loads(raw.strip())
        items = data.get("kosten") or data.get("costs") or data
        return {item["id"]: item["preis_pro_person"] for item in items if "id" in item and "preis_pro_person" in item}
    except Exception:
        return None


def estimate_costs_for_day(day: dict, request: dict) -> None:
    """Schätzt Kosten pro Aktivität eines Tages per LLM, aktualisiert die Aktivitäten in-place.
    Schlägt die Schätzung fehl (kein API-Key, Parse-Fehler), bleiben die bisherigen
    Pauschalpreise aus places.py unverändert stehen — Fallback statt Absturz."""
    activities = [slot["activity"] for slot in day.get("time_slots", []) if slot.get("activity")]
    if not activities:
        return

    n_people = request.get("number_of_people", 1)
    prompt = prompts.fill(
        prompts.ESTIMATE_COSTS,
        destination=request.get("destination", ""),
        activities=_build_activities_text(activities),
    )

    raw = llm.call("cost_estimation_agent", prompt, prompt_id="ESTIMATE_COSTS", max_tokens=600)
    cost_by_id = _parse_cost_response(raw)

    if not cost_by_id:
        llm.log_step("cost_estimation_agent", "Keine gültige Antwort — Pauschalpreise bleiben bestehen")
        return

    for activity in activities:
        cost_per_person = cost_by_id.get(activity["id"])
        if cost_per_person is None:
            continue
        try:
            cost_per_person = float(cost_per_person)
        except (TypeError, ValueError):
            continue
        if cost_per_person < 0:
            continue
        activity["estimated_cost_per_person"] = cost_per_person
        activity["estimated_cost_total"] = round(cost_per_person * n_people, 2)


def estimate_costs_for_plan(days: list, request: dict) -> None:
    for day in days:
        estimate_costs_for_day(day, request)


def get_agent_insight() -> dict:
    return {
        "agent_name": "cost_estimation_agent",
        "display_label": "Kostenschätzungs Agent",
        "status": "completed",
        "summary": "Individuelle Kostenschätzung pro Aktivität durchgeführt (ohne Websuche, aus LLM-Wissen).",
    }
