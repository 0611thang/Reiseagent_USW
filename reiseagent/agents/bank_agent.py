import json
import re

import llm
import prompts
import profile_store


def _parse_llm_response(raw):
    """Erwartet {"success": true/false, "income": ..., "fixed_costs": ...}. Sonst None."""
    if not raw:
        return None
    try:
        data = json.loads(raw.strip())
    except Exception:
        return None

    if not isinstance(data, dict) or not data.get("success"):
        return None

    try:
        income = float(data.get("income"))
        fixed_costs = float(data.get("fixed_costs"))
    except (TypeError, ValueError):
        return None

    if income < 0 or fixed_costs < 0:
        return None

    return income, fixed_costs


def _fallback_extract_numbers(text):
    """
    Regex-Fallback ohne LLM: erste gefundene Zahl = income, zweite = fixed_costs.
    Weniger als zwei Zahlen im Text -> None (success=False beim Aufrufer).
    """
    numbers = re.findall(r"\d+(?:[.,]\d+)?", text or "")
    if len(numbers) < 2:
        return None

    try:
        income = float(numbers[0].replace(",", "."))
        fixed_costs = float(numbers[1].replace(",", "."))
    except ValueError:
        return None

    return income, fixed_costs


def _build_success_result(income, fixed_costs):
    free_amount = income - fixed_costs
    travel_reserve = max(free_amount * 0.2, 0)
    return {
        "success": True,
        "income": income,
        "fixed_costs": fixed_costs,
        "free_amount": round(free_amount, 2),
        "travel_reserve": round(travel_reserve, 2),
        "message": (
            f"Freier Betrag: {free_amount:.0f} €, "
            f"vorgeschlagene Reise-Rücklage: {travel_reserve:.0f} €."
        ),
    }


def _empty_result(message="Ich konnte die Zahlen nicht eindeutig erkennen."):
    return {
        "success": False,
        "income": None,
        "fixed_costs": None,
        "free_amount": None,
        "travel_reserve": None,
        "message": message,
    }


def interpret_bank_checkin(text: str) -> dict:
    """
    Erkennt aus einer Telegram-Freitextantwort Einkommen und Fixkosten fuer
    den monatlichen Bankkonto-Check-in.

    Nutzt zuerst die bestehende Projekt-LLM-Infrastruktur (llm.call, Groq).
    Ist kein GROQ_API_KEY gesetzt oder die Antwort nicht sauber als JSON
    parsebar, greift ein einfacher Regex-Fallback (erste Zahl = income,
    zweite Zahl = fixed_costs). Wirft nie eine Exception nach aussen.
    """
    if not text or not text.strip():
        return _empty_result()

    parsed = None
    try:
        prompt = prompts.fill(prompts.INTERPRET_BANK_CHECKIN, text=text.strip())
        raw = llm.call("bank_agent", prompt, prompt_id="INTERPRET_BANK_CHECKIN", max_tokens=200)
        parsed = _parse_llm_response(raw)
    except Exception:
        parsed = None

    if parsed is None:
        parsed = _fallback_extract_numbers(text)

    if parsed is None:
        return _empty_result()

    income, fixed_costs = parsed
    return _build_success_result(income, fixed_costs)


def maybe_deduct_trip_cost(trip_id, plan, reason="trip"):
    """
    Bucht die geschaetzten Reisekosten vom simulierten Bankkonto ab, falls ein
    sinnvoller Gesamtpreis vorhanden ist.

    Der Betrag kommt aus plan["budget_summary"]["planned_total"] - das ist im
    Projekt das einzige Feld mit dem tatsaechlich geplanten Gesamtpreis eines
    Reiseplans (gesetzt von agents/budget.py:calculate_budget, aufgerufen aus
    agents/coordinator.py:handle_plan_request und agents/replanning.py).

    Fehlt trip_id, plan oder das Feld, wird NICHT geraten - es passiert
    einfach nichts (kein Crash, kein Fehler nach aussen).
    """
    if not trip_id or not plan:
        return None

    budget_summary = plan.get("budget_summary") or {}
    amount = budget_summary.get("planned_total")
    if amount is None:
        return None

    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return None

    try:
        return profile_store.deduct_trip_cost(trip_id, amount, reason=reason)
    except Exception:
        return None


def get_agent_insight() -> dict:
    return {
        "agent_name": "bank_agent",
        "display_label": "Bankkonto Agent",
        "status": "completed",
        "summary": "Monatlicher Bankkonto-Check-in verarbeitet.",
    }
