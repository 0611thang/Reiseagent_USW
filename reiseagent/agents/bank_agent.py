import json
import re

import llm
import prompts
import profile_store
from providers.telegram import normalize_telegram_command_text

# Alleinstehende /bank /konto /budget Kommandos (mit Wortgrenze, damit
# "/bank_status" NICHT als "/bank" erkannt wird).
_BANK_COMMAND_PATTERN = re.compile(r"^/(bank|konto|budget)\b", re.IGNORECASE)

# "Reiserücklage: 50" oder "Reisebudget 250" -> Zahl direkt danach.
_RESERVE_KEYWORD_PATTERN = re.compile(
    r"reiser[uü]cklage[^\d]{0,10}(\d+(?:[.,]\d+)?)|reisebudget[^\d]{0,10}(\d+(?:[.,]\d+)?)",
    re.IGNORECASE,
)


def _strip_command_prefix(text: str) -> str:
    """Entfernt ein fuehrendes /bank /konto /budget, damit interpret_bank_checkin
    z.B. '/bank Einnahmen: 603, Fixkosten: 500' genauso liest wie ohne Kommando."""
    match = _BANK_COMMAND_PATTERN.match(text)
    if not match:
        return text
    return text[match.end():].strip(" :,-")


def is_bare_bank_command(text: str) -> bool:
    """
    True NUR bei einem alleinstehenden /bank, /konto oder /budget ohne weitere
    Daten danach (z.B. '/bank' oder '/bank ' oder '/bank!').
    Das oeffnet die gefuehrte Eingabe statt sofort zu speichern.

    Normalisiert vorher einen Telegram-Bot-Mention-Suffix (z.B. aus
    "/bank@USW_ReiseplanerBot" wird "/bank"), damit angeklickte Bot-Befehle
    in Gruppen korrekt als alleinstehendes Kommando erkannt werden.
    """
    if not text:
        return False
    stripped = normalize_telegram_command_text(text.strip())
    match = _BANK_COMMAND_PATTERN.match(stripped)
    if not match:
        return False
    remainder = stripped[match.end():].strip(" :,-!?.")
    return remainder == ""


def is_spontaneous_bank_message(text: str) -> bool:
    """
    Erkennt NUR eindeutige Bankkonto-Nachrichten fuer den Fall, dass gerade
    KEINE pending_prompt-Frage offen ist. Lieber zu vorsichtig als zu
    aggressiv: im Zweifel False, damit normale Chatnachrichten oder
    Reise-Feedback (z.B. "Essen 3/5", "Ich habe 500 Euro ausgegeben")
    niemals faelschlich als Bankkonto interpretiert werden.

    Normalisiert vorher einen Telegram-Bot-Mention-Suffix (siehe is_bare_bank_command).
    """
    if not text:
        return False
    stripped = normalize_telegram_command_text(text.strip())
    if not stripped:
        return False

    if _BANK_COMMAND_PATTERN.match(stripped):
        return True

    lower = stripped.lower()
    if "bankkonto" in lower:
        return True
    if "einnahmen" in lower and "fixkosten" in lower:
        return True
    if "einkommen" in lower and "fixkosten" in lower:
        return True
    if ("reiserücklage" in lower or "reiserucklage" in lower or "reisebudget" in lower) and (
        ("einnahmen" in lower and "fixkosten" in lower)
        or ("einkommen" in lower and "fixkosten" in lower)
    ):
        return True

    return False


def _parse_llm_response(raw):
    """Erwartet {"success": true/false, "income": ..., "fixed_costs": ..., "travel_reserve": ...}. Sonst None."""
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

    travel_reserve = data.get("travel_reserve")
    if travel_reserve is not None:
        try:
            travel_reserve = float(travel_reserve)
        except (TypeError, ValueError):
            travel_reserve = None
        if travel_reserve is not None and travel_reserve < 0:
            travel_reserve = None  # negative Ruecklage nicht erlauben -> 20%-Regel greift stattdessen

    return income, fixed_costs, travel_reserve


def _fallback_extract_numbers(text):
    """
    Regex-Fallback ohne LLM.
    - Erste Zahl = income, zweite Zahl = fixed_costs.
    - Reise-Ruecklage optional: entweder ueber "Reiserücklage"/"Reisebudget" + Zahl
      erkannt, oder als dritte Zahl im Text (income, fixed_costs, travel_reserve).
    Weniger als zwei Zahlen im Text -> None (unklare Antwort beim Aufrufer).
    """
    if not text:
        return None

    reserve_match = _RESERVE_KEYWORD_PATTERN.search(text)
    reserve_value = None
    if reserve_match:
        raw_reserve = reserve_match.group(1) or reserve_match.group(2)
        try:
            reserve_value = float(raw_reserve.replace(",", "."))
        except ValueError:
            reserve_value = None

    numbers = re.findall(r"\d+(?:[.,]\d+)?", text)
    if len(numbers) < 2:
        return None

    try:
        income = float(numbers[0].replace(",", "."))
        fixed_costs = float(numbers[1].replace(",", "."))
    except ValueError:
        return None

    if reserve_value is None and len(numbers) >= 3:
        try:
            reserve_value = float(numbers[2].replace(",", "."))
        except ValueError:
            reserve_value = None

    if reserve_value is not None and reserve_value < 0:
        reserve_value = None  # negative Ruecklage nicht erlauben

    return income, fixed_costs, reserve_value


def _build_success_result(income, fixed_costs, travel_reserve=None):
    free_amount = income - fixed_costs
    if travel_reserve is None:
        travel_reserve = max(free_amount * 0.2, 0)
    # Reise-Ruecklage darf bewusst groesser als der freie Betrag sein (simuliertes Demo-Konto).
    return {
        "success": True,
        "income": income,
        "fixed_costs": fixed_costs,
        "free_amount": round(free_amount, 2),
        "travel_reserve": round(travel_reserve, 2),
        "message": (
            f"Freier Betrag: {free_amount:.0f} €, "
            f"Reise-Rücklage: {travel_reserve:.0f} €."
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
    Erkennt aus einer Telegram-Freitextantwort Einkommen, Fixkosten und
    optional eine manuelle Reise-Ruecklage fuer den Bankkonto-Check-in.

    Nutzt zuerst die bestehende Projekt-LLM-Infrastruktur (llm.call, Groq).
    Ist kein GROQ_API_KEY gesetzt oder die Antwort nicht sauber als JSON
    parsebar, greift ein einfacher Regex-Fallback (erste Zahl = income,
    zweite Zahl = fixed_costs, optionale dritte Zahl/Schluesselwort = travel_reserve).
    Ein fuehrendes /bank /konto /budget (auch mit Telegram-Bot-Mention wie
    "/bank@USW_ReiseplanerBot") wird vor der Erkennung entfernt.
    Wirft nie eine Exception nach aussen.
    """
    if not text or not text.strip():
        return _empty_result()

    text = _strip_command_prefix(normalize_telegram_command_text(text.strip()))
    if not text:
        return _empty_result()

    parsed = None
    try:
        prompt = prompts.fill(prompts.INTERPRET_BANK_CHECKIN, text=text)
        raw = llm.call("bank_agent", prompt, prompt_id="INTERPRET_BANK_CHECKIN", max_tokens=200)
        parsed = _parse_llm_response(raw)
    except Exception:
        parsed = None

    if parsed is None:
        parsed = _fallback_extract_numbers(text)

    if parsed is None:
        return _empty_result()

    income, fixed_costs, travel_reserve = parsed
    return _build_success_result(income, fixed_costs, travel_reserve)


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
