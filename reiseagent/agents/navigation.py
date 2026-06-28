import llm
import prompts


def create_navigation_reminder(activity_name, route):
    """
    Generiert eine Push-Erinnerung auf Deutsch mit 10 Minuten Puffer.
    Fallback auf einfachen Text wenn kein Groq-Key.
    """
    if not route:
        return f"Bitte rechtzeitig zur Aktivität '{activity_name}' aufbrechen."

    text = llm.call(
        "navigation_agent",
        prompts.fill(
            prompts.NAVIGATION_REMINDER,
            activity_name=activity_name,
            duration_minutes=route["duration_minutes"],
            distance_km=route["distance_km"],
        ),
        prompt_id="NAVIGATION_REMINDER",
        max_tokens=80,
    )
    if text is not None:
        return text

    total = route["duration_minutes"] + 10
    return (
        f"Aufbruch in {total} Minuten für '{activity_name}'. "
        f"Gehzeit: {route['duration_minutes']} Min ({route['distance_km']} km)."
    )


def get_agent_insight():
    return {
        "agent_name": "navigation_agent",
        "display_label": "Navigations Agent",
        "status": "completed",
        "summary": "Routen und Abfahrtszeiten berechnet.",
    }
