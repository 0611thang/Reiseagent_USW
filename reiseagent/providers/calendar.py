import os
from datetime import date, timedelta

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]

REISEAGENT_BLOCK_MARKER = "[REISEAGENT_USW_BLOCKED_DAY]"

def _get_calendar_service():
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists("calendar_token.json"):
        creds = Credentials.from_authorized_user_file("calendar_token.json", SCOPES)

    has_needed_scopes = creds and creds.valid and creds.has_scopes(SCOPES)
    if not has_needed_scopes:
        if not os.path.exists("credentials.json"):
            return None
        flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        creds = flow.run_local_server(port=0)
        with open("calendar_token.json", "w") as f:
            f.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)

def get_calendar_events(days_ahead=14):
    try:
        from datetime import datetime, time, timezone

        service = _get_calendar_service()
        if not service:
            return []

        start = datetime.combine(date.today(), time.min, tzinfo=timezone.utc)
        end = start + timedelta(days=days_ahead + 1)
        result = service.events().list(calendarId="primary", timeMin=start.isoformat(), timeMax=end.isoformat(), singleEvents=True, orderBy="startTime", maxResults=100).execute()
        events = []
        for item in result.get("items", []):
            start = item["start"].get("dateTime", item["start"].get("date", ""))
            description = item.get("description", "")
            events.append({
                "summary": item.get("summary", ""),
                "description": description,
                "start": start[:10],
                "all_day": "dateTime" not in item["start"],
                "blocks_reiseagent_day": REISEAGENT_BLOCK_MARKER in description,
            })
        return events
    except Exception:
        return []

def find_free_days(events, days_ahead=14):
    today = date.today()
    all_days = [(today + timedelta(days=i)).isoformat() for i in range(1, days_ahead + 1)]
    busy_days = set()
    for event in events:
        if event.get("blocks_reiseagent_day"):
            busy_days.add(event["start"])
    free = [d for d in all_days if d not in busy_days]
    weekends = [d for d in free if date.fromisoformat(d).weekday() >= 5]
    weekdays = [d for d in free if date.fromisoformat(d).weekday() < 5]
    return {"weekends": weekends, "weekdays": weekdays, "all_free": free}

def create_calendar_event(title, description, date_str):
    try:
        service = _get_calendar_service()
        if not service:
            return {"created": False, "reason": "credentials_missing"}

        marked_description = description + "\n\n" + REISEAGENT_BLOCK_MARKER

        event = {
            "summary": title,
            "description": marked_description,
            "start": {"date": date_str},
            "end": {"date": (date.fromisoformat(date_str) + timedelta(days=1)).isoformat()},
        }

        created = service.events().insert(calendarId="primary", body=event).execute()
        return {
            "created": True,
            "event_id": created.get("id"),
            "html_link": created.get("htmlLink"),
        }
    except Exception as error:
        return {"created": False, "reason": type(error).__name__}


def sync_plan_day_to_calendar(day):
    try:
        service = _get_calendar_service()
        if not service:
            return {"updated": False, "reason": "credentials_missing"}

        date_str = day.get("date")
        if not date_str:
            return {"updated": False, "reason": "date_missing"}

        _delete_reiseagent_events_for_day(service, date_str)

        title = f"Reiseplan Tag {day.get('day_number')}"
        description = _build_day_description(day)
        marked_description = description + "\n\n" + REISEAGENT_BLOCK_MARKER

        event = {
            "summary": title,
            "description": marked_description,
            "start": {"date": date_str},
            "end": {"date": (date.fromisoformat(date_str) + timedelta(days=1)).isoformat()},
        }

        created = service.events().insert(calendarId="primary", body=event).execute()
        return {
            "updated": True,
            "event_id": created.get("id"),
            "html_link": created.get("htmlLink"),
        }
    except Exception as error:
        return {"updated": False, "reason": type(error).__name__}


def sync_changed_days_to_calendar(days):
    results = []
    for day in days:
        results.append(sync_plan_day_to_calendar(day))

    if not results:
        return {"updated": False, "reason": "no_days"}

    if all(result.get("updated") for result in results):
        return {"updated": True, "results": results}

    failed = next((r for r in results if not r.get("updated")), {})
    return {
        "updated": False,
        "reason": failed.get("reason", "unknown"),
        "results": results,
    }


def _delete_reiseagent_events_for_day(service, date_str):
    result = service.events().list(
        calendarId="primary",
        timeMin=f"{date_str}T00:00:00Z",
        timeMax=f"{date_str}T23:59:59Z",
        singleEvents=True,
        maxResults=50,
    ).execute()

    for item in result.get("items", []):
        description = item.get("description", "")
        if REISEAGENT_BLOCK_MARKER in description:
            service.events().delete(calendarId="primary", eventId=item["id"]).execute()


def _build_day_description(day):
    lines = [f"Tag {day.get('day_number')} - {day.get('title', '')}"]
    for slot in day.get("time_slots", []):
        activity = slot.get("activity", {})
        lines.append(
            f"{slot.get('start_time', '')}-{slot.get('end_time', '')}: "
            f"{activity.get('name', '')}"
        )
    return "\n".join(lines)
