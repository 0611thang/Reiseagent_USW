def calculate_budget(days: list, request: dict) -> dict:
    budget_total = request.get("budget_total", 0.0)
    currency = request.get("currency", "EUR")
    n_people = request.get("number_of_people", 1)

    category_totals: dict[str, float] = {}
    planned_total = 0.0

    for day in days:
        for slot in day.get("time_slots", []):
            activity = slot.get("activity", {})
            cost = activity.get("estimated_cost_total", 0.0)
            category = activity.get("category", "other")
            category_totals[category] = category_totals.get(category, 0.0) + cost
            planned_total += cost

    categories = []
    for cat, amount in category_totals.items():
        pct = (amount / planned_total * 100) if planned_total > 0 else 0.0
        categories.append({"category": cat, "amount": round(amount, 2), "percentage": round(pct, 1)})

    categories.sort(key=lambda x: x["amount"], reverse=True)

    remaining = budget_total - planned_total
    ratio = planned_total / budget_total if budget_total > 0 else 0.0

    if ratio >= 1.0:
        status = "over_budget"
    elif ratio >= 0.9:
        status = "near_limit"
    else:
        status = "within_budget"

    return {
        "budget_total": round(budget_total, 2),
        "planned_total": round(planned_total, 2),
        "remaining": round(remaining, 2),
        "currency": currency,
        "per_person_total": round(planned_total / n_people, 2) if n_people > 0 else 0.0,
        "categories": categories,
        "status": status,
    }


def get_agent_insight() -> dict:
    return {
        "agent_name": "budget_agent",
        "display_label": "Budget Agent",
        "status": "completed",
        "summary": "Budget deterministisch berechnet – keine KI benötigt.",
    }
