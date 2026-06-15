from providers.calendar import get_calendar_events, find_free_days
import profile_store

def detect_and_save_free_days(days_ahead=14):
    profile_store.init_db()
    events = get_calendar_events(days_ahead=days_ahead)
    free = find_free_days(events, days_ahead=days_ahead)
    profile_store.replace_free_days(free["all_free"])
    profile_store.update_pending_suggestions_status("replaced")
    return {
        "free_days": free,
        "calendar_events_found": len(events),
        "agent_insight": {
            "agent_name": "free_time_detector",
            "display_label": "Freizeit-Erkenner Agent",
            "status": "completed",
            "summary": f"{len(free['all_free'])} freie Tage erkannt ({len(free['weekends'])} Wochenenden, {len(free['weekdays'])} Werktage).",
        }
    }
