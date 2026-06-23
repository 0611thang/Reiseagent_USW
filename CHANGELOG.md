# Changelog — Reiseplanungsagent

Alle Änderungen am Projekt werden hier dokumentiert.  
Sortierung: **neueste Einträge oben**.

---

## [2026-06-21] Feature: UI-Polish, Reiseverwaltung und Kalender-Bereinigung

**Status:** Merged  
**Datum & Uhrzeit:** 2026-06-21 11:58  
**Autor:** Ibrahim Danisman  
**Commit:** `5d34658`

### Zweck
Die Streamlit-Oberfläche sollte übersichtlicher und präsentationstauglicher werden. Außerdem sollten gespeicherte Reisen besser verwaltet werden können und beim Löschen einer Reise auch die zugehörigen Reiseagent-Kalendereinträge entfernt werden.

### Was wurde geändert
- Der Reiseassistent ist prominenter sichtbar und kann auch vor der Reiseplanung genutzt werden.
- Die Reiseübersicht „Deine Reisen“ wurde kompakter gestaltet.
- Gespeicherte Reisen können geöffnet und mit Sicherheitsabfrage gelöscht werden.
- Beim Löschen einer Reise werden eindeutig zugehörige Reiseagent-Kalendereinträge entfernt.
- Neue Kalender-Einträge enthalten einen eindeutigen Reiseagent-Marker mit `trip_id`, Reiseziel und Reisedatum.
- In der Reiseübersicht wird eine vorhandene Flugnummer angezeigt.
- Die Personenanzahl richtet sich nach der Reiseart: Solo = 1, Paar/Familie/Gruppe mindestens 2.
- Flugnummern sind bei eigenen Reisen optional und nicht mehr automatisch vorausgefüllt.
- Statusmeldungen zeigen nur noch die neueste Meldung prominent; ältere Meldungen bleiben ausklappbar.
- Alte sichtbare Vorschlags- und Profil-Blöcke wurden aus der Oberfläche entfernt.

### Planansichten und Aktivitätsbearbeitung
- Der Tagesplan bietet drei Ansichten: Detail, Kompakt und Kalender/Timeline.
- Aktivitäten können direkt im Reiseplan bearbeitet werden.
- Bearbeitungsoptionen wie Zeit ändern, Löschen, Alternative und KI-Alternative sind nicht mehr dauerhaft sichtbar.
- Zeitänderungen verschieben nachfolgende Aktivitäten dynamisch.
- Bei unplausiblen Zeitänderungen oder Überschneidungen wird gewarnt.
- Alternative und KI-Alternative bleiben an die bestehende Planlogik angebunden.

### Flug- und Ankunftslogik
- Fehlerhafte Flugrouten wie `Nicht verfügbar → Nicht verfügbar` werden vermieden.
- Das Flugpanel zeigt verfügbare Flugdetails sauberer an.
- Der Ankunftstag wird nach Flugankunft sinnvoller geplant.
- Wenn nach Ankunft und Check-in genug Zeit bleibt, wird eine leichte Aktivität ergänzt.

### Kalender-Verhalten
- Beim Löschen einer Reise werden nur Kalendereinträge mit passender `trip_id` gelöscht.
- Alte Kalendereinträge ohne `trip_id` werden nur gelöscht, wenn sie sicher als Reiseagent-Einträge erkannt werden.
- Fremde Kalendertermine und Einträge anderer Reisen bleiben erhalten.
- Wenn Google Calendar nicht eingerichtet ist, wird die Reise trotzdem aus SQLite gelöscht und eine verständliche Meldung angezeigt.

### Betroffene Dateien
- `reiseagent/streamlit_app.py`
- `reiseagent/store.py`
- `reiseagent/ui_service.py`
- `reiseagent/providers/calendar.py`
- `reiseagent/providers/flights.py`
- `reiseagent/agents/coordinator.py`
- `reiseagent/main.py`

### Tests
- Python-Syntaxcheck erfolgreich.
- `git diff --check` erfolgreich.
- Detail-, Kompakt- und Kalenderansicht geprüft.
- Reise öffnen und Löschen mit Sicherheitsabfrage geprüft.
- Session-Bereinigung nach Löschen der aktiven Reise geprüft.
- Planaktionen wie Löschen, Zeitänderung und Alternative mit lokalen Mocks geprüft.
- Sicherer Calendar-Mock bestätigt: Nur passende Reiseagent-Einträge werden gelöscht.
- Fehlende Google-Calendar-Konfiguration blockiert das Löschen aus SQLite nicht.

**Breaking Change:** Nein.
---

## [2026-06-22] Refactor: Block E1 — Business-Logik aus streamlit_app.py ausgelagert

**Status:** Merged  
**Datum & Uhrzeit:** 2026-06-22  
**Autor:** Valeriu  

### Zweck
`streamlit_app.py` (~1200 Zeilen) mischte UI-Rendering mit Business-Logik. Die Logik-Blöcke wurden in ein neues, Streamlit-freies Modul `ui_service.py` verschoben, damit `streamlit_app.py` nur noch UI und Session-Handling enthält.

### Was wurde geändert

**`ui_service.py` (neue Datei):**
- `create_trip(req)` — erstellt einen Trip, ruft `coordinator.handle_plan_request` auf, speichert Ergebnis im Store. Gibt `(trip_id, active_plan)` zurück.
- `create_demo_trip()` — dasselbe mit fest eingebautem Berlin-Demo-Request und `use_mock_weather=True`. Gibt `(trip_id, active_plan)` zurück.
- `send_chat_command(trip, prompt, chat_messages)` — hängt User- und Assistenten-Nachricht an die übergebene `chat_messages`-Liste, ruft `coordinator.handle_chat_message` auf, speichert alles im Store. Gibt das Coordinator-Ergebnis zurück. Kein `st.*` — die Liste aus `st.session_state` wird direkt übergeben und durch Python list-by-reference mutiert.

**`streamlit_app.py` — drei Stellen vereinfacht:**
- `load_demo_trip`: von 13 auf 4 Zeilen — ruft jetzt `ui_service.create_demo_trip()`, setzt danach nur noch Session-State und `sync_plan_and_notify`.
- `_send_chat_command_from_ui`: von 15 auf 7 Zeilen — ruft `ui_service.send_chat_command()`, kümmert sich danach nur noch um `add_status` und Session-State-Updates.
- Form-Handler (Trip-Erstellung): von 12 auf 5 Zeilen — ruft `ui_service.create_trip()`, setzt danach nur noch Session-State.
- `ui_service` importiert.

**Bewusst nicht ausgelagert:**
- `sync_plan_and_notify` — ruft `add_status` (Session-State) direkt, ist nur 4 Zeilen, kein Gewinn.
- Datentransformationen — zu vage, zu geringes Risiko-Nutzen-Verhältnis (laut Plan-Entscheidung).

### Betroffene Dateien
- `reiseagent/ui_service.py` (neu)
- `reiseagent/streamlit_app.py`

### Tests
- Syntax-Check erfolgreich: `python -c "import ui_service; import streamlit_app; print('OK')"` → `OK`.
- Verhalten identisch zu vorher — reiner Verschiebe-Refactor, keine neue Funktionalität.

**Breaking Change:** Nein — Verhalten unverändert, nur Struktur.

---

## [2026-06-22] Feature: Block B3 / D — IMAP Provider, Profil-Lerner, Interessen-basierte Reiseplanung

**Status:** Merged  
**Datum & Uhrzeit:** 2026-06-22  
**Autor:** Valeriu  

### Zweck
Den Profil-Strang vollständig umsetzen: web.de-Postfach per IMAP auslesen (B3), Interessen daraus extrahieren und im Profil speichern (D1), und das gespeicherte Profil automatisch beim Erstellen neuer Reisen einbeziehen (D2).

### Was wurde geändert

**B3 — IMAP Provider (`providers/imap_mail.py`, neue Datei):**
- Neuer Provider liest das web.de-Postfach (`usw_reiseplaner@web.de`) via `imaplib` (Python-Standardbibliothek, kein neues Dependency).
- `_decode()` handhabt Umlaut-Encodings korrekt via `email.header.decode_header`.
- `_extract_snippet()` zieht zuerst `text/plain`, Fallback `text/html` mit grobem Tag-Strip.
- Nicht konfiguriert (`IMAP_USER`/`IMAP_PASSWORD` leer) → gibt `[]` zurück — fail-silent wie `gmail.py`.
- Ausgabeformat `{subject, from, snippet}` ist identisch zu Gmail → `profile_learner.py` braucht keinen Umbau.
- `.env.example` um IMAP-Variablen ergänzt (`IMAP_HOST`, `IMAP_PORT`, `IMAP_USER`, `IMAP_PASSWORD`) mit Hinweis auf App-Passwort (nicht das Login-Passwort).

**D1 — Profil-Lerner erweitert (`agents/profile_learner.py`, `main.py`):**
- Neue Funktion `learn_from_imap(emails)` in `profile_learner.py` — ruft intern `learn_from_gmail`-Logik wieder, nur mit `source="imap"`. Kein doppelter Code.
- `run_profile_update()` hat neuen Parameter `imap_emails=None` — verarbeitet IMAP-Mails zusätzlich zu Telegram und Gmail.
- `/api/profile/update`-Endpoint in `main.py` ruft jetzt `get_imap_emails(limit=20)` auf und übergibt sie an `run_profile_update`.

**D2 — Interessen-basierte Reiseerstellung (`agents/coordinator.py`):**
- `handle_plan_request` lädt vor dem Planen `profile_store.get_top_interests(limit=5)`.
- Neue Mapping-Tabelle `PROFILE_TO_INTEREST` übersetzt Profil-Kategorien (z.B. `"kunst"`) in Formular-Labels (z.B. `"Museen"`), die `recommendation.py` versteht.
- Profil-Labels werden ohne Duplikate zu den Formular-Interessen hinzugefügt.
- Leeres Profil → Verhalten identisch zu vorher, kein Bruch.
- Der Coordinator-Insight zeigt an, welche Profil-Interessen eingeflossen sind (z.B. „Profil ergänzt: Museen, Natur.").

### Betroffene Dateien
- `reiseagent/providers/imap_mail.py` (neu)
- `reiseagent/agents/profile_learner.py`
- `reiseagent/main.py`
- `reiseagent/agents/coordinator.py`
- `reiseagent/.env.example`

### Tests
- Syntax-Check aller geänderten Dateien erfolgreich (`python -c "from providers.imap_mail import get_recent_emails; from agents.profile_learner import learn_from_imap; from agents import coordinator; print('OK')"` → `OK`).
- IMAP nicht konfiguriert → `get_recent_emails()` gibt `[]` zurück, kein Crash.
- Leeres Profil → `handle_plan_request` läuft unverändert durch.

**Breaking Change:** Nein — alle neuen Parameter sind optional, bestehende Aufrufe unverändert.

---

## [2026-06-22] Feature: Block C — Dynamischer Reiseplan, Flug-Monitoring-Zeitsteuerung, Aktivitätskarten

**Status:** Merged  
**Datum & Uhrzeit:** 2026-06-22  
**Autor:** Valeriu  

### Zweck
Block C setzt die drei Kern-Features des Projekts um: intelligente Flug-Monitoring-Zeitsteuerung (C1), dynamisch getakteter Reiseplan mit echten Dauern und Fahrtzeiten statt fixer Zeitfenster (C2), sowie ein interaktives Aktivitätskarten-System mit 3-Button-Bearbeitung direkt im Plan (C3).

### Was wurde geändert

**C1 — Intelligente Flug-Monitoring-Zeitsteuerung:**
- Neue Funktion `required_interval_seconds(trip)` in `monitoring.py`: berechnet das nötige Prüf-Intervall abhängig von der Zeit bis Abflug — alle 15 Min (≤2h), stündlich (≤6h), alle 6h (≤24h), oder `None` (noch nicht prüfen / kein Flug).
- `_monitoring_loop` in `main.py` komplett umgebaut: schläft jetzt immer 60 Sekunden. Wetter läuft weiterhin auf dem alten `MONITORING_INTERVAL_SECONDS`-Intervall für alle aktiven Trips. Flüge werden pro Trip individuell geprüft — nur wenn `required_interval_seconds` einen Wert zurückgibt und genug Zeit seit `last_flight_update` vergangen ist.

**C2 — Dynamischer Reiseplan (Variante A — deterministisch):**
- `DAY_SLOTS` (4 fixe Zeitfenster) entfernt.
- Neue Konstante `DURATION_BY_CATEGORY` gibt realistische Dauern pro Aktivitätskategorie (z.B. Museum 120 Min, Restaurant 75 Min, Park 60 Min).
- Neue Funktion `_get_travel_minutes(from, to)`: fragt OpenRouteService für Fußweg zwischen zwei Aktivitäten ab. Fallback 20 Min wenn kein ORS-Key oder keine Koordinaten vorhanden.
- `create_plan` taktet Aktivitäten jetzt dynamisch: `Start → +Dauer → +Fahrtzeit → nächste Aktivität`. Tagesstart kommt aus `request.day_start_time` (gesetzt durch A2-Picker), Fallback `09:00`.
- Slot-Objekte erhalten neues Feld `travel_to_next_minutes` (für C3-Kaskade und UI-Anzeige).
- Hilfsfunktionen `_time_to_minutes` und `_minutes_to_time` für die Zeitrechnung.
- Ausgabeformat (`start_time`, `end_time`, `activity`, `notes`) ist identisch zum alten Format — kein Bruch für bestehende Konsumenten.

**C3 — Aktivitätskarten mit 3-Button-System:**
- `render_plan_actions` komplett neu geschrieben. Alter Expander mit Dropdown-Auswahl entfernt.
- Pro Aktivität eine Zeile mit: editierbarem Zeitpicker + „✓ Zeit"-Button, Name + Fahrtzeit-Caption, Löschen-Button (🗑️), „Alt."-Button, „KI-Alt."-Button.
- **Zeit ändern:** sendet Chat-Befehl an den Coordinator (`"plane {name} auf HH:MM Uhr an Tag X"`). Kaskade der Folge-Aktivitäten wird vom Coordinator intern gehandhabt.
- **Löschen:** sendet `"lösche {name} an Tag X"` direkt an den Coordinator.
- **Alternative:** klappt Alternativen gleicher Kategorie inline unter der Karte auf (nicht im Chat). Aktivitäten werden aus gecachtem `all_activities` gefiltert. „Wählen" ersetzt die Aktivität per Chat-Befehl.
- **KI-Alternative:** liest `profile_store.get_top_interests()`. Kein Profil → Hinweis „verbinde deine E-Mails". Mit Profil → Aktivitäten nach Keyword-Treffern gerankt, Top 3 mit Begründung angezeigt.
- Toggle-Logik: Alt. und KI-Alt. öffnen/schließen per `st.session_state`. Wenn einer aufklappt, schließt der andere automatisch.
- `all_activities` wird einmal pro Trip in `st.session_state` gecacht — kein erneuter API-Aufruf bei jedem Render.
- `profile_store` neu importiert in `streamlit_app.py`.

### Betroffene Dateien
- `reiseagent/agents/monitoring.py`
- `reiseagent/main.py`
- `reiseagent/agents/planning.py`
- `reiseagent/streamlit_app.py`

### Tests
- Syntax-Checks für alle vier Dateien erfolgreich.
- C1: Loop prüft Trips mit Flugnummer individuell; Trips ohne Flugnummer werden übersprungen.
- C2: Plan trägt variable Startzeiten; ohne ORS-Key greift Fallback 20 Min, kein Crash.
- C3: Alt.-Bereich klappt auf/zu; KI-Alt. zeigt Leerzustand wenn kein Profil vorhanden.

**Breaking Change:** Nein — `time_slots`-Format identisch, `travel_to_next_minutes` ist additiv.

---

## [2026-06-22] Feature: Block A — Reiseübersicht, Datepicker, Tagesstart, Abflugzeit

**Status:** Merged  
**Datum & Uhrzeit:** 2026-06-22  
**Autor:** Valeriu  

### Zweck
Vier UI-nahe Verbesserungen aus Block A des Implementierungsplans umsetzen: Abflugzeit im Flug-Panel anzeigen (A4), alle gespeicherten Reisen auf der Startseite listen (A1), Datepicker + Tagesstart-Picker statt Tage-Slider einführen (A2). A3 (Telegram-Bug) wurde bewusst nicht angefasst.

### Was wurde geändert

**A4 — Abflugzeit im Flug-Panel:**
- `render_flight_panel` zeigt jetzt zusätzlich zur Ankunft auch die Abflugzeit an (geplant + aktuell/geschätzt).
- Die Felder `scheduled_departure`, `estimated_departure`, `actual_departure` waren bereits in `flight_updates` vorhanden — es fehlte nur die Anzeige.
- Reihenfolge im Panel: Route → Abflug → Ankunft → Status.

**A1 — Reiseübersicht auf der Startseite:**
- Neue Funktion `render_trip_overview()` listet alle gespeicherten Reisen aus SQLite (`store.list_trips()`).
- Jede Reise zeigt: Ziel, Dauer, Startdatum, Status.
- „Öffnen"-Button wechselt den aktiven Trip und lädt den zugehörigen Chat-Verlauf.
- Wird an zwei Stellen aufgerufen: wenn kein Trip aktiv ist, und am Ende der Seite unter dem aktiven Trip.

**A2 — Datepicker + Tagesstart statt Tage-Slider:**
- Slider „Tage" entfernt. Stattdessen: Datepicker für Start- und Enddatum, `time_input` für Tagesstart.
- `duration_days` wird automatisch aus der Datumsdifferenz berechnet.
- Request enthält jetzt `start_date` (für Plan-Datumsangaben), `departure_date` (für Flight-API & C1), `day_start_time` (Standard-Startzeit für alle Tage, Basis für C2-Fallback-Kette).
- `planning.create_plan` liest `start_date` aus dem Request statt `date.today()` zu verwenden — Plan-Tage tragen jetzt echte Reisedaten.
- Validierung: Fehlermeldung wenn Enddatum vor Startdatum liegt.

### Betroffene Dateien
- `reiseagent/streamlit_app.py`
- `reiseagent/agents/planning.py`

### Tests
- Syntax-Checks für beide Dateien erfolgreich (`python -c "import streamlit_app"`, `python -c "from agents import planning"`).
- Flug-Panel: Mock-Reise → Abflug + Ankunft sichtbar.
- Reiseübersicht: mehrere Trips → alle gelistet, „Öffnen" wechselt aktiven Trip.
- Datepicker: Reise 15.–19. Juli → `duration_days=5`, Tag 1 trägt 15. Juli, Folgetage +1.

**Breaking Change:** Nein — `duration_days` bleibt erhalten, bestehende Trips ohne `start_date` fallen auf `date.today()` zurück.

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

