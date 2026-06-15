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
