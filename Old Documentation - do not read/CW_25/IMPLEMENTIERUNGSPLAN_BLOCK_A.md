# Implementierungsplan — Block A (Quick Wins)

**Datum:** 21.06.2026
**Grundlage:** [TODO_2026-06-21.md](../Old%20Documentation%20-%20do%20not%20use/TODO_2026-06-21.md)
**Umfang:** A1 (Reiseübersicht), A2 (Datepicker), A3 (Telegram-Bug), A4 (Abflugzeit-Panel)
**Charakter:** UI-nah, geringes Risiko, keine LLM-/Provider-Änderungen. Idealer Einstieg.

---

## Reihenfolge & Aufwand

| Task |  | Risiko | Reihenfolge |
|---|---|---|---|
| A4 — Abflugzeit-Panel |  | sehr gering | 1. (reines Anzeigen, Daten da) |
| A1 — Reiseübersicht |  | gering | 2. |
| A2 — Datepicker |  | gering-mittel | 3. (berührt Planner-Datumslogik) |
| A3 — Telegram-Bug |  | mittel (Debugging) | 4. (isoliert, separat testbar) |

**Empfehlung:** A4 → A1 → A2 → A3. A4 und A1 sind UI-only. A2 fasst die Datumslogik im Planner an. A3 ist Debugging und sollte separat (eigener Branch/Commit) laufen.

---

## A4 — Abflugzeit im Flug-Panel anzeigen

### Ziel
Im Flug-Panel zusätzlich zur Ankunft auch die Abflugzeit zeigen (geplant + aktuell/geschätzt).

### Betroffene Datei
- `reiseagent/streamlit_app.py` → `render_flight_panel` (`:559-609`)

### Ausgangslage
Das Panel liest nur Ankunftsfelder (`:569-570`):
```python
scheduled = _flight_time_label(details.get("scheduled_arrival"))
current   = _flight_time_label(details.get("actual_arrival") or details.get("estimated_arrival"))
```
Die Abflugfelder existieren bereits in `flight_updates` (`providers/flights.py:168-170`): `scheduled_departure`, `estimated_departure`, `actual_departure`.

### Schritte
1. In `render_flight_panel` zwei neue Variablen ergänzen:
   ```python
   dep_scheduled = _flight_time_label(details.get("scheduled_departure"))
   dep_current   = _flight_time_label(details.get("actual_departure") or details.get("estimated_departure"))
   ```
2. Im HTML-Block (`:599-604`) eine Zeile **vor** der Ankunft einfügen:
   ```html
   <strong>Geplanter Abflug:</strong> {dep_scheduled} &nbsp;|&nbsp;
   <strong>Aktueller Abflug:</strong> {dep_current}<br>
   ```
3. Reihenfolge im Panel: Route → Abflug → Ankunft → Status.

### Edge Cases
- `_flight_time_label` (`:549`) liefert bei `None` bereits „Nicht verfügbar" — kein zusätzliches Handling nötig.
- Mock-Daten liefern Abflug = Ankunft − 3:15 h (`flights.py:26`), also immer befüllt.

### Verifikation
Demo-Reise mit Flugnummer laden → Panel zeigt Abflug + Ankunft. Mit `MOCK_FLIGHT_DELAY_MINUTES=60` in `.env` prüfen, dass „Aktueller Abflug" um 60 Min verschoben ist.

---

## A1 — Reiseübersicht auf der Startseite

### Ziel
Liste aller gespeicherten Reisen anzeigen. User kann eine auswählen → wird zum aktiven Trip (Details, Status, Umplanung).

### Betroffene Datei
- `reiseagent/streamlit_app.py` → neue Funktion `render_trip_overview()`, Aufruf in `main()` (`:959`)

### Ausgangslage
- `main()` rendert nur den **einen** aktiven Trip aus `st.session_state.trip_id` (`get_current_trip`, `:254-257`).
- `store.list_trips()` (`store.py:71`) liefert **alle** Trips aus SQLite.
- Trip-Auswahl läuft über `st.session_state.trip_id` + `st.rerun()` (Muster wie bei Demo-Reise, `:1035-1037`).

### Schritte
1. **Neue Funktion** `render_trip_overview()`:
   ```python
   def render_trip_overview():
       trips = store.list_trips()
       if not trips:
           return
       st.markdown("---")
       st.markdown("### 📋 Deine Reisen")
       for trip in trips:
           req = trip.get("request", {})
           plan = trip.get("active_plan") or {}
           dest = req.get("destination", "Unbekannt")
           status = plan.get("status", "kein Plan")
           # Datum: aus plan.days[0].date wenn vorhanden, sonst request
           cols = st.columns([3, 2, 2, 1])
           cols[0].write(f"**{dest}**")
           cols[1].caption(f"{req.get('duration_days', '?')} Tage")
           cols[2].caption(f"Status: {status}")
           is_active = trip["id"] == st.session_state.trip_id
           label = "Aktiv" if is_active else "Öffnen"
           if cols[3].button(label, key=f"open_trip_{trip['id']}", disabled=is_active):
               st.session_state.trip_id = trip["id"]
               st.session_state.chat_messages = trip.get("chat_messages", [])
               st.rerun()
   ```
2. **Aufruf in `main()`**: am Ende der Funktion, nach dem aktiven Trip-Rendering. Zwei Fälle:
   - Kein aktiver Trip (`:1041-1045`): Übersicht **statt/zusätzlich** zum Info-Hinweis zeigen.
   - Aktiver Trip vorhanden: Übersicht **unten** anhängen (nach dem Navigation-Block, ~`:1100+`).
3. Beim Wechsel `chat_messages` aus dem gewählten Trip in die Session laden (sonst zeigt der Chat die Nachrichten des vorigen Trips).

### Designhinweis (optional, leichtgewichtig)
Jede Reise als `.card` rendern (CSS existiert, `:33`) statt nackter Columns — visuell konsistent mit dem Rest.

### Edge Cases
- Trip ohne `active_plan` → Status „kein Plan", Öffnen trotzdem erlauben (zeigt dann die Warnung `:1052`).
- Demo-Trips und echte Trips landen beide in `trips.db` → erscheinen alle. Bei Bedarf später Filter/Löschen ergänzen (nicht Teil von A1).

### Verifikation
2–3 Reisen anlegen → alle erscheinen in der Liste → „Öffnen" wechselt korrekt, Chat & Plan passen zum gewählten Trip.

---

## A2 — Datepicker + Tagesstart-Zeit

### Ziel
Start- und Enddatum per Datepicker wählen. Dauer automatisch berechnen. **`departure_date` ins Request schreiben** (Voraussetzung für C1). Zusätzlich: optionaler **Tagesstart-Picker** — der User legt fest, um wie viel Uhr die erste Aktivität beginnt. Dieser Wert gilt als Standard für **alle Tage**; Tag 1 wird bei vorhandener Flugnummer davon durch die echte Ankunftszeit überschrieben (→ C2).

**Konzept Abflugdatum vs. Ankunftsort-Datum:** Der User wählt das Datum, ab dem er *am Zielort* ist. Es wird davon ausgegangen, dass er am Startdatum anreist. Die Flugnummer dient nur dem Monitoring und dem Planner-Kontext (Anreise-Puffer) — nicht zur Datumsberechnung.

### Betroffene Dateien
- `reiseagent/streamlit_app.py` → `plan_form` (`:992-1037`)
- `reiseagent/agents/planning.py` → `create_plan` (`:24-67`), Konstante `start_date` (`:29`)

### Ausgangslage
- Formular nutzt `dur = st.slider("Tage", 1, 14, 3)` (`:996`), kein Datum, keine Startzeit.
- `create_plan` setzt `start_date = date.today()` **hartkodiert** (`planning.py:29`) → Plan-Tage zählen ab heute, ignorieren echtes Reisedatum.
- `flights.py` erwartet `departure_date` im Request (`_build_aviationstack_params:76`, `_mock_flight_updates:19`).

### Schritte
1. **Formular umbauen** (`:994-996`) — Datum + Tagesstart:
   ```python
   from datetime import date, time, timedelta
   col_date1, col_date2, col_time = st.columns(3)
   with col_date1:
       start = st.date_input("Startdatum (Anreise)", value=date.today() + timedelta(days=1))
   with col_date2:
       end = st.date_input("Enddatum (Abreise)", value=date.today() + timedelta(days=4))
   with col_time:
       day_start = st.time_input("Tagesstart (alle Tage)", value=time(9, 0))
   ```
   `dur`-Slider entfernen.

2. **Validierung + Dauer berechnen** (vor `req`-Aufbau, `:1013`):
   ```python
   if end < start:
       st.error("Enddatum muss nach dem Startdatum liegen.")
       st.stop()
   dur = (end - start).days + 1
   ```

3. **Request erweitern** (`:1013-1022`):
   ```python
   "duration_days": dur,
   "start_date": start.isoformat(),
   "departure_date": start.isoformat(),   # für Flug-API & C1
   "day_start_time": day_start.strftime("%H:%M"),  # Standard-Tagesstart für C2
   ```

4. **`create_plan` anpassen** (`planning.py:29`):
   ```python
   start_date_str = request.get("start_date")
   start_date = date.fromisoformat(start_date_str) if start_date_str else date.today()
   ```
   Rest (`:62`, `date = start_date + timedelta(...)`) bleibt → Plan-Tage tragen jetzt echte Reisedaten.

### Edge Cases
- `duration_days` bleibt als abgeleiteter Wert erhalten → kein Bruch bei bestehenden Stellen (`coordinator.py:1575/1599`, `monitoring`, etc.).
- `departure_date` muss `YYYY-MM-DD` sein (Aviationstack-Format) → `.isoformat()` liefert das korrekt.
- `day_start_time` wird in C2 für die 3-stufige Fallback-Kette genutzt: Flug-Ankunft → `day_start_time` → `"09:00"`. Ist der Wert nicht im Request (Altdaten), greift der Default 09:00 automatisch.

### Verifikation
- Reise „15.–19. Juli, Tagesstart 10:00" anlegen → Plan hat `duration_days=5`, Tag 1 trägt 15. Juli, Folgetage +1.
- Ohne Flugnummer: alle Tage starten 10:00.
- Mit Flugnummer: Tag 1 startet nach Flugankunft + Puffer (→ C2), Tage 2+ starten 10:00.

---

## A3 — Telegram Accept/Reject Button reparieren

### Ziel
Inline-Buttons funktionieren zuverlässig. Buttons nur bei echtem Replanning (Wetter/Flugverspätung). User bestätigt/lehnt in Telegram ab.

### Betroffene Dateien
- `reiseagent/main.py` → Thread-Start (`:60-85`), `_telegram_callback_loop` (`:474-521`)
- `reiseagent/providers/telegram.py` → `get_recent_messages` (`:99`), `get_callback_updates` (`:214`), `send_flight_delay_proposal` (`:133`)
- `reiseagent/.env` → `TELEGRAM_BOT_TOKEN`

### Zwei wahrscheinliche Ursachen (in dieser Reihenfolge prüfen)

**Ursache 1 — Backend läuft nicht.**
Die Callback-Verarbeitung lebt in einem FastAPI-Background-Thread (`main.py:81-85`, gestartet via `@app.on_event("startup")`). Streamlit (`streamlit_app.py`) und FastAPI (`main.py`) sind **getrennte Prozesse**, die sich nur `trips.db` teilen — Streamlit ruft das Backend **nicht** per HTTP. Läuft nur `streamlit run`, wird **kein** Button verarbeitet.
→ **Prüfen:** Läuft `uvicorn main:app`? Ist `TELEGRAM_BOT_TOKEN` in `.env` gesetzt? (`send_message:35` und alle Telegram-Calls returnen sonst still `False`.)
→ **Fix/Doku:** Sicherstellen, dass für Telegram-Features **beide** Prozesse laufen. In README/Start-Befehlen klar dokumentieren.

**Ursache 2 — getUpdates-Konflikt (Telegram 409).**
Telegram erlaubt **nur einen** aktiven `getUpdates`-Consumer pro Bot. Aktuell pollen **zwei** Stellen:
- `_telegram_callback_loop` → `get_callback_updates` (Long-Poll mit Offset, `telegram.py:214`)
- Profil-Endpoint → `get_recent_messages` (zweiter `getUpdates`-Call ohne Offset, `telegram.py:99`, aufgerufen in `main.py:347`)

Laufen beide, liefert Telegram `409 Conflict` und/oder „stiehlt" sich Updates → Buttons reagieren nicht.
→ **Fix (sauber):** **Einen einzigen** `getUpdates`-Consumer (`_telegram_callback_loop`). Dieser verarbeitet sowohl `callback_query` als auch normale Messages und legt eingehende Messages für das Profil-Lernen in einem Puffer ab (In-Memory-Liste oder DB-Tabelle). `get_recent_messages` liest dann aus diesem Puffer statt selbst `getUpdates` zu rufen.
→ **Fix (minimal, falls Zeit knapp):** `allowed_updates` im Callback-Loop auf `["callback_query"]` belassen und `get_recent_messages` nur **manuell/selten** aufrufen, **nie** während der Loop pollt. Pragmatisch für Demo, aber nicht robust.

### Schritte
1. `.env` prüfen: `TELEGRAM_BOT_TOKEN` gesetzt? Bot in der Gruppe (`DEFAULT_CHAT_ID`, `telegram.py:8`)?
2. `uvicorn main:app` starten, Logs beobachten: erscheint `[telegram_callback] ... gestartet` (`main.py:85`)? Erscheinen `409`-Fehler (`telegram.py:239`)?
3. Replanning auslösen: `.env` `MOCK_FLIGHT_DELAY_MINUTES=60` setzen, Monitoring laufen lassen → `send_flight_delay_proposal` sollte Nachricht + Buttons senden (`telegram.py:194-208`).
4. Button klicken → in den Logs `_telegram_callback_loop` (`:474`) prüfen: kommt `callback_query` an? Wird Token in `_find_telegram_callback` (`main.py:413`) gefunden?
5. Den getUpdates-Konflikt gemäß „Fix (sauber)" beheben.
6. **Trigger-Bedingung absichern:** Buttons nur bei Replanning. Aktuell korrekt verdrahtet — `send_flight_delay_proposal` wird nur in `monitoring._refresh_flights` bei `delay >= 30` aufgerufen (`monitoring.py:252-278`). Sicherstellen, dass kein anderer Pfad Buttons sendet. Für Wetter-Replanning prüfen, ob eine analoge Telegram-Benachrichtigung gewünscht ist (aktuell nur Flug → ggf. ergänzen).

### Edge Cases
- Token läuft ab / Trip gelöscht → `_find_telegram_callback` gibt `None`, Loop antwortet „Button nicht mehr gültig" (`main.py:497-500`). Verhalten ok.
- Doppelklick: nach Verarbeitung werden Tokens entfernt (`_remove_telegram_callbacks`, `main.py:515`) → zweiter Klick sauber abgefangen.

### Verifikation
Künstliche Flugverspätung → Telegram-Nachricht mit zwei Buttons → „Annehmen" → Proposal-Status wird `accepted` (`main.py:449-450`), Plan aktualisiert, Telegram-Callback-Antwort erscheint. Logs ohne `409`.

---

## Definition of Done (Block A)
- [ ] A4: Abflug + Ankunft im Flug-Panel sichtbar
- [ ] A1: Alle Reisen unten gelistet, Auswahl wechselt aktiven Trip inkl. Chat
- [ ] A2: Datepicker statt Slider, `start_date`/`departure_date` im Request, Plan trägt echte Reisedaten
- [ ] A3: Button-Klick verarbeitet Proposal, kein getUpdates-409, Trigger nur bei Replanning
- [ ] Manuelle Verifikation aller vier Punkte mit Demo-Reise durchgeführt

## Offene Entscheidungen für die Umsetzung
1. **A1:** Reisen löschen/archivieren — jetzt mitnehmen oder später? (Empfehlung: später, eigener Task.)
2. **A2:** Separate Abflug-**Uhrzeit** (time_input) jetzt schon, oder reicht Datum bis C1? (Empfehlung: Datum reicht, Uhrzeit kommt aus Flight-API.)
3. **A3:** „Fix sauber" (ein getUpdates-Consumer) vs. „Fix minimal" — abhängig von verbleibender Zeit vor Abgabe.
