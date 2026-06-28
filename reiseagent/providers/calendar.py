import os
from datetime import date, timedelta

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]

REISEAGENT_BLOCK_MARKER = "[REISEAGENT_USW_BLOCKED_DAY]"
REISEAGENT_TRIP_MARKER_PREFIX = "[REISEAGENT_USW_TRIP_ID:"


def _trip_marker(trip_id):
    if not trip_id:
        return ""
    return f"{REISEAGENT_TRIP_MARKER_PREFIX}{trip_id}]"


def _mark_description(description, trip_id=None, destination=None, date_str=None):
    details = []
    if destination:
        details.append(f"Reiseziel: {destination}")
    if date_str:
        details.append(f"Reisedatum: {date_str}")

    markers = [REISEAGENT_BLOCK_MARKER]
    trip_marker = _trip_marker(trip_id)
    if trip_marker:
        markers.append(trip_marker)

    additions = details + markers
    return description + "\n\n" + "\n".join(additions)

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

        window_start = datetime.combine(date.today(), time.min, tzinfo=timezone.utc)
        window_end = window_start + timedelta(days=days_ahead + 1)
        result = service.events().list(calendarId="primary", timeMin=window_start.isoformat(), timeMax=window_end.isoformat(), singleEvents=True, orderBy="startTime", maxResults=100).execute()
        events = []
        for item in result.get("items", []):
            description = item.get("description", "")
            summary = item.get("summary", "")
            blocks = REISEAGENT_BLOCK_MARKER in description
            is_all_day = "dateTime" not in item["start"]

            if is_all_day:
                # Ganztaegige Events koennen mehrere Tage umfassen (Google: Ende ist exklusiv).
                # Wir spalten sie in einen Eintrag pro Tag auf.
                start_str = item["start"].get("date", "")[:10]
                end_str = item.get("end", {}).get("date", "")[:10]
                if not start_str:
                    continue
                day = date.fromisoformat(start_str)
                last = date.fromisoformat(end_str) if end_str else day + timedelta(days=1)
                while day < last:
                    events.append({
                        "summary": summary,
                        "description": description,
                        "start": day.isoformat(),
                        "all_day": True,
                        "blocks_reiseagent_day": blocks,
                    })
                    day += timedelta(days=1)
            else:
                start_str = item["start"].get("dateTime", "")[:10]
                events.append({
                    "summary": summary,
                    "description": description,
                    "start": start_str,
                    "all_day": False,
                    "blocks_reiseagent_day": blocks,
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

        marked_description = _mark_description(description)

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


def sync_plan_day_to_calendar(day, trip_id=None, destination=None):
    try:
        service = _get_calendar_service()
        if not service:
            return {"updated": False, "reason": "credentials_missing"}

        date_str = day.get("date")
        if not date_str:
            return {"updated": False, "reason": "date_missing"}

        _delete_reiseagent_events_for_day(service, date_str, trip_id, day)

        title = f"Reiseplan Tag {day.get('day_number')}"
        description = _build_day_description(day)
        marked_description = _mark_description(
            description,
            trip_id,
            destination,
            date_str,
        )

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


def sync_changed_days_to_calendar(days, trip_id=None, destination=None):
    results = []
    for day in days:
        results.append(sync_plan_day_to_calendar(day, trip_id, destination))

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


def sync_full_plan_to_calendar(plan, trip_id=None):
    try:
        service = _get_calendar_service()
        if not service:
            return {"updated": False, "reason": "credentials_missing"}

        days = plan.get("days", [])
        if not days:
            return {"updated": False, "reason": "no_days"}

        destination = (plan.get("request") or {}).get("destination")
        results = []
        for day in days:
            date_str = day.get("date")
            if date_str:
                _delete_reiseagent_events_for_day(service, date_str, trip_id, day)

        for day in days:
            date_str = day.get("date")
            if not date_str:
                results.append({"updated": False, "reason": "date_missing"})
                continue

            title = f"Reiseplan Tag {day.get('day_number')}"
            description = _build_day_description(day)
            marked_description = _mark_description(
                description,
                trip_id,
                destination,
                date_str,
            )

            event = {
                "summary": title,
                "description": marked_description,
                "start": {"date": date_str},
                "end": {"date": (date.fromisoformat(date_str) + timedelta(days=1)).isoformat()},
            }
            created = service.events().insert(calendarId="primary", body=event).execute()
            results.append({
                "updated": True,
                "event_id": created.get("id"),
                "html_link": created.get("htmlLink"),
            })

        if all(result.get("updated") for result in results):
            return {"updated": True, "results": results}

        failed = next((r for r in results if not r.get("updated")), {})
        return {
            "updated": False,
            "reason": failed.get("reason", "unknown"),
            "results": results,
        }
    except Exception as error:
        return {"updated": False, "reason": type(error).__name__}


def _list_events_for_day(service, date_str):
    result = service.events().list(
        calendarId="primary",
        timeMin=f"{date_str}T00:00:00Z",
        timeMax=f"{date_str}T23:59:59Z",
        singleEvents=True,
        maxResults=50,
    ).execute()
    return result.get("items", [])


def _event_matches_trip(item, trip_id=None, day=None):
    description = item.get("description", "")
    if REISEAGENT_BLOCK_MARKER not in description:
        return False

    trip_marker = _trip_marker(trip_id)
    if REISEAGENT_TRIP_MARKER_PREFIX in description:
        return bool(trip_marker and trip_marker in description)

    # Alte Events haben noch keine trip_id. Sie werden nur bei exakt
    # passender Tagesbeschreibung als Teil dieser Reise erkannt.
    expected_description = _build_day_description(day) if day else ""
    return bool(expected_description and expected_description in description)


def _delete_reiseagent_events_for_day(service, date_str, trip_id=None, day=None):
    deleted_count = 0
    for item in _list_events_for_day(service, date_str):
        if _event_matches_trip(item, trip_id, day):
            service.events().delete(calendarId="primary", eventId=item["id"]).execute()
            deleted_count += 1
    return deleted_count


def delete_trip_from_calendar(trip):
    try:
        service = _get_calendar_service()
        if not service:
            return {
                "success": False,
                "deleted_count": 0,
                "message": "Kalender nicht eingerichtet.",
            }

        active_plan = trip.get("active_plan") or {}
        days = active_plan.get("days", [])
        trip_id = trip.get("id")
        deleted_count = 0

        for day in days:
            date_str = day.get("date")
            if date_str:
                deleted_count += _delete_reiseagent_events_for_day(
                    service,
                    date_str,
                    trip_id,
                    day,
                )

        if deleted_count:
            message = f"{deleted_count} Kalendereinträge gelöscht."
        else:
            message = "Keine passenden Kalendereinträge gefunden."

        return {
            "success": True,
            "deleted_count": deleted_count,
            "message": message,
        }
    except Exception as error:
        return {
            "success": False,
            "deleted_count": 0,
            "message": f"Kalender konnte nicht aktualisiert werden: {type(error).__name__}",
        }


def _build_day_description(day):
    lines = [f"Tag {day.get('day_number')} - {day.get('title', '')}"]
    for slot in day.get("time_slots", []):
        activity = slot.get("activity", {})
        lines.append(
            f"{slot.get('start_time', '')}-{slot.get('end_time', '')}: "
            f"{activity.get('name', '')}"
        )
    return "\n".join(lines)
