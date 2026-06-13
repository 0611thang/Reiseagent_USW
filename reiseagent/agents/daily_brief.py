import os
from groq import Groq
from providers.telegram import get_recent_messages, find_trip_relevant_messages
from providers.gmail import get_recent_emails, find_trip_relevant_emails


def create_daily_brief(trip, day_number):
    """
    Generiert einen Morgenbrief für den angegebenen Reisetag.
    Kombiniert Tagesplan, Gmail und Telegram.
    """
    plan = trip.get("active_plan")
    if not plan:
        return "Kein aktiver Reiseplan gefunden."

    destination = trip["request"]["destination"]
    day = next((d for d in plan["days"] if d["day_number"] == day_number), None)
    if not day:
        return "Kein Plan für diesen Tag gefunden."

    activities = [s["activity"]["name"] for s in day.get("time_slots", [])]
    weather = day.get("weather", {}).get("description", "unbekannt")

    # Gmail
    emails = get_recent_emails(hours=24)
    relevant_emails = find_trip_relevant_emails(emails, destination)
    gmail_section = ""
    if relevant_emails:
        lines = [f"- {e['subject']} ({e['from']}): {e['snippet'][:80]}" for e in relevant_emails]
        gmail_section = "Relevante Emails:\n" + "\n".join(lines)

    # Telegram
    messages = get_recent_messages(hours=24)
    relevant_msgs = find_trip_relevant_messages(messages, destination)
    telegram_section = ""
    if relevant_msgs:
        lines = [f"- {m['date']}: {m['text']}" for m in relevant_msgs]
        telegram_section = "Relevante Telegram-Nachrichten:\n" + "\n".join(lines)

    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return (
            f"Guten Morgen! Heute ist Tag {day_number} in {destination}.\n"
            f"Wetter: {weather}.\n"
            f"Geplant: {', '.join(activities)}.\n"
            + (f"\nHinweise aus Emails:\n{gmail_section}" if gmail_section else "")
            + (f"\nHinweise aus Telegram:\n{telegram_section}" if telegram_section else "")
        )

    client = Groq(api_key=api_key)
    prompt = (
        f"Schreibe einen freundlichen Morgenbrief auf Deutsch für Tag {day_number} "
        f"der Reise nach {destination}.\n"
        f"Wetter heute: {weather}.\n"
        f"Geplante Aktivitäten: {', '.join(activities)}.\n"
        f"{gmail_section}\n"
        f"{telegram_section}\n"
        f"Falls Nachrichten vorhanden: kurz erwähnen ob es Konflikte oder wichtige Hinweise gibt. "
        f"Maximal 6 Sätze, motivierend und persönlich."
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
    )
    return response.choices[0].message.content


def get_agent_insight():
    return {
        "agent_name": "daily_brief_agent",
        "display_label": "Tagesbrief Agent",
        "status": "completed",
        "summary": "Morgenbrief aus Reiseplan, Gmail und Telegram generiert.",
    }
