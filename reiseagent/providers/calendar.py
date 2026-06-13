import os
from datetime import date, timedelta

def get_calendar_events(days_ahead=14):
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from datetime import datetime, timezone
        SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
        creds = None
        if os.path.exists("calendar_token.json"):
            creds = Credentials.from_authorized_user_file("calendar_token.json", SCOPES)
        if not creds or not creds.valid:
            if not os.path.exists("credentials.json"):
                return []
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
            with open("calendar_token.json", "w") as f:
                f.write(creds.to_json())
        service = build("calendar", "v3", credentials=creds)
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days_ahead)
        result = service.events().list(calendarId="primary", timeMin=now.isoformat(), timeMax=end.isoformat(), singleEvents=True, orderBy="startTime", maxResults=50).execute()
        events = []
        for item in result.get("items", []):
            start = item["start"].get("dateTime", item["start"].get("date", ""))
            events.append({"summary": item.get("summary", ""), "start": start[:10], "all_day": "dateTime" not in item["start"]})
        return events
    except Exception:
        return []

def find_free_days(events, days_ahead=14):
    today = date.today()
    all_days = [(today + timedelta(days=i)).isoformat() for i in range(1, days_ahead + 1)]
    busy_days = set()
    for event in events:
        if event["all_day"]:
            busy_days.add(event["start"])
    event_count = {}
    for event in events:
        day = event["start"]
        event_count[day] = event_count.get(day, 0) + 1
    for day, count in event_count.items():
        if count >= 2:
            busy_days.add(day)
    free = [d for d in all_days if d not in busy_days]
    weekends = [d for d in free if date.fromisoformat(d).weekday() >= 5]
    weekdays = [d for d in free if date.fromisoformat(d).weekday() < 5]
    return {"weekends": weekends, "weekdays": weekdays, "all_free": free}
