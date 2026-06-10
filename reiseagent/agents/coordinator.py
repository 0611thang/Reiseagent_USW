import os
import uuid
from datetime import datetime

from providers.weather import get_weather_for_trip
from providers.places import get_places
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

    all_activities = get_places(request["destination"], request.get("interests", []))
    insights.append({
        "agent_name": "places_agent",
        "display_label": "POI Agent",
        "status": "completed",
        "summary": f"{len(all_activities)} Aktivitäten für {request['destination']} geladen.",
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
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if api_key:
        return _claude_response(trip, message, api_key)
    return _rule_based_response(trip, message)


def _claude_response(trip: dict, message: str, api_key: str) -> dict:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        trip_summary = _create_trip_summary(trip)

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": (
                    f"Du bist ein freundlicher Reiseassistent. Hier ist der aktuelle Reiseplan:\n"
                    f"{trip_summary}\n\n"
                    f"Nutzerfrage: {message}\n\n"
                    f"Antworte auf Deutsch, kurz und hilfreich."
                ),
            }],
        )
        return {
            "message": response.content[0].text,
            "agent_insights": [{
                "agent_name": "coordinator",
                "display_label": "Coordinator Agent",
                "status": "completed",
                "summary": "Chat-Antwort via Claude API generiert.",
            }],
        }
    except Exception as e:
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
