import json
from datetime import date, timedelta

import llm
import prompts
from providers.calendar import get_calendar_events


def _build_day_lines(events, days_ahead):
    """Baut für jeden Tag im Zeitraum eine Zeile — auch für Tage ohne Termin."""
    today = date.today()
    all_days = [(today + timedelta(days=i)).isoformat() for i in range(1, days_ahead + 1)]

    events_by_day = {}
    for e in events:
        events_by_day.setdefault(e["start"], []).append(e.get("summary") or "Termin")

    lines = []
    for d in all_days:
        day_events = events_by_day.get(d, [])
        if day_events:
            lines.append(f"- {d}: {', '.join(day_events)}")
        else:
            lines.append(f"- {d}: kein Termin")
    return all_days, events_by_day, lines


def interpret_calendar(events, days_ahead=14):
    """
    Lässt das LLM jeden Tag im Zeitraum als free/busy einstufen.
    Tage ohne Termin werden ebenfalls bewertet (= frei).
    Bei LLM-Fehler: einfacher Fallback (Tag mit Termin = belegt, sonst frei).
    """
    all_days, events_by_day, lines = _build_day_lines(events, days_ahead)
    events_text = "\n".join(lines)

    raw = llm.call(
        "calendar_agent",
        prompts.fill(prompts.INTERPRET_CALENDAR, events_text=events_text),
        prompt_id="INTERPRET_CALENDAR",
        max_tokens=1200,
    )

    if raw:
        result = _parse_calendar_response(raw)
        if result is not None:
            llm.log_step("calendar_agent", f"{len(result)} Tage interpretiert")
            return result

    # Fallback: Tag mit Termin = belegt, sonst frei
    llm.log_step("calendar_agent", "Fallback (LLM nicht verfügbar)")
    result = []
    for d in all_days:
        if events_by_day.get(d):
            result.append({"date": d, "status": "busy", "reason": "Termin im Kalender"})
        else:
            result.append({"date": d, "status": "free", "reason": "Kein Termin"})
    return result


def _parse_calendar_response(raw):
    try:
        data = json.loads(raw.strip())
        days = data if isinstance(data, list) else data.get("days", [])
        result = []
        for item in days:
            if not isinstance(item, dict):
                continue
            day_date = item.get("date", "")
            status = item.get("status", "")
            if day_date and status in ("free", "busy"):
                result.append({
                    "date": day_date,
                    "status": status,
                    "reason": item.get("reason", ""),
                })
        return result if result else None
    except Exception:
        return None


def get_truly_free_days(days_ahead=14):
    """
    Liest den Kalender, lässt das LLM interpretieren,
    gibt nur vollständig freie Tage zurück.
    """
    events = get_calendar_events(days_ahead=days_ahead)
    interpreted = interpret_calendar(events, days_ahead=days_ahead)
    return [d["date"] for d in interpreted if d["status"] == "free"]
