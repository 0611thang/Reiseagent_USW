import os
import json
from datetime import date
import profile_store
from providers.places import get_places

def _build_profile_summary():
    interests = profile_store.get_top_interests(limit=8)
    events = profile_store.get_past_events(limit=5)
    interest_lines = [f"- {i['keyword']} ({i['category']}): Score {round(i['total'], 1)}" for i in interests]
    event_lines = [f"- {e['name']} ({e['category']}, {e['date']})" for e in events]
    if not interest_lines:
        return "Noch kein Profil vorhanden."
    return "Interessen des Nutzers:\n" + "\n".join(interest_lines) + "\n\nVergangene besuchte Events:\n" + "\n".join(event_lines)

def create_suggestion_for_day(free_date, home_city="Berlin"):
    profile_store.init_db()
    interests = profile_store.get_top_interests(limit=8)
    profile_summary = _build_profile_summary()
    interest_keywords = [i["keyword"] for i in interests[:5]]
    pois = get_places(home_city, interest_keywords)
    poi_lines = [f"- {p['name']} ({p['category']}, {p.get('indoor_outdoor','?')}, ca. {p.get('estimated_cost_per_person', 0)}€/Person)" for p in pois[:10]]
    poi_text = "\n".join(poi_lines) if poi_lines else "Keine spezifischen POIs verfügbar."
    day_name = date.fromisoformat(free_date).strftime("%A, %d.%m.%Y")
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        activities = [p["name"] for p in pois[:3]]
        title = f"Vorschlag für {day_name}"
        description = "Basierend auf deinen Interessen empfehlen wir folgende Aktivitäten."
        profile_store.save_suggestion(free_date, title, description, activities)
        return {"date": free_date, "title": title, "description": description, "activities": activities, "status": "pending"}
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        prompt = f"""Du bist ein persönlicher Freizeitplaner.\n\n{profile_summary}\n\nVerfügbare Orte:\n{poi_text}\n\nDer Nutzer hat am {day_name} einen freien Tag.\nAntworte NUR als JSON ohne Markdown-Backticks:\n{{"title": "Kurzer Titel", "description": "2-3 Sätze warum dieser Tag passt", "activities": ["Aktivität 1", "Aktivität 2", "Aktivität 3"], "highlight": "Das Besondere in einem Satz"}}"""
        response = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}], max_tokens=400)
        data = json.loads(response.choices[0].message.content.strip())
        profile_store.save_suggestion(free_date, data["title"], data.get("description", ""), data.get("activities", []))
        return {"date": free_date, "title": data["title"], "description": data.get("description", ""), "activities": data.get("activities", []), "highlight": data.get("highlight", ""), "status": "pending"}
    except Exception:
        activities = [p["name"] for p in pois[:3]]
        title = f"Ausflug am {day_name}"
        profile_store.save_suggestion(free_date, title, "", activities)
        return {"date": free_date, "title": title, "activities": activities, "status": "pending"}

def create_suggestions_for_upcoming_free_days(home_city="Berlin", max_suggestions=3):
    profile_store.init_db()
    free_days = profile_store.get_upcoming_free_days(limit=max_suggestions)
    suggestions = [create_suggestion_for_day(day, home_city=home_city) for day in free_days]
    return {"suggestions": suggestions, "agent_insight": {"agent_name": "suggestion_agent", "display_label": "Vorschlags-Agent", "status": "completed", "summary": f"{len(suggestions)} personalisierte Vorschläge für freie Tage erstellt."}}
