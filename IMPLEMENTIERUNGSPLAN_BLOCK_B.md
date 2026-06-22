# Implementierungsplan — Block B (Provider)

**Datum:** 21.06.2026
**Grundlage:** [TODO_2026-06-21.md](TODO_2026-06-21.md)
**Umfang:** B1 (✅ erledigt), B2 (✅ erledigt), B3 (web.de IMAP)

---

## B1 — Ankunftszeit aus Flight API ✅ ERLEDIGT
Keine Arbeit nötig. `scheduled_arrival`/`estimated_arrival`/`actual_arrival` in `providers/flights.py:173-176`. Tag-1-Anpassung in `agents/coordinator.py:106-195`.
**Nur verifizieren:** Demo-Reise mit Flugnummer → Tag 1 beginnt nach Ankunftszeit.

## B2 — OpenRouteService Provider ✅ ERLEDIGT
Keine Arbeit nötig. `providers/navigation.py:5` (`get_route`, `get_both_routes`). Braucht `ORS_API_KEY` in `.env`.
**Nur verifizieren:** `ORS_API_KEY` gesetzt? Testroute zwischen zwei Koordinaten liefert `duration_minutes`.

---

## B3 — web.de IMAP Provider ❌ (einziger echter Task in Block B)

### Ziel
Neuer Provider, der das Postfach `usw_reiseplaner@web.de` per IMAP ausliest und E-Mails im selben Format wie `gmail.py` zurückgibt — damit `profile_learner.py` (D1) sie ohne Umbau verarbeiten kann.

### Betroffene Dateien
- **Neu:** `reiseagent/providers/imap_mail.py`
- `reiseagent/.env` → neue Variablen
- (später D1: `agents/profile_learner.py`)

### Zielformat (muss zu `profile_learner.learn_from_gmail` passen)
`learn_from_gmail` (`profile_learner.py:56-60`) erwartet pro E-Mail:
```python
{"subject": "...", "from": "...", "snippet": "..."}
```
→ Der IMAP-Provider liefert exakt diese Keys. So bleibt der Profil-Lerner unverändert; in D1 wird nur eine dünne `learn_from_imap = learn_from_gmail`-Brücke nötig.

### Neue .env-Variablen
```
IMAP_HOST=imap.web.de
IMAP_PORT=993
IMAP_USER=usw_reiseplaner@web.de
IMAP_PASSWORD=<App-Passwort, NICHT das Login-Passwort>
```
**Wichtig:** web.de verlangt ein **App-Passwort** und aktiviertes IMAP in den web.de-Einstellungen (Einstellungen → POP3/IMAP Abruf). Das normale Login-Passwort funktioniert oft nicht.

### Implementierung (Standardbibliothek `imaplib`, kein neues Dependency)
```python
import os, imaplib, email
from email.header import decode_header

def _decode(value):
    if not value:
        return ""
    parts = decode_header(value)
    out = ""
    for text, enc in parts:
        out += text.decode(enc or "utf-8", errors="replace") if isinstance(text, bytes) else text
    return out

def get_recent_emails(limit=20):
    """Liest die letzten E-Mails via IMAP. Gibt [] zurueck, wenn nicht konfiguriert."""
    host = os.getenv("IMAP_HOST", "imap.web.de")
    user = os.getenv("IMAP_USER", "")
    password = os.getenv("IMAP_PASSWORD", "")
    if not user or not password:
        return []
    try:
        imap = imaplib.IMAP4_SSL(host, int(os.getenv("IMAP_PORT", "993")))
        imap.login(user, password)
        imap.select("INBOX")
        _, ids = imap.search(None, "ALL")
        id_list = ids[0].split()[-limit:]  # letzte N
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
        print(f"[imap] Fehler: {type(exc).__name__}")
        return []
```
`_extract_snippet(msg)` zieht den ersten Text/Plain-Body (max ~300 Zeichen) — analog zum Gmail-`snippet`.

### Edge Cases
- Nicht konfiguriert → `[]` (gleiches Fail-Silent-Muster wie `gmail.py:50-51`). System läuft ohne E-Mail weiter.
- HTML-only Mails: Fallback auf `text/html` mit grobem Tag-Strip, oder Snippet leer lassen.
- Encoding (Umlaute) → über `decode_header` + `errors="replace"` abgesichert.
- Multipart vs. einfache Mails → in `_extract_snippet` per `msg.walk()` behandeln.

### Verifikation
1. Fake-Mail an `usw_reiseplaner@web.de` senden (z. B. „Dein Gym-Abo", „Architektur-Magazin").
2. `python -c "from providers.imap_mail import get_recent_emails; print(get_recent_emails(5))"` → Liste mit subject/from/snippet.
3. Umlaute korrekt? Snippet befüllt?

### Aufwand
~1,5–2 h inkl. web.de-App-Passwort-Einrichtung und Snippet-Extraktion.

---

## Definition of Done (Block B)
- [ ] B1/B2 als vorhanden verifiziert (keine Code-Arbeit)
- [ ] `providers/imap_mail.py` liest web.de, liefert `{subject, from, snippet}`
- [ ] `.env`-Variablen dokumentiert, App-Passwort eingerichtet, IMAP in web.de aktiviert
- [ ] Fake-Mail erscheint im Provider-Output
