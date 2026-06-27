# Implementierungsplan — Block C (Core Features)

**Datum:** 21.06.2026
**Grundlage:** [TODO_2026-06-21.md](../Old%20Documentation%20-%20do%20not%20use/TODO_2026-06-21.md)
**Umfang:** C1 (Flug-Monitoring-Zeitsteuerung), C2 (Dynamischer Plan ★ Kern), C3 (Aktivitätskarten + 3 Buttons)

> **Wichtigster Block.** C2 ist das Herzstück. C1 ist klein und unabhängig. C3 baut auf C2 + D1 auf.

---

## C1 — Intelligente Flug-Monitoring-Zeitsteuerung

### Ziel
Statt fix alle 30 Min: Prüf-Intervall abhängig von der Zeit bis Abflug.
- > 24 h vor Abflug: alle **6 h**
- ≤ 6 h vor Abflug: alle **1 h**
- ≤ 2 h vor Abflug: alle **15 min**
- außerhalb (kein Abflug bekannt / lange vorbei): nicht prüfen

### Betroffene Dateien
- `reiseagent/main.py` → `_monitoring_loop` (`:50-57`), `MONITORING_INTERVAL_SECONDS` (`:44`)
- `reiseagent/agents/monitoring.py` → ggf. neue Helfer-Funktion `seconds_until_next_check(trip)`
- Nutzt `departure_date` aus dem Request (kommt aus **A2**) bzw. `scheduled_departure` aus `flight_updates`.

### Ausgangslage
`_monitoring_loop` ruft stur `monitor_all_active_trips()` und schläft `MONITORING_INTERVAL_SECONDS` (Default 1800). Keine Abhängigkeit von der Abflugzeit.

### Schritte
1. **Helfer in `monitoring.py`** — bestimmt den nötigen Intervall pro Trip:
   ```python
   def required_interval_seconds(trip) -> int | None:
       dep = _departure_datetime(trip)   # aus flight_updates.scheduled_departure
       if not dep:                       # Fallback: request.departure_date 00:00
           dep = _departure_from_request(trip)
       if not dep:
           return None                   # nichts zu prüfen
       hours_until = (dep - datetime.now()).total_seconds() / 3600
       if hours_until < -3:              # Flug deutlich vorbei
           return None
       if hours_until <= 2:
           return 15 * 60
       if hours_until <= 6:
           return 60 * 60
       if hours_until <= 24:
           return 6 * 3600
       return None                       # mehr als 24h hin -> noch nicht starten
   ```
2. **Pro-Trip-Scheduling.** Statt globalem Sleep: in jeder Loop-Runde je Trip prüfen, ob seit `last_flight_update` genug Zeit vergangen ist. Einfachster Ansatz — Loop alle 60 s wach, entscheidet pro Trip:
   ```python
   def _monitoring_loop():
       while True:
           for trip in store.list_trips():
               interval = monitoring.required_interval_seconds(trip)
               if interval is None:
                   continue
               last = _parse(trip.get("last_flight_update"))
               if last is None or (datetime.now() - last).total_seconds() >= interval:
                   monitoring.monitor_trip(trip["id"])
           time.sleep(60)
   ```
   `last_flight_update` wird in `_refresh_flights` bereits gesetzt (`monitoring.py:246`).
3. **Wetter-Monitoring** kann beim alten Intervall bleiben oder analog — für C1 reicht der Flug-Teil. Wetter ggf. weiter über `MONITORING_INTERVAL_SECONDS`.

### Edge Cases
- Mock-Flüge (`flights.py:_mock_flight_updates`) setzen `scheduled_departure` immer → testbar.
- Kein Flug im Trip → `required_interval_seconds` = None → übersprungen.
- Zeitzonen: `scheduled_departure` kann TZ-aware sein (Aviationstack). `datetime.now()` ist naiv → beim Parsen TZ normalisieren (UTC) um Vergleichsfehler zu vermeiden.

### Verifikation
`.env`: `MOCK_FLIGHT_ARRIVAL_TIME` so setzen, dass Abflug in ~1 h liegt → Loop prüft stündlich; auf ~1,5 h → 15-min-Takt. Logs zeigen die Prüfzeitpunkte.

### Aufwand
~1,5–2 h.

---

## C2 — Dynamischer Reiseplan mit OpenTripMap + OpenRouteService ★ KERN

### Ziel
Die 4 fixen Zeitfenster ersetzen durch einen **dynamisch getakteten** Tagesplan: echte Aktivitätsdauern + Fahrtzeiten zwischen den Orten, vom LLM zu einem realistischen Plan zusammengesetzt.

### Betroffene Dateien
- `reiseagent/agents/planning.py` → `create_plan` (`:24-67`), `DAY_SLOTS` (`:6-11`) **entfällt**
- Nutzt vorhandene Provider: `providers/places.py` (OpenTripMap), `providers/navigation.py` (OpenRouteService)
- ggf. `reiseagent/llm.py` (zentraler LLM-Zugang — falls noch nicht vorhanden, hier mit anlegen)

### Ausgangslage (wichtige Funde)
- **Aktivitäten tragen bereits Koordinaten + Dauer.** `places.py:112-124` liefert pro Aktivität:
  ```python
  {"id": "otm-...", "name": ..., "category": ...,
   "location": {"lat": .., "lng": ..}, "duration_minutes": 90, ...}
  ```
  → OpenRouteService kann `location.lat/lng` **direkt** konsumieren. Kein Geocoding-Zwischenschritt nötig.
- `pick_activities_for_day` (`recommendation.py:106`) wählt schon passende Aktivitäten pro Tag (Score nach Interessen/Wetter). Kann als Vorauswahl bleiben.
- `planning.create_plan` mappt diese Auswahl bisher stumpf auf `DAY_SLOTS[i]`.

### Architektur-Entscheidung: 2 Varianten
**Variante A — Deterministisch (empfohlen für stabilen Start):**
Plan rein rechnerisch takten, ohne LLM. Reihenfolge der Aktivitäten optimieren (Nearest-Neighbor über Fahrtzeiten), Startzeit + Dauer + Fahrtzeit aufaddieren. Robust, testbar, kein LLM-Risiko.

**Variante B — LLM-gestützt (Ziel laut Anforderung):**
LLM bekommt Aktivitäten (mit Dauer + paarweisen Fahrtzeiten) + Ankunftszeit als Kontext und gibt einen geordneten, getakteten Plan zurück. Flexibler, „durchdacht", aber LLM-Output muss validiert werden.

→ **Empfehlung:** Variante A als Fundament bauen, dann B als Verfeinerung darüberlegen (LLM ordnet/begründet, Rechenlogik sichert Zeiten ab). So bricht nichts, wenn das LLM mal Unsinn liefert.

### Schritte (Variante A, dann B)
1. **Dauer je Kategorie** statt pauschal 90 Min:
   ```python
   DURATION_BY_CATEGORY = {
       "essen": 75, "restaurant": 75, "museum": 120,
       "sehenswuerdigkeit": 90, "park": 60, "shopping": 90,
   }
   def _duration(activity):
       return DURATION_BY_CATEGORY.get(activity.get("category"), activity.get("duration_minutes", 90))
   ```
2. **Fahrtzeiten** zwischen aufeinanderfolgenden Aktivitäten via `navigation.get_route(lat1,lng1,lat2,lng2,"foot-walking")` (`navigation.py:5`). Ergebnis `duration_minutes`. Bei `None` (kein ORS_KEY / keine Koordinaten) → Fallback-Puffer (z. B. 20 Min).
3. **Tagesstart festlegen** — 3-stufige Fallback-Kette:

   **Konzept:** Der User wählt im Formular (A2) ein „Tagesstart"-Feld (`day_start_time`), das als Standard für **alle Tage** gilt. Für Tag 1 mit Flugnummer wird dieser Wert durch die echte Ankunftszeit + Anreise-Puffer überschrieben.

   **3-stufige Prioritätskette — gilt für Tag 1:**
   ```python
   # 1. Flugnummer vorhanden + API-Antwort → Ankunftszeit aus Flight-API + Anreise-Puffer
   # 2. request.get("day_start_time") gesetzt (Picker aus A2) → diesen Wert nutzen
   # 3. sonst → "09:00" als Default
   day_start = (
       _flight_arrival_with_buffer(flight_updates)   # aus _adjust_first_day_for_flight
       or request.get("day_start_time")
       or "09:00"
   )
   ```
   **Folgetage (Tag 2+):** starten immer mit `request.get("day_start_time") or "09:00"` — Flug-Ankunft gilt nur für Tag 1.

4. **Anreise-Puffer bei Flugnummer realistisch setzen** (`coordinator.py:147` — `_adjust_first_day_for_flight`):
   Der aktuelle Puffer von **75 Minuten** ist zu knapp. Realistischer Ablauf nach Landung:
   - Aussteigen + Gepäck + ggf. Zoll: ~60 Min
   - Transfer zum Hotel: ~60 Min
   - Check-in: ~30 Min
   - **Gesamt: ~2,5–3 h Puffer**

   Umsetzung: Puffer auf **180 Min** erhöhen, Slot-Name auf **„Anreise zum Hotel & Check-in"** ändern (ehrliche Beschriftung, da keine echte Hotelroute berechnet wird):
   ```python
   # coordinator.py — bisher
   check_in_start = arrival_minutes + 75
   # neu
   check_in_start = arrival_minutes + 180  # ~3h für Gepäck, Transfer, Check-in
   ```
5. **Takten:** ab Tagesstart iterativ `start → +Dauer → +Fahrtzeit → nächste Aktivität`. Mahlzeiten an realistische Uhrzeiten (Mittag ~12–13, Abend ~19) einpassen.
6. **Slot-Objekte** im **bestehenden Format** erzeugen (damit UI/Coordinator unverändert bleiben):
   ```python
   {"id": str(uuid4()), "start_time": "HH:MM", "end_time": "HH:MM",
    "activity": activity, "notes": None, "travel_to_next_minutes": 12}
   ```
   `travel_to_next_minutes` ist neu/optional → später in C3 für die Kaskade nutzbar.
7. **Variante B aufsetzen:** `llm.py` als zentralen Zugang anlegen (Groq, bisher inline). Prompt: Aktivitätsliste + Dauer + Fahrtzeitmatrix + Ankunftszeit → JSON mit geordneten Slots. Output gegen Variante-A-Logik validieren (Zeiten plausibel, keine Überlappung), sonst Fallback auf A.

### Edge Cases / Risiken
- **Kein Tagesstart bekannt** (kein Flug, kein `day_start_time` im Request): Default 09:00 — kein Crash, kein leerer Plan.
- **Konflikt Flug vs. `day_start_time`**: Flug-API hat Vorrang für Tag 1 — die echte Ankunftszeit ist verlässlicher. Für Tag 2+ gilt `day_start_time`.
- **Anreise-Puffer zu groß für Kurzflüge** (z.B. Berlin→München, kein langer Gepäckweg): 180 Min sind pauschal, können in einer späteren Version konfigurierbar gemacht werden. Für die Demo ist der Pauschalpuffer ausreichend.
- **Keine Koordinaten** (Mock-Daten aus `data/mock_berlin.py`, Fallback-Quellen): Routing nicht möglich → Fallback-Puffer, nicht crashen.
- **ORS Rate-Limit/Timeout** (`navigation.py` timeout 8 s): Fahrtzeiten cachen pro (from,to), nicht bei jedem Rerun neu abfragen. ORS Free = 40 req/min.
- **Bestehende Konsumenten** des Plans dürfen nicht brechen: `time_slots`-Struktur und `activity`-Shape unverändert lassen. Nur additiv erweitern.
- **LLM-JSON** kann invalide sein → strikt parsen, bei Fehler Variante A.
- `duration_days` kommt aus A2 (Datepicker) → Plan-Länge daran koppeln.

### Verifikation
- Reise mit echten Koordinaten (OpenTripMap aktiv, `OPENTRIPMAP_API_KEY` + `ORS_API_KEY` gesetzt) → Plan zeigt variable Zeiten, Fahrtzeiten plausibel.
- Plan ohne ORS-Key → Fallback-Puffer, kein Crash.
- **3-stufige Fallback-Kette (alle Pfade testen):**
  1. Flugnummer + gültige API-Antwort → Tag 1 startet nach Flugankunft + 3h Puffer, Slot heißt „Anreise zum Hotel & Check-in".
  2. Kein Flug, `day_start_time = "10:00"` gewählt → alle Tage starten 10:00.
  3. Weder Flug noch Picker-Eingabe → alle Tage starten 09:00.

### Aufwand
Variante A: ~4–6 h. Variante B (LLM): zusätzlich ~3–4 h. **Größter Einzelposten im Projekt.**

---

## C3 — Aktivitätskarten im Tagesplan mit 3-Button-System + manuelle Zeit

### Ziel
Jede Aktivität als Karte mit: editierbarer Startzeit (Kaskade), Löschen, Alternative (gleiche Kategorie), KI-Alternative (profilbasiert). Vorschläge öffnen sich **direkt unter der Karte**, nicht im Chat.

### Betroffene Dateien
- `reiseagent/streamlit_app.py` → `render_plan_actions` (`:620-705`) umbauen, neue Karten-Render-Funktion
- `reiseagent/agents/coordinator.py` → Kaskaden-Logik (`:1067-1078`) als Funktion wiederverwendbar machen; Alternativen-Quelle
- `reiseagent/profile_store.py` → `get_top_interests` (`:106`) für KI-Alternative

### Ausgangslage (Teile existieren schon)
In `render_plan_actions` (Expander „Plan schnell bearbeiten"):
- Löschen-Button (`:695`), Alternative-Button (`:701`) — schicken aber Chat-Befehle, Ergebnis landet im **Chat**.
- Zeit-Input + „Uhrzeit übernehmen" (`:651-683`) — funktioniert, aber pro Tag/Slot im Dropdown, nicht pro Karte.
- Kaskade existiert im Coordinator (`:1067-1078`), wird aber nur bei bestimmten Chat-Phrasen ausgelöst (`_should_shift_following_slots:1399`).

### Schritte
1. **Karten-Layout** statt Expander: pro `time_slot` eine `.card` (CSS vorhanden, `streamlit_app.py:33`). Inhalt: Startzeit (editierbar), Name, Kategorie, 3 Buttons.
2. **Editierbare Startzeit pro Karte:** `st.time_input` direkt auf der Karte. Bei Änderung → Kaskade auf Folge-Slots (gleiche Differenz), Fahrtzeiten (`travel_to_next_minutes` aus C2) berücksichtigen. Kaskaden-Logik aus `coordinator.py:1067` in eine aufrufbare Funktion `shift_following_slots(day, slot, new_start)` extrahieren und hier + im Chat nutzen (DRY).
3. **Button „Löschen":** Slot entfernen, Folge-Slots nachrücken (Kaskade), Plan speichern (`store.update_trip`).
4. **Button „Alternative":** Aktivitäten gleicher Kategorie aus OpenTripMap (`places.get_places`, gefiltert auf `category`, nicht bereits genutzt — Muster wie `coordinator._available_activities:441`). Ergebnis in einem **aufklappbaren Bereich unter der Karte** (`st.session_state[f"alt_open_{slot_id}"]` togglen, dann Liste rendern). Auswahl ersetzt Aktivität, Dauer/Kaskade anpassen.
5. **Button „KI-Alternative":** `profile_store.get_top_interests()` lesen. Kein Profil → Hinweis „Noch keine Interessen bekannt — verbinde deine E-Mails". Profil vorhanden → Aktivitäten nach Interessen-Score ranken (LLM-Begründung optional via `llm.py`), im selben Aufklapp-Bereich anzeigen mit Begründungstext.
6. **State-Handling:** Pro Slot ein Toggle-Key in `st.session_state`, damit nur der geklickte Bereich aufklappt und `st.rerun()` den Zustand hält.

### Edge Cases
- Letzte Aktivität des Tages → keine Folge-Slots, Kaskade no-op.
- Zeit-Kollision nach Verschiebung → `_find_schedule_conflict` (`coordinator.py:1080`) wiederverwenden, Warnung zeigen.
- Alternative mit fehlenden Koordinaten → Fahrtzeit-Fallback (wie C2).
- KI-Alternative ohne D1/Profil → klar kommunizierter Leerzustand (kein leeres Feld).
- Calendar-Sync: nach Änderung `_refresh_plan_after_change` (`coordinator.py:1093`) aufrufen, damit Kalender aktuell bleibt.

### Abhängigkeiten
- **C2** (dynamische Slot-Struktur inkl. `travel_to_next_minutes`)
- **B2** ✅ (Fahrtzeiten)
- **D1** (Profil für KI-Alternative) — ohne D1 funktionieren Löschen/Alternative/Zeit trotzdem; nur KI-Alternative zeigt Leerzustand.

### Verifikation
- Startzeit einer mittleren Aktivität ändern → alle folgenden verschieben sich korrekt, Fahrtzeiten gewahrt.
- „Alternative" → Liste gleicher Kategorie unter der Karte, Auswahl ersetzt Aktivität + Zeiten stimmen.
- „KI-Alternative" mit Profil → profilpassende Vorschläge + Begründung; ohne Profil → Hinweis.

### Aufwand
~5–7 h (UI-Umbau + Kaskade-Refactor + zwei Alternativ-Quellen).

---

## Definition of Done (Block C)
- [ ] C1: Flug-Monitoring taktet nach Zeit bis Abflug (6h/1h/15min)
- [ ] C2: Planner erzeugt dynamisch getaktete Tage mit Dauer + Fahrtzeit; Fallback ohne ORS; Tag 1 ab Ankunft
- [ ] C3: Aktivitätskarten mit editierbarer Zeit (Kaskade) + 3 Buttons; Vorschläge unter der Karte; KI-Alternative profilbasiert mit Leerzustand
- [ ] Alle drei mit Demo-Reise manuell verifiziert

## Offene Entscheidungen
1. **C2:** Start mit Variante A (deterministisch) und B (LLM) später, oder direkt B? (Empfehlung: A zuerst.)
2. **C2:** `llm.py` jetzt zentral anlegen (Phase-0-Schuld) oder Groq weiter inline? (Empfehlung: jetzt anlegen, zahlt auf C3-KI-Alternative + D2 ein.)
3. **C1:** Wetter-Monitoring auch dynamisch takten oder beim alten Intervall belassen? (Empfehlung: belassen.)
