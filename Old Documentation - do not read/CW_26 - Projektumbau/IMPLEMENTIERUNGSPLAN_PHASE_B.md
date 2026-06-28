# Implementierungsplan — Places-Fix & Phase B (LLM-Planung)

> Arbeitsgrundlage für den nächsten Claude-Code-Prompt. Beschreibt **Schritt für Schritt**, welche
> Dateien wie geändert werden, **welche Abhängigkeiten** beachtet werden müssen (damit nichts kaputtgeht),
> und **welche offenen Fragen** vorher geklärt werden sollten.
>
> Architektur-Kontext: [ARCHITEKTUR_PLANUNG_LLM.md](Old%20Documentation%20-%20do%20not%20use/ARCHITEKTUR_PLANUNG_LLM.md) ·
> Design-Entscheidungen: [ZUKUNFT_NOTIZEN.md](Old%20Documentation%20-%20do%20not%20use/ZUKUNFT_NOTIZEN.md)

---

## Coding-Prinzipien (MUSS eingehalten werden)

> Write simple Python code that a beginner can easily understand. Use basic Python features,
> minimal exception handling, very little abstraction, no unnecessary classes, no over-engineering.
> Keep it short, readable, and easy to modify.

Zusätzlich projektspezifisch:
- Kategorie-Vokabular immer: `culture / food / nature / sightseeing / shopping`
- `A3 Telegram` NICHT anfassen
- LLM-Prompt auf **Englisch**, Ortsnamen **original** lassen

---

## Reihenfolge

**Teil 1 (Places-Fix) zuerst**, dann **Teil 2 (Phase B)**. Grund: Phase B braucht einen sauberen,
ausreichend großen Kandidaten-Pool als Input. Teil 1 erzeugt genau den.

---

## TEIL 1 — Places-Fix (`providers/places.py`)

### 1.1 Essen immer erlauben
**Datei:** `providers/places.py` · Funktion `_category_allowed_by_interests` (ca. Zeile 533)
- Für `category == "food"` immer `True` zurückgeben (Restaurants nie mehr blockieren).
- **ENTSCHIEDEN:** Nur `food` immer erlauben. `nature` und `shopping` bleiben gated (nur bei
  gewähltem Interesse) — also dort **keine** Änderung.

### 1.2 City Highlights & stadtspezifische Fallbacks entfernen
**Datei:** `providers/places.py`
- Löschen: `CITY_HIGHLIGHTS` (Z. 109–274), `_get_city_highlight_activities` (Z. 651), `_get_city_key`
  (Z. 634), `_tags_for_category` falls nur dort genutzt, die Highlight-/Berlin-Zweige in `get_places`
  (Z. 755–768).
- Import `from data.mock_berlin import BERLIN_ACTIVITIES` (Z. 6) entfernen, wenn nicht mehr genutzt.
- **Abhängigkeit:** `recommendation.py:70` nutzt `source == "city_highlight"` für `highlight_bonus`.
  Wird automatisch immer `0` (kein Ort hat mehr diese source) → harmlos. Optional dort aufräumen.
- **ENTSCHIEDEN:** `GENERIC_ACTIVITIES` ebenfalls **entfernen**. Bei komplettem API-Ausfall
  (kein Key / API down) gibt `get_places` eine **leere Liste** zurück und setzt `LAST_PLACES_STATUS`
  auf eine klare Fehlermeldung (wird in `coordinator.py:67–68` bereits im POI-Insight angezeigt).
  → Prüfen, dass leere Aktivitätsliste sauber durchläuft (Plan mit leeren Tagen + Fehlermeldung,
  keine Exception) in `planning.create_plan`, `coordinator.handle_plan_request`, UI.

### 1.3 Quality Score zu dünnem Vorfilter umbauen
**Datei:** `providers/places.py`
- `_quality_score` (Z. 544) stark vereinfachen: hauptsächlich aus OpenTripMap-`rate`
  (z.B. `rate * 12`, gedeckelt 0–100), optional kleiner Kategorie-Bonus. **Entfernen:**
  `IMPORTANT_NAME_WORDS`-Bonus (+60), wikipedia-Bonus (+10, totes Signal), wikidata (+6, konstant),
  die −80-Strafen (Müll wird stattdessen im Vorfilter hart entfernt).
- Müll-Vorfilter `_is_bad_place` (Z. 524) **behalten** als harten Ausschluss.
- **Hard-Cutoff lockern:** `quality_score >= 35` (Z. 409) auf z.B. `>= 10` senken oder entfernen —
  damit ~50 statt ~9 Kandidaten überleben (das LLM kuratiert ja danach).
- **Pool-Größe erhöhen:** in `_rank_and_deduplicate` das `[:30]` (Z. 613) auf ~50 anheben.
- **ENTSCHIEDEN:** `random.shuffle` des `variable_pool` (Z. 611) **entfernen** — das LLM soll stabil
  die besten Kandidaten sehen (reproduzierbar). Stattdessen einfach nach `quality_score` sortiert lassen.
  `import random` (Z. 2) entfernen, falls dann ungenutzt.
- **Wichtig — Shape behalten:** Jede Activity muss weiterhin alle Felder haben, die downstream
  konsumiert werden: `id, name, category, tags, indoor_outdoor, estimated_cost_per_person,
  location{lat,lng}, quality_score, duration_minutes, source`. (sonst brechen `budget.py`,
  `planning.py`, `recommendation.py`, `replanning.py`)

### 1.4 Abhängigkeiten Teil 1 (NICHT brechen)
- `get_places(destination, interests)` wird aufgerufen von: `coordinator.py:61` & `:507`,
  `streamlit_app.py:388/566/960`, `main.py:255`, `monitoring.py:113`, `suggestion_agent.py:76`,
  `test_all.py:77`. → **Signatur und Rückgabetyp (Liste von Activity-Dicts) unverändert lassen.**
- `quality_score` wird als Zahl gelesen in `recommendation.py:69` (`/100`) & `:128` (Sort) und
  `coordinator.py:584`. → **muss eine 0–100-Zahl bleiben.**

---

## TEIL 2 — Phase B: LLM-Planung

### 2.1 Neue Datei `reiseagent/llm.py`
Zentrales Groq-Modul. Eine Hauptfunktion, simpel gehalten:

```python
# Pseudostruktur (nicht final):
def curate_plan(candidates: list, request: dict, weather: list) -> dict | None:
    # 1. GROQ_API_KEY prüfen; fehlt -> return None (Fallback Phase A)
    # 2. Prompt (Englisch) bauen: city, duration_days, interests, weather, kompakte candidates
    #    -> OHNE Budget (ENTSCHIEDEN: Budget bleibt komplett bei Python)
    # 3. Groq aufrufen (model="llama-3.3-70b-versatile"), JSON-Antwort erzwingen
    # 4. JSON parsen; bei Fehler -> return None
    # 5. Struktur prüfen + ids gegen candidate-id-Set validieren
    # 6. {"days":[{"day_number":int,"activity_ids":[...]}]} zurückgeben oder None
```
- Modell wie im Rest des Codes: `llama-3.3-70b-versatile`.
- Groq-Aufruf-Stil an `agents/daily_brief.py` (Z. 50–66) anlehnen (gleiche Lib, gleiche Form).
- Möglichst `response_format={"type":"json_object"}` nutzen, damit nur JSON kommt.
- Minimales Exception-Handling: ein `try/except` um den API-Call, bei Fehler `return None`.

### 2.2 Integration in `agents/planning.py`
**Funktion `create_plan` (Z. 69) — Signatur UNVERÄNDERT lassen.** Nur der innere Mechanismus
„welche Aktivitäten kommen an Tag X" wird ersetzt:

1. Am Anfang: `curated = llm.curate_plan(all_activities, request, weather)`.
2. Wenn `curated` gültig: pro Tag die `activity_ids` über eine `id -> activity`-Map auflösen →
   `activities_for_day`. (Map einmal aus `all_activities` bauen.)
3. Wenn `curated is None`: bestehender Weg über `pick_activities_for_day(...)` (Phase A).
4. **Der Rest von `create_plan` bleibt komplett gleich** — Uhrzeiten, Mahlzeiten-Anker
   (food → 12:30/19:00), Fahrtzeiten, `time_slots`-Aufbau.

→ So ändert sich **nichts** an `coordinator.py:72` und `test_all.py:144`.

### 2.3 Validierungs-Regeln (in `llm.py` oder `planning.py`)
- Alle `activity_ids` müssen in der Kandidaten-Map existieren → unbekannte verwerfen.
- Anzahl Tage sollte zu `duration_days` passen (mehr/weniger tolerant behandeln; fehlende Tage →
  für diese Tage Phase-A-Fallback).
- Innerhalb eines Tages keine Duplikate; **über Tage hinweg Wiederholung erlaubt** (für lange Trips).
- Wenn ein Tag nach Validierung leer/zu klein ist → für diesen Tag Phase A nutzen.

### 2.4 Abhängigkeiten Teil 2 (NICHT brechen)
- `create_plan(request, all_activities, weather)` Signatur fix (Aufrufer: `coordinator.py:72`,
  `test_all.py:144`).
- `pick_activities_for_day(...)` bleibt vorhanden und funktionsfähig (Fallback + `test_all.py:130`).
- Neue Abhängigkeit `planning.py → llm.py`. Prüfen, dass der Import-Pfad zur restlichen Struktur passt
  (`reiseagent/` ist Working-Dir; andere Module importieren z.B. `from providers... import ...`,
  `from agents import ...`). `llm.py` liegt auf gleicher Ebene wie `agents/` und `providers/`.

---

## Test-Auswirkungen
- `test_all.py` testet `get_places`, `score_activity`, `pick_activities_for_day`, `create_plan`.
  Alle Signaturen bleiben → Tests sollten weiter laufen. **Nach jeder Teil-Änderung `python test_all.py`
  ausführen.**
- TEST 4 erwartet „max 4 Aktivitäten" von `pick_activities_for_day` — prüfen, ob das mit gelockertem
  Pool noch stimmt (Fallback-Pfad).
- Manueller Test: Rotterdam, 5 Tage → erwartet volle Tage mit echten Sehenswürdigkeiten + Essen;
  Rotterdam 11 Tage → erwartet keine leeren Tage (Fallback/Wiederholung greift).

---

## Alle Fragen entschieden — bereit zur Implementierung

### Entschiedene Fragen (2026-06-23)

1. **Nature & Shopping:** ✅ Nur `food` immer erlauben. Nature/Shopping bleiben gated.
2. **Notfall-Fallback:** ✅ `GENERIC_ACTIVITIES` entfernen. Bei API-Ausfall → leere Liste + Fehlermeldung.
3. **random.shuffle:** ✅ Entfernen. LLM soll stabil die besten Kandidaten sehen.
4. **Budget im Prompt:** ✅ Raushalten. Budget macht komplett Python.

5. **Profil-Interessen:** ✅ Später im Profil-Feature trennen (Out-of-Scope für Phase B). Notiert in ZUKUNFT_NOTIZEN.md.
6. **Anzahl Aktivitäten/Tag:** ✅ Richtwert ~4–5 im Prompt nennen, LLM darf abweichen.
7. **`MIN_ACTIVITIES_PER_DAY` / `MAX_PER_CATEGORY`:** ✅ Gelten nur noch im Phase-A-Fallback. LLM-Ausgabe wird nicht danach nachgeprüft.

---

## Definition of Done
- Rotterdam 5 Tage: volle, abwechslungsreiche Tage mit echten Sehenswürdigkeiten **und** Essen.
- Rotterdam 11 Tage: keine leeren Tage.
- Ohne `GROQ_API_KEY`: Plan funktioniert weiter (Phase A Fallback), keine Exception.
- `python test_all.py` läuft grün.
- Keine geänderten Signaturen an `get_places` / `create_plan`.
