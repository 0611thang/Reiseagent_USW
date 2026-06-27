# Implementierungsplan — Block E (Technische Schulden)

**Datum:** 21.06.2026
**Grundlage:** [TODO_2026-06-21.md](../Old%20Documentation%20-%20do%20not%20use/TODO_2026-06-21.md)
**Umfang:** E1 (Business-Logik aus `streamlit_app.py` auslagern)
**Zeitpunkt:** Ganz am Ende — erst nach C3, da dort ohnehin neue UI-Logik entsteht.

---

## E1 — Business-Logik aus `streamlit_app.py` auslagern

### Ziel
`streamlit_app.py` mischt aktuell UI-Rendering mit Business-Logik (Coordinator-Aufrufe, Store-Updates, Datentransformation). Die Logik in ein separates Modul `ui_service.py` ziehen. **Kein Framework-Wechsel — Streamlit bleibt.**

### Warum (und warum kein React-Rewrite)
Für ein Uni-Demo ist Streamlit die richtige Wahl: schnell, Python-nativ, kein Frontend-Stack nötig. Das Problem ist nicht das Framework, sondern dass `streamlit_app.py` ~1100 Zeilen mit vermischten Zuständigkeiten ist. Ein Rewrite nach React kostet Wochen ohne Mehrwert für die Demo. Sauberer Schnitt UI↔Logik löst die Wartbarkeit.

### Betroffene Dateien
- `reiseagent/streamlit_app.py` (~1100 Zeilen) → bleibt UI, ruft `ui_service`
- **Neu:** `reiseagent/ui_service.py`

### Kandidaten zum Auslagern (Logik, kein Rendering)
- `_send_chat_command_from_ui` (`:708-727`) — Coordinator-Aufruf + Store-Update + Session-Sync
- `load_demo_trip` (`:260-281`) — Trip-Erzeugung
- `sync_plan_and_notify` / Kalender-/Telegram-Sync-Aufrufe (im Form-Handler `:1023-1034`)
- Trip-Erstellung aus dem Formular (`:1012-1037`) — Request bauen, `store.create_trip`, `coordinator.handle_plan_request`, Persistenz
- Datentransformationen für Budget/Plan vor dem Rendern
- (nach C3) Kaskade-/Alternativen-Aufrufe

### Was in `streamlit_app.py` bleibt
- `st.*`-Aufrufe, Layout, CSS, `render_*`-Funktionen, Session-State-Handling
- Reine Darstellungs-Helfer (`_esc`, `_flight_time_label`, `_format_day_label`)

### Schritte
1. `ui_service.py` anlegen. Funktionen ohne `st.*` — sie nehmen Inputs, rufen `coordinator`/`store`/Provider, geben Ergebnisse zurück.
2. Logik-Blöcke nach und nach verschieben; in `streamlit_app.py` durch `ui_service.xyz(...)`-Aufrufe ersetzen.
3. **Session-State** (`st.session_state`) bleibt in `streamlit_app.py` — `ui_service` ist Streamlit-frei und damit unabhängig testbar.
4. **Schrittweise**, nach jeder verschobenen Funktion App testen (kein Big-Bang-Refactor).

### Edge Cases / Risiken
- Funktionen, die `st.session_state` lesen/schreiben, dürfen nicht 1:1 verschoben werden → Zustand als Parameter übergeben / Rückgabewert zurückschreiben.
- `st.rerun()`-Aufrufe bleiben in der UI-Schicht.
- Import-Zyklen vermeiden: `ui_service` importiert `coordinator`/`store`, **nicht** umgekehrt.
- Reiner Verschiebe-Refactor → **Verhalten muss identisch bleiben**. Vorher/nachher dieselben manuellen Checks.

### Verifikation
Kompletter Smoke-Test nach dem Refactor: Reise erstellen, Chat, Plan bearbeiten, Proposal annehmen, Kalender-/Telegram-Sync — alles wie vorher. Keine neue Funktionalität, nur Struktur.

### Aufwand
~3–4 h (schrittweise, mit Zwischentests).

---

## Definition of Done (Block E)
- [ ] `ui_service.py` existiert, enthält die Business-Logik
- [ ] `streamlit_app.py` enthält nur noch UI + Session-Handling + `ui_service`-Aufrufe
- [ ] `ui_service` ist Streamlit-frei (keine `st.*`-Aufrufe)
- [ ] Smoke-Test: identisches Verhalten wie vor dem Refactor

## Offene Entscheidungen
1. Ein `ui_service.py` oder feiner (z. B. `services/trip_service.py`, `services/plan_service.py`)? (Empfehlung: erst ein File, bei Bedarf splitten.)
2. Refactor erst nach C3 (empfohlen) oder vorher? Vorher bedeutet doppelte Arbeit, weil C3 neue Logik bringt.
