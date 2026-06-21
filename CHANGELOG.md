# Changelog — Reiseplanungsagent

Alle Änderungen am Projekt werden hier dokumentiert.  
Sortierung: **neueste Einträge oben**.

---

## [2026-06-21] Feature: Flugankunft im Reiseplan und UI-Zeitbearbeitung

**Status:** Merged
**Datum & Uhrzeit:** 2026-06-21 16:08
**Autor:** Ibrahim Danisman
**Commit:** `eb76d48`

### Zweck
Flugdaten sollen bereits bei der Reiseplanung sichtbar sein und den ersten Reisetag sinnvoll beeinflussen. Zusätzlich sollen Nutzer Aktivitätszeiten direkt in Streamlit bearbeiten können.

### Was wurde geändert

**Flugdaten bei der Erstplanung:**
- `coordinator.py` lädt bei vorhandener Flugnummer direkt Flugdaten über den bestehenden Flight-Provider.
- Flugnummer und Flugdetails werden als `flight_updates` im Trip gespeichert.
- Reale Aviationstack-Daten werden bevorzugt; ohne API-Key bleibt der Mock-Fallback aktiv.

**Ankunftsbasierter erster Reisetag:**
- Verwendete Reihenfolge: tatsächliche, geschätzte, danach geplante Ankunft.
- Tag 1 beginnt mit Flugankunft sowie einem 75-Minuten-Puffer für Transfer und Hotel-Check-in.
- Aktivitäten vor der verfügbaren Ankunftszeit werden aus Tag 1 entfernt.
- Tag 2 und spätere Tage behalten ihre normalen Startzeiten.

**Streamlit-Oberfläche:**
- Neuer Flugbereich mit Flugnummer, Route, geplanter und aktueller Ankunft sowie Status.
- Mock-Daten werden mit `Flugmonitoring simuliert` gekennzeichnet.
- Im Bereich `Plan schnell bearbeiten` können Tag, Aktivität, Startzeit und Endzeit ausgewählt werden.
- Die UI verwendet für Zeitänderungen dieselbe Konflikt-, Sortier- und Kalenderlogik wie der Chatbot.

**Monitoring und Testbarkeit:**
- Gestrichene und umgeleitete Flüge werden als relevante Monitoring-Ereignisse erkannt.
- Neue Mock-Konfiguration `MOCK_FLIGHT_ARRIVAL_TIME` ergänzt.
- `FLIGHT_NUMBER` kann als Standardwert aus der Environment-Konfiguration gelesen werden.

### Betroffene Dateien
- `reiseagent/agents/coordinator.py`
- `reiseagent/agents/monitoring.py`
- `reiseagent/main.py`
- `reiseagent/providers/flights.py`
- `reiseagent/streamlit_app.py`
- `reiseagent/.env.example`

### Tests
- Flug BA 8493 mit geplanter Ankunft 16:05 und aktueller Ankunft 16:16 simuliert.
- Tag 1 startete ab 16:16; Tag 2 blieb bei 09:00.
- Mock-Verspätung erzeugte einen Replanning-Vorschlag.
- Chat- und UI-Zeitänderung aktualisierten Plan und Kalenderpfad.
- Python-Syntaxchecks erfolgreich.

**Breaking Change:** Nein.

---

## [2026-06-21] Fix: Chat-Zeitparser und natürliche Neuplanungsbefehle

**Status:** Merged
**Datum & Uhrzeit:** 2026-06-21 15:46
**Autor:** Ibrahim Danisman
**Commit:** `475da25`

### Zweck
Zeitänderungen mit zwei Uhrzeiten wurden falsch interpretiert. Außerdem sollten natürlich formulierte Neuplanungswünsche zuverlässig von reinen Vorschlagsanfragen unterschieden werden.

### Was wurde geändert
- Bei `verschiebe die Aktivität um 14 Uhr auf 16 Uhr` ist 14:00 jetzt die alte und 16:00 die neue Uhrzeit.
- Aktivitätsnamen mit einer einzelnen neuen Uhrzeit werden unterstützt.
- Explizite Zeiträume wie `von 18 bis 20 Uhr` werden erkannt.
- Die bisherige Aktivitätsdauer bleibt beim Verschieben erhalten; ohne gültige Dauer gelten 90 Minuten.
- Zeitkonflikte werden erkannt und freundlich gemeldet.
- Nach einer Änderung werden die Aktivitäten chronologisch sortiert.
- Optional können nachfolgende Aktivitäten gemeinsam nach hinten verschoben werden.
- Formulierungen wie `mach den Nachmittag später` werden unterstützt.
- Deutsche Ordnungszahlen wie `zweiter Tag` werden erkannt.

### Neuplanung und Vorschläge
- Eindeutige Befehle wie `generiere Tag 2 erneut`, `plane Tag 2 nochmal` oder `mach den zweiten Tag neu` ändern den Plan und synchronisieren den Kalender.
- Formulierungen wie `gib mir andere Vorschläge für Tag 2` oder `was kann ich an Tag 2 anders machen` zeigen nur Alternativen.
- Der Plan bleibt bei Vorschlagsanfragen unverändert, bis beispielsweise `nimm Vorschlag 2` bestätigt wird.

### Betroffene Dateien
- `reiseagent/agents/coordinator.py`

### Tests
- Sechs Zeitformulierungen erfolgreich geprüft.
- Konflikt, gleiche Uhrzeit, Bereichsverschiebung und Sortierung geprüft.
- Sieben Neuplanungsformulierungen geprüft.
- Sechs Vorschlagsformulierungen inklusive anschließender Übernahme geprüft.
- Python-Syntaxcheck erfolgreich.

**Breaking Change:** Nein.

---

## [2026-06-21] Fix: Telegram-Callbacks und Hintergrundthreads

**Status:** Merged
**Datum & Uhrzeit:** 2026-06-21 14:33
**Autor:** Ibrahim Danisman
**Commit:** `30bbacc`

### Zweck
Telegram-Callback-Daten mit zwei vollständigen UUIDs waren länger als das zulässige Limit. Navigation und Telegram-Polling konnten außerdem bei mehreren Startup-Aufrufen mehrfach gestartet werden.

### Was wurde geändert
- Telegram verwendet kurze Callback-Daten im Format `accept:<token>` beziehungsweise `reject:<token>`.
- Token, Aktion, Trip-ID und Proposal-ID werden unter `trip["telegram_callbacks"]` gespeichert.
- Verwendete oder ungültige Tokens werden freundlich behandelt und nach der Entscheidung entfernt.
- Fehler beim Telegram-Versand und Callback-Polling werden ohne Secrets protokolliert.
- Monitoring-, Navigation- und Telegram-Threads besitzen jeweils einen einfachen Einmal-Startschutz.
- Der verbliebene Mojibake-Rest im Bulletpoint-Regex von `coordinator.py` wurde korrigiert.
- `.env.example` wurde wiederhergestellt und um Telegram-/Flight-Konfiguration ergänzt.

### Betroffene Dateien
- `reiseagent/providers/telegram.py`
- `reiseagent/main.py`
- `reiseagent/store.py`
- `reiseagent/agents/coordinator.py`
- `reiseagent/.env.example`

### Tests
- Callback-Daten mit 18 Bytes erfolgreich geprüft.
- Token-Speicherung und Entfernung geprüft.
- Mehrfacher Startup-Aufruf erzeugte jeden Hintergrundthread nur einmal.
- Bulletpoints `-`, `*` und `•` wurden erkannt.
- `init_db()` und Python-Syntaxchecks erfolgreich.

**Breaking Change:** Nein.

---


## Changelog – Flugzeiten-Monitoring & Verspätungs-Replanning

**Datum & Uhrzeit:** 2026-06-21
**Autor:** Suhaib

- Weboberfläche erweitert:
    - Ein neues Eingabefeld für die Flugnummer wurde im Reiseplanungsformular hinzugefügt.
    - Die eingegebene Flugnummer wird zusammen mit den Reisedaten an das Backend gesendet und im Trip gespeichert.

- Flight-Provider erweitert:
    - `providers/flights.py` wurde ergänzt bzw. korrigiert.
    - Die Flugzeiten-API kann über `FLIGHT_API_URL` und `FLIGHT_API_KEY` aus der `.env` Datei konfiguriert werden.
    - Flugnummern werden normalisiert, z. B. `LH 1961` zu `LH1961`.
    - Es wurde ein Mock-Modus über `MOCK_FLIGHT_DELAY_MINUTES` eingebaut, um Flugverspätungen für Tests zu simulieren.
    - Die Rückgabe enthält jetzt Felder wie `delay_minutes`, `departure_delay_minutes`, `arrival_delay_minutes`, `scheduled_departure` und `estimated_departure`.

- Environment-Konfiguration ergänzt:
    - Neue `.env` Variablen eingeführt:
        - `FLIGHT_API_URL`
        - `FLIGHT_API_KEY`
        - `FLIGHT_API_AUTH_MODE`
        - `MONITORING_INTERVAL_SECONDS`
        - `MOCK_FLIGHT_DELAY_MINUTES`
    - Dadurch können echte API-Daten oder Mock-Daten für Demo-Tests verwendet werden.

- Monitoring-Agent erweitert:
    - Der Monitoring-Agent prüft nun regelmäßig die gespeicherte Flugnummer eines Trips.
    - Die Flugzeiten werden im Hintergrund über die Flight-API aktualisiert.
    - Das Monitoring läuft konfigurierbar alle 30 Minuten über `MONITORING_INTERVAL_SECONDS`.
    - Eine Verspätung wird erkannt, wenn `delay_minutes` mindestens 30 Minuten beträgt.
    - Die letzten Flugupdates werden im Trip gespeichert.

- Store/Trip-Daten erweitert:
    - Trips speichern nun zusätzliche Felder:
        - `flight_updates`
        - `last_flight_update`
        - `last_notified_flight_delay_minutes`
    - Dadurch kann nachvollzogen werden, wann der Flug zuletzt geprüft wurde und ob eine Verspätung bereits gemeldet wurde.

- Replanning bei Flugverspätung ergänzt:
    - Bei erkannter Flugverspätung wird automatisch ein neuer Reiseplan-Vorschlag erstellt.
    - Der erste Reisetag wird zeitlich an die Verspätung angepasst.
    - Der neue Vorschlag enthält:
        - Grund der Änderung
        - betroffene Tage
        - konkrete Änderungen im Tagesplan
        - Budget vor der Änderung
        - Budget nach der Änderung
        - Preisdifferenz zwischen altem und neuem Plan

- Telegram-Integration erweitert:
    - Bei einer relevanten Flugverspätung sendet der Reiseagent automatisch eine Telegram-Nachricht an den Nutzer.
    - Die Nachricht enthält:
        - Flugnummer
        - Reiseziel
        - Verspätung in Minuten
        - Preis des alten Plans
        - Preis des neuen Plans
        - Preisdifferenz
    - Inline-Buttons wurden ergänzt:
        - „Neuen Plan annehmen“
        - „Ablehnen“

- Telegram-Callback-Verarbeitung ergänzt:
    - Das Backend kann nun Telegram-Button-Klicks abfragen.
    - Wenn der Nutzer den neuen Plan akzeptiert, wird der vorgeschlagene Plan als aktiver Reiseplan übernommen.
    - Wenn der Nutzer ablehnt, wird der Vorschlag als abgelehnt markiert.
    - Bereits bearbeitete Vorschläge werden nicht erneut verarbeitet.

- Testbarkeit verbessert:
    - Manuelles Monitoring ist über Swagger/FastAPI testbar.
    - Mit `MOCK_FLIGHT_DELAY_MINUTES=60` kann eine Flugverspätung simuliert werden.
    - Dadurch kann der komplette Ablauf getestet werden:
      Flugnummer eingeben → Monitoring auslösen → Verspätung erkennen → neuen Plan erstellen → Telegram-Nachricht senden → Plan akzeptieren oder ablehnen.

---

## [2026-06-17] Fix: Zeichenkodierung in coordinator.py

**Status:** Merged  
**Datum & Uhrzeit:** 2026-06-17  
**Autor:** Valeriu

### Zweck
Behebung eines stillen Bugs, bei dem deutsche Sonderzeichen (ä, ö, ü) im Code als korrupte Zeichenfolgen gespeichert waren und dadurch sowohl die Nutzeranzeige als auch mehrere Chat-Erkennungsmuster nicht funktioniert haben.

### Was wurde geändert
- `reiseagent/agents/coordinator.py` — alle vorkommenden Zeichenfehler korrigiert

Konkret ersetzt:
- `Ã¼` → `ü` (betraf: `für`, `überschrieben`, `Wetterübersicht`, `verfügbar`, `Kurfürstendamm`)
- `Ã¤` → `ä` (betraf: `Aktivitäten`, `aktivität`, `geändert`)
- `Ã¶` → `ö` (betraf: `lösche` in Regex-Pattern)

### Warum
Die Datei wurde zu einem früheren Zeitpunkt mit falscher Zeichenkodierung gespeichert (UTF-8-Bytes als Latin-1 interpretiert). Das hat zwei Kategorien von Fehlern verursacht:
1. **Sichtbar:** Nutzer sahen in der UI korrumpierte Texte wie `"Wetterdaten fÃ¼r Rom"`.
2. **Funktional (still):** Regex-Muster wie `lÃ¶sche` haben nie mit Nutzereingaben gematcht, weil der korrupte String niemals im normalen Text vorkommt. Die Chat-Erkennung für Formulierungen wie "lösche Aktivität" war dadurch teilweise kaputt.

### Implementation & Impact
Drei globale Ersetzungen in `coordinator.py` mit `replace_all`. Kein Logik-Eingriff, nur Textkorrektur. Betroffene Regex-Pattern auf den Zeilen 780, 1085, 1088 funktionieren nach dem Fix korrekt und matchen jetzt tatsächlich Nutzereingaben mit Umlauten.

### Abhängigkeiten
- Nur `coordinator.py` betroffen
- Keine anderen Dateien angepasst
- Kein Breaking Change

---

## [2026-06-17] Migration: In-Memory Store → SQLite

**Status:** Merged  
**Datum & Uhrzeit:** 2026-06-17  
**Autor:** Valeriu

### Zweck
Reisedaten gingen bei jedem Server-Neustart verloren, weil sie nur im Arbeitsspeicher gespeichert wurden. Das Hintergrund-Monitoring (Wetter, Flüge, Navigation) war dadurch nach einem Neustart funktionslos, weil es keine Reisen mehr fand.

### Was wurde geändert

**`reiseagent/store.py`** — komplett neu geschrieben (~55 Zeilen):
- Globales `trips: dict = {}` entfernt
- SQLite-Datenbank `trips.db` eingeführt (eine Tabelle: `id TEXT`, `data TEXT`)
- Trip-Objekt wird als JSON-String gespeichert (`json.dumps`) und beim Lesen wiederhergestellt (`json.loads`)
- Neue Funktion `init_db()` erstellt die Tabelle beim ersten Start
- `check_same_thread=False` für Thread-Sicherheit (Monitoring-Thread greift parallel zu)

**`reiseagent/main.py`** — zwei Änderungen:
- Zeile 399: `for trip in store.trips.values()` → `for trip in store.list_trips()` (direkter Dict-Zugriff entfernt)
- `store.init_db()` beim Server-Start aufgerufen

**`reiseagent/streamlit_app.py`** — eine Änderung:
- `store.init_db()` nach dem Import aufgerufen, damit die DB auch existiert wenn Streamlit ohne FastAPI läuft

### Warum
- **Persistenz:** Trips überleben Server-Neustarts
- **Monitoring-Stabilität:** Der Hintergrund-Thread findet nach einem Neustart alle aktiven Reisen wieder
- **Prozess-Trennung:** Streamlit und FastAPI teilen jetzt dieselbe `trips.db`-Datei statt isolierter In-Memory-Dicts

### Implementation & Impact
Interface von `store.py` ist identisch geblieben (gleiche vier Funktionen: `create_trip`, `get_trip`, `update_trip`, `list_trips`). Dadurch mussten `monitoring.py` und alle Agenten nicht angepasst werden. Der einzige Breaking Point war der direkte Dict-Zugriff `store.trips.values()` in `main.py`, der explizit ersetzt wurde.

### Abhängigkeiten

| Datei | Art der Abhängigkeit |
|---|---|
| `main.py` | 16 Aufrufe auf store-Funktionen + 1 direkter Dict-Zugriff (gefixt) |
| `agents/monitoring.py` | 10 Aufrufe — kein Eingriff nötig |
| `streamlit_app.py` | 12 Aufrufe + init_db() ergänzt |
| `.gitignore` | Deckt `*.db` bereits ab — kein Eintrag nötig |

**Breaking Change:** Nein — Interface unverändert.  
**Datenverlust:** Bestehende In-Memory-Trips gehen bei der Migration einmalig verloren (erwartet).

### Test

1. Server starten: `uvicorn main:app` im Verzeichnis `reiseagent/`
2. Trip anlegen über `http://localhost:8000/docs` → `POST /api/trips/demo`
3. Server stoppen: `Ctrl + C`
4. Server neu starten: `uvicorn main:app`
5. Trip abrufen — entweder im Browser unter `http://localhost:8000/docs` → `GET /api/trips/{trip_id}` oder per Terminal:
```
curl http://localhost:8000/api/trips/756b2b1b-3014-4e59-9593-fc5b3d67fa82
```
→ Trip muss nach dem Neustart noch vollständig zurückkommen.

