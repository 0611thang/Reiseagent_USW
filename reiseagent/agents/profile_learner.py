import os
import re
from datetime import datetime
import profile_store

INTEREST_CATEGORIES = {
    "musik": ["konzert", "festival", "open air", "band", "livemusik", "ticket", "club", "dj"],
    "kunst": ["museum", "galerie", "ausstellung", "vernissage", "kunsthalle", "kunst"],
    "sport": ["marathon", "yoga", "fitness", "klettern", "fahrrad", "wandern", "schwimmen", "gym"],
    "essen": ["restaurant", "brunch", "dinner", "foodtruck", "street food", "weinprobe", "kochkurs"],
    "natur": ["wandern", "park", "see", "strand", "wald", "garten", "natur"],
    "kultur": ["theater", "oper", "lesung", "kino", "film", "vortrag", "stadtführung"],
    "gaming": ["gaming", "spieleabend", "brettspiel", "escape room"],
    "reisen": ["ausflug", "wochenende", "tagesausflug", "reise", "urlaub"],
    "technologie": ["hackathon", "meetup", "konferenz", "tech", "startup"],
}

EVENT_PATTERNS = [
    r"ticket.*?(?:für|zu|zum)\s+([\w\s]+)",
    r"eintrittskarte.*?([\w\s]+)",
    r"buchung.*?(?:für|zu|beim?)\s+([\w\s]+)",
    r"anmeldung.*?(?:für|zu)\s+([\w\s]+)",
    r"bestellung.*?(?:für|zu)\s+([\w\s]+)",
]

def _extract_interests_from_text(text, source):
    text_lower = text.lower()
    for category, keywords in INTEREST_CATEGORIES.items():
        for kw in keywords:
            if kw in text_lower:
                profile_store.save_interest(category, kw, score=1.0, source=source)

def _extract_event_from_text(text, source, date=None):
    text_lower = text.lower()
    for pattern in EVENT_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            event_name = match.group(1).strip()
            if len(event_name) > 3:
                category = "unbekannt"
                for cat, keywords in INTEREST_CATEGORIES.items():
                    if any(kw in text_lower for kw in keywords):
                        category = cat
                        break
                profile_store.save_past_event(name=event_name, category=category, date=date or datetime.now().strftime("%Y-%m-%d"), source=source, raw_text=text[:200])
                return

def learn_from_telegram(messages):
    for msg in messages:
        text = msg.get("text", "")
        if len(text) < 5:
            continue
        _extract_interests_from_text(text, source="telegram")
        _extract_event_from_text(text, source="telegram", date=msg.get("date"))

def learn_from_gmail(emails):
    for email in emails:
        full_text = email.get("subject", "") + " " + email.get("snippet", "")
        _extract_interests_from_text(full_text, source="gmail")
        _extract_event_from_text(full_text, source="gmail")

def run_profile_update(telegram_messages=None, gmail_emails=None):
    profile_store.init_db()
    if telegram_messages:
        learn_from_telegram(telegram_messages)
    if gmail_emails:
        learn_from_gmail(gmail_emails)
    top_interests = profile_store.get_top_interests(limit=5)
    past_events = profile_store.get_past_events(limit=3)
    return {
        "top_interests": top_interests,
        "recent_events": past_events,
        "agent_insight": {
            "agent_name": "profile_learner",
            "display_label": "Profil-Lerner Agent",
            "status": "completed",
            "summary": f"{len(top_interests)} Interessen erkannt, {len(past_events)} vergangene Events gespeichert.",
        }
    }
