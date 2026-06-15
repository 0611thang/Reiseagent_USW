import json
import os
from datetime import date

import profile_store
from providers.places import get_places


def _build_profile_summary():
    interests = profile_store.get_top_interests(limit=8)
    events = profile_store.get_past_events(limit=5)

    interest_lines = [
        f"- {i['keyword']} ({i['category']}): Score {round(i['total'], 1)}"
        for i in interests
    ]
    event_lines = [
        f"- {e['name']} ({e['category']}, {e['date']})"
        for e in events
    ]

    if not interest_lines:
        return "Noch kein Profil vorhanden."

    return (
        "Interessen des Nutzers:\n"
        + "\n".join(interest_lines)
        + "\n\nVergangene besuchte Events:\n"
        + "\n".join(event_lines)
    )


def _get_already_suggested_activities(free_date):
    suggestions = profile_store.get_suggestions_for_date(free_date)
    activities = []
    for suggestion in suggestions:
        activities.extend(suggestion.get("activities", []))
    return activities


def _pick_activities(pois, free_date, already_suggested=None, count=3):
    already_suggested = set(already_suggested or [])
    if not pois:
        return []

    available = [p for p in pois if p["name"] not in already_suggested]
    if len(available) < count:
        available = pois

    day_number = date.fromisoformat(free_date).toordinal()
    start = day_number % len(available)

    selected = []
    for offset in range(len(available)):
        item = available[(start + offset) % len(available)]
        if item["name"] not in selected:
            selected.append(item["name"])
        if len(selected) == count:
            break

    return selected


def create_suggestion_for_day(
    free_date,
    home_city="Berlin",
    avoid_previous=True,
    extra_avoid=None,
):
    profile_store.init_db()

    interests = profile_store.get_top_interests(limit=8)
    profile_summary = _build_profile_summary()
    interest_keywords = [i["keyword"] for i in interests[:5]]

    pois = get_places(home_city, interest_keywords)
    already_suggested = []
    if avoid_previous:
        already_suggested = _get_already_suggested_activities(free_date)
    already_suggested += list(extra_avoid or [])

    poi_lines = [
        f"- {p['name']} ({p['category']}, {p.get('indoor_outdoor', '?')}, ca. {p.get('estimated_cost_per_person', 0)} EUR/Person)"
        for p in pois[:12]
    ]
    poi_text = "\n".join(poi_lines) if poi_lines else "Keine spezifischen POIs verfuegbar."
    day_name = date.fromisoformat(free_date).strftime("%A, %d.%m.%Y")

    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        activities = _pick_activities(pois, free_date, already_suggested)
        title = f"Vorschlag fuer {day_name}"
        description = "Basierend auf deinen Interessen empfehlen wir folgende Aktivitaeten."
        profile_store.save_suggestion(free_date, title, description, activities)
        return {
            "date": free_date,
            "title": title,
            "description": description,
            "activities": activities,
            "status": "pending",
        }

    try:
        from groq import Groq

        avoid_text = ", ".join(already_suggested) if already_suggested else "keine"
        prompt = f"""Du bist ein persoenlicher Freizeitplaner.

{profile_summary}

Verfuegbare Orte:
{poi_text}

Der Nutzer hat am {day_name} einen freien Tag.
Diese bereits vorgeschlagenen Aktivitaeten bitte vermeiden: {avoid_text}

Antworte NUR als JSON ohne Markdown-Backticks:
{{"title": "Kurzer Titel", "description": "2-3 Saetze warum dieser Tag passt", "activities": ["Aktivitaet 1", "Aktivitaet 2", "Aktivitaet 3"], "highlight": "Das Besondere in einem Satz"}}"""

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
        )
        data = json.loads(response.choices[0].message.content.strip())
        activities = data.get("activities", [])
        if not activities or any(a in already_suggested for a in activities):
            activities = _pick_activities(pois, free_date, already_suggested)

        profile_store.save_suggestion(
            free_date,
            data["title"],
            data.get("description", ""),
            activities,
        )
        return {
            "date": free_date,
            "title": data["title"],
            "description": data.get("description", ""),
            "activities": activities,
            "highlight": data.get("highlight", ""),
            "status": "pending",
        }
    except Exception:
        activities = _pick_activities(pois, free_date, already_suggested)
        title = f"Ausflug am {day_name}"
        profile_store.save_suggestion(free_date, title, "", activities)
        return {
            "date": free_date,
            "title": title,
            "activities": activities,
            "status": "pending",
        }


def create_replacement_suggestion(suggestion_id, home_city="Berlin"):
    profile_store.init_db()
    old_suggestion = profile_store.get_suggestion(suggestion_id)
    if not old_suggestion:
        return None
    return create_suggestion_for_day(
        old_suggestion["date"],
        home_city=home_city,
        avoid_previous=True,
    )


def create_suggestions_for_upcoming_free_days(home_city="Berlin", max_suggestions=3):
    profile_store.init_db()
    profile_store.update_pending_suggestions_status("replaced")
    free_days = profile_store.get_upcoming_free_days(limit=max_suggestions)

    suggestions = []
    used_activities = []
    for day in free_days:
        suggestion = create_suggestion_for_day(
            day,
            home_city=home_city,
            avoid_previous=False,
            extra_avoid=used_activities,
        )
        suggestions.append(suggestion)
        used_activities.extend(suggestion.get("activities", []))

    return {
        "suggestions": suggestions,
        "agent_insight": {
            "agent_name": "suggestion_agent",
            "display_label": "Vorschlags-Agent",
            "status": "completed",
            "summary": f"{len(suggestions)} personalisierte Vorschlaege fuer freie Tage erstellt.",
        },
    }
