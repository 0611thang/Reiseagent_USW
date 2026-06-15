import os
import re
import unicodedata
import uuid
from datetime import datetime

from providers.weather import get_weather_for_trip
import providers.places as places_provider
from agents import planning, budget, checklist, recommendation, replanning


def handle_plan_request(request: dict, use_mock_weather: bool = False) -> dict:
    insights = []

    insights.append({
        "agent_name": "coordinator",
        "display_label": "Coordinator Agent",
        "status": "running",
        "summary": "Anfrage analysiert, Agenten werden koordiniert...",
    })

    weather = get_weather_for_trip(request, use_mock=use_mock_weather)
    insights.append({
        "agent_name": "weather_agent",
        "display_label": "Wetter Agent",
        "status": "completed",
        "summary": f"Wetterdaten für {request['destination']} ({len(weather)} Tage) geladen.",
    })

    all_activities = places_provider.get_places(request["destination"], request.get("interests", []))
    insights.append({
        "agent_name": "places_agent",
        "display_label": "POI Agent",
        "status": "completed",
        "summary": (
            f"{len(all_activities)} Aktivitäten für {request['destination']} geladen. "
            f"{places_provider.LAST_PLACES_STATUS}"
        ),
    })

    days = planning.create_plan(request, all_activities, weather)
    insights.append(planning.get_agent_insight(len(days)))

    total_activities = sum(len(d["time_slots"]) for d in days)
    insights.append(recommendation.get_agent_insight(total_activities))

    budget_summary = budget.calculate_budget(days, request)
    insights.append(budget.get_agent_insight())

    plan_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    active_plan = {
        "id": plan_id,
        "request": request,
        "days": days,
        "budget_summary": budget_summary,
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }

    trip_id_placeholder = str(uuid.uuid4())
    checklist_data = checklist.create_checklist(trip_id_placeholder, request, weather)
    insights.append(checklist.get_agent_insight())

    insights[0]["status"] = "completed"
    insights[0]["summary"] = "Alle Agenten erfolgreich koordiniert."

    return {
        "active_plan": active_plan,
        "checklist": checklist_data,
        "agent_insights": insights,
        "weather": weather,
        "all_activities": all_activities,
    }


def handle_chat_message(trip: dict, message: str) -> dict:
    plan_change = _try_apply_plan_change(trip, message)
    if plan_change:
        return plan_change

    api_key = os.getenv("GROQ_API_KEY", "")
    if api_key:
        return _groq_response(trip, message, api_key)
    return _rule_based_response(trip, message)


def _try_apply_plan_change(trip: dict, message: str) -> dict | None:
    text = _plain_text(message)
    active_plan = trip.get("active_plan")
    if not active_plan:
        return None

    change_words = [
        "hinzufuegen", "hinzufugen", "fuege", "fuge", "einsetzen", "setze",
        "ersetze", "austauschen", "tausch", "fuelle", "fulle", "vervollstaendige",
        "vervollstandige", "plan auffuellen", "plan auffullen", "vorschlag",
        "nehme", "nehmen", "nimm",
    ]
    if not any(word in text for word in change_words):
        return None

    if any(word in text for word in ["fuelle", "fulle", "vervollstaendige", "vervollstandige", "plan auffuellen", "plan auffullen"]):
        return _fill_plan_from_chat(trip, message)

    if any(word in text for word in ["ersetze", "austauschen", "tausch", "vorschlag", "nehme", "nehmen", "nimm"]):
        return _replace_activity_from_chat(trip, message)

    return _add_activity_from_chat(trip, message)


def _plain_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return (
        ascii_text
        .replace("ae", "ae")
        .replace("oe", "oe")
        .replace("ue", "ue")
        .replace("Ã¼", "ue")
        .replace("Ã¤", "ae")
        .replace("Ã¶", "oe")
    )


def _get_day_number(message: str, fallback: int = 1) -> int:
    match = re.search(r"tag\s*(\d+)", message.lower())
    if match:
        return int(match.group(1))
    return fallback


def _extract_day_number(message: str) -> int | None:
    match = re.search(r"tag\s*(\d+)", message.lower())
    if match:
        return int(match.group(1))
    return None


def _find_day(active_plan: dict, day_number: int) -> dict | None:
    for day in active_plan.get("days", []):
        if day.get("day_number") == day_number:
            return day
    return None


def _get_used_activity_names(active_plan: dict) -> set:
    used = set()
    for day in active_plan.get("days", []):
        for slot in day.get("time_slots", []):
            used.add(slot["activity"]["name"].lower())
    return used


def _available_activities(trip: dict) -> list:
    request = trip.get("request", {})
    destination = request.get("destination", "")
    interests = request.get("interests", [])
    activities = places_provider.get_places(destination, interests)
    used_names = _get_used_activity_names(trip["active_plan"])
    return [a for a in activities if a["name"].lower() not in used_names]


def _category_from_text(message: str) -> str | None:
    text = _plain_text(message)
    if "shopping" in text or "laden" in text or "markt" in text:
        return "shopping"
    if "restaurant" in text or "essen" in text:
        return "restaurant"
    if "museum" in text or "museen" in text:
        return "museum"
    if "spaziergang" in text or "park" in text or "natur" in text:
        return "walk"
    if "sehenswuerdigkeit" in text or "sightseeing" in text:
        return "sightseeing"
    return None


def _activity_matches_category(activity: dict, category: str) -> bool:
    if activity.get("category") == category:
        return True
    if category in ["restaurant", "museum"]:
        return False
    tags = [_plain_text(t) for t in activity.get("tags", [])]
    if category == "walk":
        return "spaziergaenge" in tags or "natur" in tags
    return category in tags


def _find_replacement_activity(trip: dict, message: str, category: str | None) -> dict | None:
    activities = _available_activities(trip)
    suggestion_activity = _activity_from_previous_chat_suggestion(trip, message, category)
    if suggestion_activity:
        return suggestion_activity

    replacement_text = ""
    match = re.search(r"(?:durch|mit)\s+(.+?)(?:\s+an\s+tag\s+\d+|\s+tag\s+\d+|$)", message, re.IGNORECASE)
    if match:
        replacement_text = match.group(1).strip()

    generic_words = [
        "einem anderen", "einen anderen", "anderes", "anderem", "andere",
        "spezifischen", "passenden", "neuen", "restaurant", "museum",
        "aktivitaet", "aktivität", "vorschlag",
    ]
    is_generic = _is_generic_replacement_text(replacement_text)

    if replacement_text and not is_generic:
        text = replacement_text.lower()
        for activity in activities:
            if activity["name"].lower() in text or text in activity["name"].lower():
                return activity
        return _custom_activity(trip, replacement_text, category=category or "activity")

    if not activities:
        return None

    if category:
        for activity in activities:
            if _activity_matches_category(activity, category):
                return activity
        return _custom_activity(trip, _generic_name_for_category(category), category=category)

    return activities[0]


def _is_generic_replacement_text(replacement_text: str) -> bool:
    text = _plain_text(replacement_text).strip()
    if not text:
        return True

    generic_category_words = ["restaurant", "museum", "aktivitaet", "aktivitat"]
    filler_words = {
        "der", "die", "das", "dem", "den", "ein", "eine", "einem", "einen",
        "anderer", "andere", "anderes", "anderen", "anderem", "passenden",
        "neuen", "spezifischen", "restaurant", "museum", "aktivitaet",
        "aktivitat", "vorschlag",
    }
    meaningful_words = [word for word in text.split() if word not in filler_words]
    if meaningful_words:
        return False

    if text in generic_category_words:
        return True
    generic_phrases = [
        "einem anderen", "einen anderen", "ein anderes", "anderes",
        "passenden", "neuen", "spezifischen", "vorschlag",
    ]
    return any(phrase in text for phrase in generic_phrases)


def _activity_from_previous_chat_suggestion(trip: dict, message: str, category: str | None) -> dict | None:
    wanted_number = _requested_suggestion_number(message)
    if not wanted_number:
        return None

    suggestions = _extract_last_assistant_suggestions(trip)
    if wanted_number < 1 or wanted_number > len(suggestions):
        return None

    name = suggestions[wanted_number - 1]
    activities = _available_activities(trip)
    for activity in activities:
        activity_name = _plain_text(activity["name"])
        wanted_name = _plain_text(name)
        if activity_name == wanted_name or wanted_name in activity_name or activity_name in wanted_name:
            return activity

    return _custom_activity(trip, name, category=category or "activity")


def _requested_suggestion_number(message: str) -> int | None:
    text = _plain_text(message)
    match = re.search(r"(\d+)\.?\s*(vorschlag|option|alternative)", text)
    if match:
        return int(match.group(1))
    match = re.search(r"(ersten|erste|zweiten|zweite|dritten|dritte|vierten|vierte)\s*(vorschlag|option|alternative)", text)
    if not match:
        return None
    words = {
        "ersten": 1,
        "erste": 1,
        "zweiten": 2,
        "zweite": 2,
        "dritten": 3,
        "dritte": 3,
        "vierten": 4,
        "vierte": 4,
    }
    return words.get(match.group(1))


def _extract_last_assistant_suggestions(trip: dict) -> list[str]:
    messages = trip.get("chat_messages", [])
    for msg in reversed(messages):
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", "")
        suggestions = []
        for line in content.splitlines():
            raw = line.strip()
            if not re.match(r"^(\d+[\.)]\s+|[-*•]\s+)", raw):
                continue
            cleaned = re.sub(r"^[-*•]\s*", "", raw)
            cleaned = re.sub(r"^\d+[\.)]\s*", "", cleaned)
            cleaned = cleaned.strip(" -:;")
            if not cleaned:
                continue
            if len(cleaned) > 80:
                cleaned = cleaned.split(":")[0].strip()
            if len(cleaned) >= 3:
                suggestions.append(cleaned)
        if suggestions:
            return suggestions[:5]
    return []


def _generic_name_for_category(category: str) -> str:
    names = {
        "restaurant": "Anderes Restaurant",
        "museum": "Anderes Museum",
        "shopping": "Shopping-Alternative",
        "walk": "Alternativer Spaziergang",
        "sightseeing": "Alternative Sehenswuerdigkeit",
    }
    return names.get(category, "Alternative Aktivitaet")


def _find_target_slot(active_plan: dict, message: str, category: str | None):
    day_number = _extract_day_number(message)
    days = active_plan.get("days", [])
    if day_number:
        days = [d for d in days if d.get("day_number") == day_number]

    target_match = re.search(r"ersetze\s+(.+?)(?:\s+durch|\s+mit|$)", message, re.IGNORECASE)
    if target_match:
        wanted = _plain_text(target_match.group(1).strip())
        wanted = re.sub(r"^an\s+tag\s+\d+\s+", "", wanted).strip()
        wanted = re.sub(r"^bitte\s+", "", wanted).strip()
        if wanted and wanted not in ["es", "das", "ihn", "sie"]:
            for day in days:
                for slot in day.get("time_slots", []):
                    name = _plain_text(slot["activity"]["name"])
                    if wanted in name or name in wanted:
                        return day, slot
            return None, None

    if category:
        for day in days:
            for slot in day.get("time_slots", []):
                if _activity_matches_category(slot["activity"], category):
                    return day, slot

    for day in days:
        slots = day.get("time_slots", [])
        if slots:
            return day, slots[-1]

    return None, None


def _activity_from_text_or_pool(trip: dict, message: str) -> dict | None:
    cleaned = re.sub(r".*(hinzufuegen|hinzufügen|hinzufugen|fuege|füge|fuge|einsetzen|setze|plane)\s*", "", message, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*(an|auf|in)?\s*tag\s*\d+.*", "", cleaned, flags=re.IGNORECASE).strip()
    if cleaned and len(cleaned) >= 3:
        return _custom_activity(trip, cleaned)

    activities = _available_activities(trip)
    if not activities:
        return None

    text = message.lower()
    for activity in activities:
        if activity["name"].lower() in text:
            return activity

    return activities[0]


def _custom_activity(trip: dict, name: str, category: str = "activity") -> dict:
    destination = trip.get("request", {}).get("destination", "")
    display_name = _clean_custom_activity_name(name)
    cost = 0.0
    indoor_outdoor = "mixed"
    tags = ["chat", "nutzerwunsch"]
    if category == "restaurant":
        cost = 20.0
        indoor_outdoor = "indoor"
        tags += ["gutes essen", "restaurant"]
    elif category == "museum":
        cost = 12.0
        indoor_outdoor = "indoor"
        tags += ["museen", "rain_safe"]

    return {
        "id": f"chat-{uuid.uuid4()}",
        "name": display_name,
        "category": category,
        "description": f"Vom Nutzer per Chat fuer {destination} hinzugefuegt.",
        "location": {"name": display_name, "area": destination, "lat": None, "lng": None},
        "estimated_cost_per_person": cost,
        "duration_minutes": 90,
        "indoor_outdoor": indoor_outdoor,
        "tags": tags,
        "reasoning": "Direkter Nutzerwunsch aus dem Chat.",
        "source": "chat",
    }


def _clean_custom_activity_name(name: str) -> str:
    cleaned = name.strip(" .,:;")
    cleaned = re.sub(r"^ein\s+besuch\s+(des|der|dem|den)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(der|die|das|dem|den|ein|eine|einem|einen)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+fuer\s+.+$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+für\s+.+$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+oder\s+(des|der|dem|den)?\s*", " und ", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("Kurfuerstendamms", "Kurfuerstendamm")
    cleaned = cleaned.replace("Kurfürstendamms", "Kurfürstendamm")
    cleaned = cleaned.replace("Friedrichshains", "Friedrichshain")
    if not cleaned:
        return "Alternative Aktivitaet"
    return cleaned[:1].upper() + cleaned[1:]


def _next_slot_times(day: dict) -> tuple[str, str]:
    slot_times = [
        ("09:00", "11:30"),
        ("12:00", "13:30"),
        ("14:00", "16:30"),
        ("17:00", "19:00"),
        ("19:30", "21:30"),
    ]
    index = len(day.get("time_slots", []))
    if index < len(slot_times):
        return slot_times[index]
    return ("20:00", "21:30")


def _prepare_activity_for_plan(activity: dict, trip: dict) -> dict:
    prepared = dict(activity)
    people = trip.get("request", {}).get("number_of_people", 1)
    prepared["estimated_cost_total"] = prepared.get("estimated_cost_per_person", 0.0) * people
    prepared.setdefault("score", {
        "activity_id": prepared["id"],
        "overall_score": 0.75,
        "explanation": "direkter Nutzerwunsch",
    })
    return prepared


def _add_activity_to_day(trip: dict, day: dict, activity: dict):
    start, end = _next_slot_times(day)
    day.setdefault("time_slots", []).append({
        "id": str(uuid.uuid4()),
        "start_time": start,
        "end_time": end,
        "activity": _prepare_activity_for_plan(activity, trip),
        "notes": "Per Chat hinzugefuegt",
    })


def _refresh_plan_after_change(trip: dict):
    active_plan = trip["active_plan"]
    active_plan["budget_summary"] = budget.calculate_budget(active_plan["days"], trip["request"])
    active_plan["updated_at"] = datetime.now().isoformat()
    trip["agent_insights"].append({
        "agent_name": "chat_planning_agent",
        "display_label": "Chat Planungs Agent",
        "status": "completed",
        "summary": "Aktiver Plan wurde durch Chat-Befehl angepasst.",
    })


def _fill_plan_from_chat(trip: dict, message: str) -> dict:
    active_plan = trip["active_plan"]
    day_number = _get_day_number(message, fallback=0)
    days = active_plan.get("days", [])
    target_days = days if day_number == 0 else [_find_day(active_plan, day_number)]
    target_days = [d for d in target_days if d]

    if not target_days:
        return _chat_change_reply("Ich konnte den genannten Tag im Plan nicht finden.", False)

    added = []
    for day in target_days:
        while len(day.get("time_slots", [])) < 4:
            activities = _available_activities(trip)
            if not activities:
                break
            activity = activities[0]
            _add_activity_to_day(trip, day, activity)
            added.append(f"Tag {day['day_number']}: {activity['name']}")

    if not added:
        return _chat_change_reply("Ich habe keine passenden freien Aktivitaeten zum Auffuellen gefunden.", False)

    _refresh_plan_after_change(trip)
    return _chat_change_reply("Ich habe den Plan aufgefuellt:\n- " + "\n- ".join(added), True)


def _add_activity_from_chat(trip: dict, message: str) -> dict:
    active_plan = trip["active_plan"]
    day_number = _get_day_number(message)
    day = _find_day(active_plan, day_number)
    if not day:
        return _chat_change_reply(f"Ich konnte Tag {day_number} im Plan nicht finden.", False)

    activity = _activity_from_text_or_pool(trip, message)
    if not activity:
        return _chat_change_reply("Ich habe keine passende Aktivitaet zum Hinzufuegen gefunden.", False)

    _add_activity_to_day(trip, day, activity)
    _refresh_plan_after_change(trip)
    return _chat_change_reply(f"Erledigt: Ich habe '{activity['name']}' an Tag {day_number} hinzugefuegt.", True)


def _replace_activity_from_chat(trip: dict, message: str) -> dict:
    active_plan = trip["active_plan"]
    category = _category_from_text(message)
    if not category:
        category = _category_from_previous_chat_context(trip)
    day, target_slot = _find_target_slot(active_plan, message, category)
    if not day or not target_slot:
        return _chat_change_reply("Ich konnte keine passende Aktivitaet im Plan finden, die ich ersetzen kann.", False)

    replacement = _find_replacement_activity(trip, message, category)
    if not replacement:
        return _chat_change_reply("Ich habe keine Ersatzaktivitaet gefunden.", False)

    old_name = target_slot["activity"]["name"]
    if _plan_contains_activity(active_plan, replacement["name"], except_slot=target_slot):
        return _chat_change_reply(f"'{replacement['name']}' ist bereits im Plan. Ich habe nichts doppelt eingefuegt.", False)
    if _plain_text(old_name) == _plain_text(replacement["name"]):
        return _chat_change_reply(f"'{replacement['name']}' ist bereits im Plan. Ich habe nichts doppelt eingefuegt.", False)

    target_slot["activity"] = _prepare_activity_for_plan(replacement, trip)
    target_slot["notes"] = "Per Chat ersetzt"
    _refresh_plan_after_change(trip)
    return _chat_change_reply(f"Erledigt: Ich habe an Tag {day['day_number']} '{old_name}' durch '{replacement['name']}' ersetzt.", True)


def _plan_contains_activity(active_plan: dict, activity_name: str, except_slot: dict | None = None) -> bool:
    wanted = _plain_text(activity_name)
    for day in active_plan.get("days", []):
        for slot in day.get("time_slots", []):
            if except_slot is not None and slot is except_slot:
                continue
            if _plain_text(slot["activity"]["name"]) == wanted:
                return True
    return False


def _category_from_previous_chat_context(trip: dict) -> str | None:
    messages = trip.get("chat_messages", [])
    for msg in reversed(messages):
        if msg.get("role") != "assistant":
            continue
        return _category_from_text(msg.get("content", ""))
    return None


def _chat_change_reply(message: str, changed: bool) -> dict:
    status = "completed" if changed else "failed"
    return {
        "message": message,
        "agent_insights": [{
            "agent_name": "chat_planning_agent",
            "display_label": "Chat Planungs Agent",
            "status": status,
            "summary": "Chat-Befehl zur Plananpassung verarbeitet.",
        }],
    }


def _groq_response(trip: dict, message: str, api_key: str) -> dict:
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        trip_summary = _create_trip_summary(trip)

        prompt = (
            f"Du bist ein freundlicher Reiseassistent. Hier ist der aktuelle Reiseplan:\n"
            f"{trip_summary}\n\n"
            f"Nutzerfrage: {message}\n\n"
            f"Antworte auf Deutsch, kurz und hilfreich."
        )
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        return {
            "message": response.choices[0].message.content,
            "agent_insights": [{
                "agent_name": "coordinator",
                "display_label": "Coordinator Agent",
                "status": "completed",
                "summary": "Chat-Antwort via Groq API generiert.",
            }],
        }
    except Exception:
        return _rule_based_response(trip, message)


def _rule_based_response(trip: dict, message: str) -> dict:
    msg_lower = message.lower()
    active_plan = trip.get("active_plan")

    if any(kw in msg_lower for kw in ["budget", "kosten", "geld", "preis"]):
        bs = active_plan["budget_summary"] if active_plan else None
        if bs:
            reply = (
                f"Dein Budget: {bs['budget_total']} {bs['currency']}. "
                f"Geplant: {bs['planned_total']} {bs['currency']}. "
                f"Verbleibend: {bs['remaining']} {bs['currency']}. "
                f"Status: {bs['status'].replace('_', ' ')}."
            )
        else:
            reply = "Kein aktiver Plan gefunden."

    elif any(kw in msg_lower for kw in ["wetter", "regen", "sonne", "schnee"]):
        if active_plan:
            conditions = [
                f"Tag {d['day_number']}: {d['weather']['condition']}"
                for d in active_plan["days"]
                if d.get("weather")
            ]
            reply = "Wetterübersicht: " + ", ".join(conditions) if conditions else "Keine Wetterdaten verfügbar."
        else:
            reply = "Kein aktiver Plan gefunden."

    elif any(kw in msg_lower for kw in ["aktivität", "aktivitaet", "programm", "was machen", "highlights"]):
        if active_plan:
            day1 = active_plan["days"][0] if active_plan["days"] else None
            if day1:
                acts = [slot["activity"]["name"] for slot in day1.get("time_slots", [])]
                reply = f"Highlights an Tag 1: {', '.join(acts)}." if acts else "Keine Aktivitäten geplant."
            else:
                reply = "Plan ist leer."
        else:
            reply = "Kein aktiver Plan gefunden."

    elif any(kw in msg_lower for kw in ["tage", "wie lange", "dauer"]):
        req = trip.get("request", {})
        reply = f"Deine Reise geht {req.get('duration_days', '?')} Tage nach {req.get('destination', '?')}."

    else:
        dest = trip.get("request", {}).get("destination", "deinem Reiseziel")
        reply = (
            f"Ich helfe dir gerne mit deiner Reise nach {dest}! "
            f"Du kannst mich nach Budget, Wetter, Aktivitäten oder Reisetipps fragen."
        )

    return {
        "message": reply,
        "agent_insights": [{
            "agent_name": "coordinator",
            "display_label": "Coordinator Agent",
            "status": "completed",
            "summary": "Chat-Antwort regelbasiert generiert (kein API-Key).",
        }],
    }


def _create_trip_summary(trip: dict) -> str:
    req = trip.get("request", {})
    plan = trip.get("active_plan")
    lines = [
        f"Ziel: {req.get('destination')}, {req.get('duration_days')} Tage",
        f"Budget: {req.get('budget_total')} {req.get('currency')}, {req.get('number_of_people')} Person(en)",
        f"Reiseart: {req.get('travel_type')}, Interessen: {', '.join(req.get('interests', []))}",
    ]
    if plan:
        bs = plan.get("budget_summary", {})
        lines.append(f"Geplante Ausgaben: {bs.get('planned_total')} {bs.get('currency')}")
        for day in plan.get("days", []):
            acts = [s["activity"]["name"] for s in day.get("time_slots", [])]
            lines.append(f"Tag {day['day_number']}: {', '.join(acts)}")
    return "\n".join(lines)
