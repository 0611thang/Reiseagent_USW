import json
import re

import llm
import prompts

ALLOWED_CATEGORIES = {"culture", "food", "nature", "sightseeing", "shopping"}

# Einfache Keyword-Listen fuer den Regex-Fallback (ohne LLM).
CATEGORY_KEYWORDS = {
    "culture": ["museen", "museum", "kunst", "kultur", "architektur", "historisch", "gebäude", "gebaeude"],
    "food": ["essen", "café", "cafe", "restaurant", "kulinarisch"],
    "nature": ["natur", "park", "see", "spazier", "garten"],
    "sightseeing": [
        "sehenswürdigkeit", "sehenswuerdigkeit", "sehenswürdigkeiten", "sehenswuerdigkeiten",
        "aussicht", "stadtführung", "stadtfuehrung", "wahrzeichen",
    ],
    "shopping": ["shopping", "markt", "laden", "läden", "laeden", "einkauf"],
}

# Erkennt eine Bewertung wie "5/5", "5 von 5", "3 Sterne", "4 Punkte".
_RATING_PATTERN = re.compile(
    r"(?P<rating>[1-5])\s*(?:/\s*5|von\s*5|sterne|stern|punkte)",
    re.IGNORECASE,
)


def _detect_category(window_lower: str):
    """Gibt die Kategorie zurueck, wenn GENAU eine im Textabschnitt vorkommt.
    Bei keiner oder mehreren Treffern: None (keine Kategorie raten).

    Nutzt Wortgrenzen (\\b) statt reinem Teilstring-Vergleich, sonst wuerde
    z.B. "see" (nature) faelschlich in "museen" (culture) gefunden werden.
    """
    found = set()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if re.search(r"\b" + re.escape(kw) + r"\b", window_lower):
                found.add(category)
                break
    if len(found) == 1:
        return next(iter(found))
    return None


def _fallback_extract_feedback(text: str) -> list:
    """
    Regex-Fallback ohne LLM: sucht jede Bewertung (z.B. "5/5", "3 Sterne") im
    Text und prueft den Textabschnitt davor auf genau eine Kategorie.

    Wird weder eine Bewertung noch eine eindeutige Kategorie gefunden, wird
    der Abschnitt einfach uebersprungen (keine erfundenen Kategorien).
    """
    if not text:
        return []

    matches = list(_RATING_PATTERN.finditer(text))
    if not matches:
        return []

    items = []
    prev_end = 0
    for match in matches:
        window = text[prev_end:match.end()]
        relative_start = match.start() - prev_end
        comment = window[:relative_start].strip(" ,.!?;:\n\t-")
        category = _detect_category(window.lower())
        prev_end = match.end()

        if not category:
            continue

        try:
            rating = int(match.group("rating"))
        except (TypeError, ValueError):
            continue
        rating = max(1, min(rating, 5))

        items.append({"category": category, "rating": rating, "comment": comment})

    return items


def _parse_llm_response(raw):
    """
    Erwartet {"feedback": [{"category": ..., "rating": ..., "comment": ...}, ...]}.
    Gibt None zurueck, wenn die Antwort nicht sauber geparst werden kann
    (dann greift der Regex-Fallback). Eine gueltig geparste, aber LEERE Liste
    ist ein legitimes Ergebnis (keine klare Bewertung erkannt) und wird NICHT
    als Fehler behandelt.
    """
    if not raw:
        return None
    try:
        data = json.loads(raw.strip())
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    items = data.get("feedback")
    if not isinstance(items, list):
        return None

    validated = []
    for item in items:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category", "")).strip().lower()
        if category not in ALLOWED_CATEGORIES:
            continue  # unbekannte Kategorien ignorieren, nichts erfinden

        try:
            rating = int(item.get("rating"))
        except (TypeError, ValueError):
            continue
        rating = max(1, min(rating, 5))

        comment = item.get("comment") or ""
        validated.append({"category": category, "rating": rating, "comment": comment})

    return validated


def interpret_feedback(trip: dict, text: str) -> list:
    """
    Erkennt aus einer Telegram-Freitextantwort strukturiertes Reise-Feedback
    (Kategorie + Bewertung + kurzer Kommentar) fuer eine beendete Reise.

    `trip` ist fuer spaetere Erweiterungen (z.B. Reiseziel-Kontext) vorgesehen,
    wird fuer die Erkennung selbst aktuell nicht zwingend benoetigt.

    Nutzt zuerst die bestehende Projekt-LLM-Infrastruktur (llm.call, Groq).
    Ist kein GROQ_API_KEY gesetzt oder die Antwort nicht sauber als JSON
    parsebar, greift ein einfacher Regex-Fallback (Keyword + Bewertungsmuster).
    Wirft nie eine Exception nach aussen. Bei unklarer Antwort: [].
    """
    if not text or not text.strip():
        return []

    parsed = None
    try:
        prompt = prompts.fill(prompts.INTERPRET_TRIP_FEEDBACK, text=text.strip())
        raw = llm.call("feedback_agent", prompt, prompt_id="INTERPRET_TRIP_FEEDBACK", max_tokens=400)
        parsed = _parse_llm_response(raw)
    except Exception:
        parsed = None

    if parsed is None:
        parsed = _fallback_extract_feedback(text)

    return parsed


def get_agent_insight() -> dict:
    return {
        "agent_name": "feedback_agent",
        "display_label": "Feedback Agent",
        "status": "completed",
        "summary": "Reise-Feedback interpretiert und gespeichert.",
    }
