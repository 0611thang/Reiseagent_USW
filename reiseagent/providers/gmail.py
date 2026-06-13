import os
from datetime import datetime, timedelta


def get_recent_emails(hours=24):
    """
    Liest Emails der letzten X Stunden via Gmail API.
    Braucht credentials.json (Google Cloud OAuth2).
    Gibt leere Liste zurück wenn nicht konfiguriert.
    """
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
        creds = None

        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)

        if not creds or not creds.valid:
            if not os.path.exists("credentials.json"):
                return []
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
            with open("token.json", "w") as f:
                f.write(creds.to_json())

        service = build("gmail", "v1", credentials=creds)
        cutoff = int((datetime.now() - timedelta(hours=hours)).timestamp())

        results = service.users().messages().list(
            userId="me", q=f"after:{cutoff}", maxResults=20
        ).execute()

        emails = []
        for msg in results.get("messages", []):
            detail = service.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["Subject", "From"],
            ).execute()
            headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
            emails.append({
                "subject": headers.get("Subject", ""),
                "from": headers.get("From", ""),
                "snippet": detail.get("snippet", ""),
            })
        return emails
    except Exception:
        return []


def find_trip_relevant_emails(emails, destination):
    """Filtert Emails nach reisebezogenen Keywords."""
    keywords = [
        destination.lower(),
        "buchung", "reservierung", "bestätigung", "confirmation",
        "hotel", "flug", "bahn", "ticket", "absage", "stornierung",
        "restaurant", "museum", "eintrittskarte",
    ]
    relevant = []
    for email in emails:
        text = (email["subject"] + " " + email["snippet"]).lower()
        if any(kw in text for kw in keywords):
            relevant.append(email)
    return relevant
