from agents.calendar_agent import get_truly_free_days
import profile_store


def detect_and_save_free_days(days_ahead=14):
    profile_store.init_db()
    free_days = get_truly_free_days(days_ahead=days_ahead)
    profile_store.replace_free_days(free_days)
    profile_store.update_pending_suggestions_status("replaced")
    return {
        "free_days": free_days,
        "agent_insight": {
            "agent_name": "free_time_detector",
            "display_label": "Freizeit-Erkenner Agent",
            "status": "completed",
            "summary": f"{len(free_days)} freie Tage erkannt und gespeichert.",
        }
    }
