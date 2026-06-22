import os
import imaplib
import email
from email.header import decode_header


def _decode(value):
    if not value:
        return ""
    parts = decode_header(value)
    out = ""
    for text, enc in parts:
        if isinstance(text, bytes):
            out += text.decode(enc or "utf-8", errors="replace")
        else:
            out += text
    return out


def _extract_snippet(msg):
    # Versucht zuerst text/plain, dann text/html (grob getrimmt)
    for part in msg.walk():
        content_type = part.get_content_type()
        if content_type == "text/plain":
            payload = part.get_payload(decode=True)
            if payload:
                return payload.decode(part.get_content_charset() or "utf-8", errors="replace")[:300]
    for part in msg.walk():
        content_type = part.get_content_type()
        if content_type == "text/html":
            payload = part.get_payload(decode=True)
            if payload:
                raw = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                # HTML-Tags grob entfernen
                import re
                text = re.sub(r"<[^>]+>", " ", raw)
                return text[:300].strip()
    return ""


def get_recent_emails(limit=20):
    """Liest die letzten E-Mails vom web.de-Postfach via IMAP.
    Gibt [] zurück wenn nicht konfiguriert oder Verbindung fehlschlägt."""
    host = os.getenv("IMAP_HOST", "imap.web.de")
    port = int(os.getenv("IMAP_PORT", "993"))
    user = os.getenv("IMAP_USER", "")
    password = os.getenv("IMAP_PASSWORD", "")

    if not user or not password:
        return []

    try:
        imap = imaplib.IMAP4_SSL(host, port)
        imap.login(user, password)
        imap.select("INBOX")

        _, ids = imap.search(None, "ALL")
        id_list = ids[0].split()
        id_list = id_list[-limit:]  # nur die letzten N

        emails = []
        for msg_id in reversed(id_list):
            _, data = imap.fetch(msg_id, "(RFC822)")
            msg = email.message_from_bytes(data[0][1])
            emails.append({
                "subject": _decode(msg.get("Subject")),
                "from": _decode(msg.get("From")),
                "snippet": _extract_snippet(msg),
            })

        imap.logout()
        return emails

    except Exception as exc:
        print(f"[imap] Verbindungsfehler: {type(exc).__name__}: {exc}")
        return []
