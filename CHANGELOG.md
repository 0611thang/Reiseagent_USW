# Changelog — Reiseplanungsagent

Alle Änderungen am Projekt werden hier dokumentiert.  
Sortierung: **neueste Einträge oben**.

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
