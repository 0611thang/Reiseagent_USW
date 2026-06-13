import os
from groq import Groq


def create_navigation_reminder(activity_name, route):
    """
    Generiert eine Push-Erinnerung auf Deutsch mit 10 Minuten Puffer.
    Fallback auf einfachen Text wenn kein Groq-Key.
    """
    if not route:
        return f"Bitte rechtzeitig zur Aktivität '{activity_name}' aufbrechen."

    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        total = route["duration_minutes"] + 10
        return (
            f"Aufbruch in {total} Minuten für '{activity_name}'. "
            f"Gehzeit: {route['duration_minutes']} Min ({route['distance_km']} km)."
        )

    client = Groq(api_key=api_key)
    prompt = (
        f"Schreibe eine kurze freundliche Push-Erinnerung auf Deutsch. "
        f"Aktivität: '{activity_name}'. "
        f"Gehzeit: {route['duration_minutes']} Minuten, {route['distance_km']} km. "
        f"Inkl. 10 Minuten Puffer. Maximal 2 Sätze."
    )
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=80,
    )
    return response.choices[0].message.content


def get_agent_insight():
    return {
        "agent_name": "navigation_agent",
        "display_label": "Navigations Agent",
        "status": "completed",
        "summary": "Routen und Abfahrtszeiten berechnet.",
    }
