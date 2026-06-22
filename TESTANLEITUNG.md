# Testanleitung — Reiseplanungsagent
**Stand:** 22.06.2026 | Getestete Blöcke: A1, A2, A4, C1, C2, C3, B3, D1, D2, E1

---

## Voraussetzungen

```bash
# Terminal 1 — Backend (für Monitoring + Telegram)
cd reiseagent
uvicorn main:app

# Terminal 2 — Frontend
cd reiseagent
streamlit run streamlit_app.py
```

**`.env` liegt im Projekt-Root** (`Reiseplanungsagent2/.env`), nicht in `reiseagent/`.  
App öffnet sich unter `http://localhost:8501`.

---

## Block A — Quick Wins

### A4 — Abflugzeit im Flug-Panel

**Vorbereitung:** `.env` setzen:
```
FLIGHT_NUMBER=LH400
MOCK_FLIGHT_ARRIVAL_TIME=14:30
MOCK_FLIGHT_DELAY_MINUTES=60
```

**Schritte:**
1. Demo-Reise laden (Button oben rechts)
2. Im Flug-Panel prüfen

**Erwartetes Ergebnis:**
```
Geplanter Abflug: 11:15  |  Aktueller Abflug: 12:15
Geplante Ankunft: 14:30  |  Aktuelle Ankunft: 15:30
```

**Worauf achten:**
- Beide Zeilen müssen erscheinen (nicht nur Ankunft)
- Bei `MOCK_FLIGHT_DELAY_MINUTES=60` müssen Abflug UND Ankunft jeweils +60 Min verschoben sein
- Ohne Flugnummer → Panel soll komplett ausgeblendet sein

---

### A1 — Reiseübersicht

**Schritte:**
1. 2–3 Reisen anlegen (oder Demo-Reise mehrfach laden)
2. Ganz nach unten scrollen → Liste „Deine Reisen" prüfen
3. „Öffnen"-Button einer anderen Reise klicken

**Erwartetes Ergebnis:**
- Alle Reisen erscheinen mit Ziel, Dauer, Datum, Status
- Aktive Reise zeigt „Aktiv"-Button (ausgegraut, nicht klickbar)
- Nach „Öffnen": Plan und Chat wechseln zur gewählten Reise

**Worauf achten:**
- Wenn noch kein Trip aktiv ist, erscheint die Liste trotzdem (unterhalb des Info-Hinweises)
- Chat-Nachrichten müssen zur neuen Reise passen — nicht die der alten Reise zeigen

---

### A2 — Datepicker + Tagesstart

**Schritte:**
1. Expander „Eigene Reise planen" öffnen
2. Startdatum: 15. Juli, Enddatum: 19. Juli, Tagesstart: 10:00
3. Ziel: München, Budget und Interessen beliebig → „Reise planen"

**Erwartetes Ergebnis:**
- Plan hat 5 Tage (`duration_days=5`)
- Tag 1 trägt Datum 15. Juli, Tag 2 → 16. Juli usw.
- Aktivitäten starten ab 10:00 (oder später, je nach Routing)

**Fehlerfall testen:**
- Enddatum vor Startdatum setzen → rote Fehlermeldung, Plan wird nicht erstellt

**Worauf achten:**
- Kein Tage-Slider mehr — der ist ersetzt
- Mit Flugnummer: Tag 1 startet nach Flugankunft, nicht um 10:00 (C2-Fallback-Kette)
- Ohne Flugnummer: alle Tage starten um den gewählten Tagesstart

---

## Block C — Core Features

### C2 — Dynamischer Reiseplan

**Schritte:**
1. Reise für München anlegen (Tagesstart 09:00, kein Flug)
2. Tagesplan im mittleren Panel anschauen

**Erwartetes Ergebnis:**
- Zeiten sind variabel (nicht mehr 09:00 / 12:00 / 14:00 / 19:00 fix)
- Aktivitäten folgen direkt aufeinander mit realistischen Lücken
- Museum: ~120 Min, Restaurant: ~75 Min, Park: ~60 Min

**Mit ORS-Key (wenn `ORS_API_KEY` gesetzt):**
- Fahrtzeiten zwischen Aktivitäten werden berechnet
- Im „Plan bearbeiten"-Bereich erscheint `🚶 X Min` zur nächsten Aktivität

**Ohne ORS-Key:**
- Fallback: 20 Min Puffer zwischen Aktivitäten
- Kein Crash, kein leerer Plan

**Worauf achten:**
- Zeiten dürfen sich nicht überlappen
- Letzter Slot des Tages darf nicht nach 23:59 enden
- `travel_to_next_minutes` beim letzten Slot eines Tages = 0 (kein Folge-Slot)

---

### C1 — Flug-Monitoring-Zeitsteuerung

**Testen nur mit laufendem Backend (`uvicorn main:app`).**

**Vorbereitung `.env`:**
```
FLIGHT_NUMBER=LH400
MOCK_FLIGHT_ARRIVAL_TIME=<jetzt + 1,5h>   # z.B. wenn es 14:00 ist → 15:30
```

**Schritte:**
1. Demo-Reise laden
2. Backend-Logs beobachten (Terminal 1)

**Erwartetes Ergebnis in den Logs:**
```
[monitoring] Flug-Check für Trip abc123 (Intervall 900s)
```
→ Intervall 900s = 15 Min (weil Abflug < 2h entfernt)

**Intervalle nach Abflugzeit:**
| Zeit bis Abflug | Erwartetes Intervall |
|---|---|
| > 24h | kein Check (None) |
| 6–24h | alle 6h (21600s) |
| 2–6h | stündlich (3600s) |
| < 2h | alle 15 Min (900s) |

**Worauf achten:**
- Trip ohne Flugnummer → kein Flug-Check-Log (wird übersprungen)
- Wetter-Check läuft weiterhin alle 30 Min für alle aktiven Trips (separater Log)

---

### C3 — Aktivitätskarten + 3-Button-System

**Schritte:**

**1. Zeit ändern:**
- Im „Plan bearbeiten"-Bereich Zeitpicker einer Aktivität ändern (z. B. 09:00 → 11:00)
- „✓ Zeit"-Button klicken
- Erwartung: Startzeit geändert, folgende Aktivitäten verschieben sich mit (Kaskade)

**2. Aktivität löschen:**
- 🗑️-Button klicken
- Erwartung: Aktivität verschwindet aus dem Plan, nachfolgende Zeiten passen sich an

**3. Alternative:**
- „Alt."-Button klicken
- Erwartung: Aufklappbereich direkt darunter mit bis zu 3 Alternativen gleicher Kategorie
- „Wählen" ersetzen → Aktivität im Plan aktualisiert
- Zweiten „Alt."-Klick → Bereich schließt sich wieder

**4. KI-Alternative (ohne Profil):**
- „KI-Alt."-Button klicken
- Erwartung: Hinweis „Noch keine Interessen bekannt — verbinde deine E-Mails"

**4. KI-Alternative (mit Profil, nach D1-Test):**
- Erwartung: Profilbasierte Vorschläge mit Begründung (z. B. „Basierend auf: kunst, natur")

**Worauf achten:**
- Alt. und KI-Alt. schließen sich gegenseitig (nie beide gleichzeitig offen)
- Nach „Wählen" schließt der Aufklappbereich automatisch
- Ohne `OPENTRIPMAP_API_KEY`: Alternativen-Liste kann leer sein (kein Crash)

---

## Block B3 / D — Profil-Strang

### B3 — IMAP Provider

**Voraussetzung:**
```
# In .env eintragen:
IMAP_HOST=imap.web.de
IMAP_PORT=993
IMAP_USER=usw_reiseplaner@web.de
IMAP_PASSWORD=<App-Passwort aus web.de-Einstellungen>
```

**App-Passwort erstellen:** web.de → Einstellungen → E-Mail → POP3/IMAP Abruf → App-Passwort generieren. **Nicht** das normale Login-Passwort.

**Test im Terminal:**
```bash
cd reiseagent
python -c "from providers.imap_mail import get_recent_emails; emails = get_recent_emails(5); print(emails)"
```

**Erwartetes Ergebnis:**
```python
[{'subject': 'Willkommen bei FitnessFirst', 'from': '...', 'snippet': '...'}]
```

**Ohne Credentials:**
```python
[]   # leere Liste, kein Fehler
```

**Worauf achten:**
- Umlaute im Betreff (ä, ö, ü) müssen korrekt dargestellt sein
- HTML-Mails: Snippet ist der Text ohne HTML-Tags (grob)
- `[imap] Verbindungsfehler:` im Log → IMAP in web.de-Einstellungen aktiviert?

---

### D1 — Profil aus E-Mails lernen

**Demo-Mails vorbereiten:** Eine E-Mail an `usw_reiseplaner@web.de` senden:
- Betreff: „Willkommen im FitnessFirst Gym — dein Abo startet"
- Eine weitere: „ARCHITECTURE TODAY — Das Magazin für Architektur-Fans"

**Profil-Update triggern:**
```bash
# Option A: API-Endpoint (Backend muss laufen)
curl -X POST http://localhost:8000/api/profile/update

# Option B: Terminal direkt
cd reiseagent
python -c "
from providers.imap_mail import get_recent_emails
from agents.profile_learner import run_profile_update
emails = get_recent_emails(20)
result = run_profile_update(imap_emails=emails)
print(result['top_interests'])
"
```

**Erwartetes Ergebnis:**
```python
[{'category': 'sport', 'keyword': 'gym', 'total': 1.0},
 {'category': 'kunst', 'keyword': 'kunst', 'total': 1.0}]
```

**Worauf achten:**
- `source` in der DB sollte `"imap"` sein (nicht `"gmail"`)
- Interessen werden bei wiederholtem Update aufsummiert (Score erhöht sich), nicht dupliziert

---

### D2 — Profil in Reiseplanung einbeziehen

**Vorbereitung:** D1-Test zuerst durchführen, damit Profil gefüllt ist.

**Schritte:**
1. Neue Reise anlegen (ohne „Museen" in den Formular-Interessen)
2. Agent-Insight nach dem Laden prüfen

**Erwartetes Ergebnis im Coordinator-Insight:**
```
Alle Agenten erfolgreich koordiniert. Profil ergänzt: Museen, Spaziergänge.
```

**Und im Plan:** mehr Museen/Kunstgalerien als ohne Profil

**Leertest (Profil leer):**
- `profile.db` löschen oder umbenennen
- Neue Reise anlegen → Insight zeigt kein „Profil ergänzt", Verhalten identisch zu vorher

---

## Block E1 — Refactor-Verifikation

Kein neues Feature — nur sicherstellen, dass alles noch funktioniert wie vorher.

**Smoke-Test-Checkliste:**
- [ ] Demo-Reise laden → Plan erscheint
- [ ] Eigene Reise planen → Plan erscheint, Trip in Reiseübersicht sichtbar
- [ ] Chat-Nachricht senden (z. B. „Was kann ich in Berlin machen?") → Antwort erscheint
- [ ] Chat-Zeitänderung (z. B. „plane Museum auf 15 Uhr") → Plan aktualisiert
- [ ] Reise wechseln über Reiseübersicht → Chat und Plan wechseln korrekt

---

## Bekannte Einschränkungen

| Einschränkung | Betrifft | Workaround |
|---|---|---|
| A3 Telegram-Buttons nicht repariert | Telegram-Callback | Backend muss laufen; Bug noch offen |
| Anreise-Puffer noch 75 Min (geplant: 180) | Tag 1 bei Flugnummer | `coordinator.py` ~Zeile 185 anpassen |
| C2 Variante B (LLM) nicht implementiert | Plan-Qualität | Variante A (deterministisch) läuft stabil |
| Alternativen leer ohne OpenTripMap-Key | C3 Alt.-Button | `OPENTRIPMAP_API_KEY` in `.env` setzen |
| IMAP nicht getestet ohne App-Passwort | B3/D1 | Credentials einrichten, dann testen |
