# Architekturübersicht — Neuer Planning Agent & Quality Score

> Beschreibt, wie der **LLM-gestützte Planning Agent** und die **neue (dünne) Quality-Score-Berechnung**
> zusammenarbeiten: was in den LLM-Prompt fließt, wie Wetter/Eingaben berücksichtigt werden, und wo die
> Grenze zwischen LLM (kuratiert) und Python (rechnet) verläuft.
>
> Stand: 2026-06-23 · Gehört zu [ZUKUNFT_NOTIZEN.md](../Miscancellous/ZUKUNFT_NOTIZEN.md) (Design-Entscheidungen).

---

## 1. Grundprinzip: Wer macht was?

| Aufgabe | Wer | Warum |
|---|---|---|
| Orte beschaffen (OpenTripMap) | `places.py` | API-Zugriff, deterministisch |
| Müll rausfiltern | `places.py` (Vorfilter) | billig, klare Regeln |
| **Welche Orte sind sehenswert? Reihenfolge? Anzahl pro Tag?** | **LLM (Planning Agent)** | braucht Weltwissen, kann Heuristik nicht |
| Genaue Uhrzeiten, Fahrtzeiten, Budget | Python (`planning.py`, `budget.py`) | LLM rechnet schlecht |
| Fallback wenn LLM fehlt/halluziniert | Python (Phase A) | System muss immer funktionieren |

**Kernsatz:** Das LLM trifft *Geschmacks- und Auswahl-Entscheidungen*. Python macht *alles Rechnerische*.

---

## 2. Datenfluss (Gesamtbild)

```
USER-EINGABE (Formular)
  destination, duration_days, interests,
  budget_total, number_of_people,
  start_date, day_start_time, flight_number
        │
        ▼
  COORDINATOR  (agents/coordinator.py)
        │
        ├─► WETTER-AGENT (providers/weather.py)
        │      └─► weather[]  pro Tag: {day_number, condition,
        │                                affects_outdoor_activities, description}
        │
        ├─► PLACES  (providers/places.py → get_places)
        │      1. OpenTripMap radius (8/15/25 km, mehrere kinds)
        │      2. Müll-Vorfilter (_is_bad_place: Name/kinds-Blockliste)
        │      3. quality_score NEU = simpel aus OpenTripMap-`rate`
        │      └─► ~50 saubere Kandidaten:
        │            {id, name, category, tags, indoor_outdoor,
        │             estimated_cost_per_person, location{lat,lng}, quality_score}
        │
        └─► PLANNING AGENT  (agents/planning.py → create_plan)
               │
               │  (A) NEU: llm.curate_plan(candidates, request, weather)
               │        INPUT an LLM (Prompt auf ENGLISCH):
               │          • city, duration_days, interests
               │          • weather pro Tag (Regen → indoor bevorzugen)
               │          • budget-Hinweis (optional), number_of_people
               │          • candidates als kompakte Liste:
               │              [{id, name, category, tags}]
               │        OUTPUT vom LLM (nur JSON):
               │          {"days":[{"day_number":1,
               │                    "activity_ids":["otm-1","otm-food3",...]}, ...]}
               │
               │  (B) VALIDIERUNG in Python:
               │        • JSON parsebar? Struktur korrekt?
               │        • jede id ∈ Kandidaten-Set?
               │        • genug Aktivitäten pro Tag?
               │        └─ NEIN / kein GROQ_API_KEY → FALLBACK Phase A
               │                  (recommendation.pick_activities_for_day)
               │
               │  (C) Python rechnet (UNVERÄNDERT, deterministisch):
               │        • Uhrzeiten ab day_start_time
               │        • Mahlzeiten-Anker: 1. food → 12:30, 2. food → 19:00
               │        • Fahrtzeiten (providers/navigation.py get_route)
               │        • Dauer je Kategorie (DURATION_BY_CATEGORY)
               │        └─► days[] mit time_slots
        │
        ▼
  BUDGET (agents/budget.py) ── deterministisch ──► budget_summary
        ▼
  active_plan {days, budget_summary, request, ...}  ──► Store / Streamlit-UI
```

---

## 3. Was genau fließt in den LLM-Prompt?

**Kontext (Rahmen):**
- `destination` — Stadtname, original (z.B. "Rotterdam")
- `duration_days` — damit das LLM die Orte über die Tage verteilt und die Anzahl pro Tag selbst bestimmt
- `interests` — vom User gewählte Interessen (Museen, Sightseeing, Essen, Natur, Shopping)
- `number_of_people`, `budget_total` — als grober Hinweis (teuer vs. günstig abwägen), **nicht zum Rechnen**
- `weather` pro Tag — bei Regen/Sturm sollen Indoor-Orte (Museen) bevorzugt, Outdoor (Parks) gemieden werden

**Die Kandidaten (~50):** pro Ort nur das Nötige, damit der Prompt kompakt bleibt:
```
{ "id": "otm-W12345", "name": "Markthal", "category": "sightseeing", "tags": ["architektur"] }
```
Koordinaten, Kosten, Dauer kommen **nicht** in den Prompt — die braucht das LLM nicht, die nutzt Python danach.

**Sprache:** Prompt auf **Englisch** (Modell ist primär englisch trainiert). **Ortsnamen bleiben original** (nicht übersetzen).

**Beispiel-Prompt (konzeptionell):**
```
You are a travel planner. From the candidate places below, build a {duration_days}-day
plan for {city}. Traveler interests: {interests}.

Rules:
- Pick only genuinely worth-visiting places for a tourist. Skip generic buildings,
  offices, banks, post offices even if they appear.
- Each day rhythm: morning sightseeing → lunch (a food place) → afternoon → dinner (a food place).
- Sensible number per day (about 4-5). Don't put 4 museums in a row.
- Weather per day: {weather}. On rainy days prefer indoor places.
- For long trips you may keep some days lighter or revisit a highlight.

Return ONLY JSON: {"days":[{"day_number":1,"activity_ids":["id1","id2"]}, ...]}

Candidates:
{json list of {id, name, category, tags}}
```

---

## 4. Neue Quality-Score-Berechnung (in `places.py`)

**Vorher (Problem):** `quality_score` versuchte mit Magic Numbers (+60 für berühmte Namen, −80 für
„schlechte" Wörter, +16 Museum …) zu *ranken*, was sehenswert ist. Die echten Daten zeigten: das
zugrundeliegende Signal (`rate`, wikidata) misst Denkmalwert, nicht touristische Attraktivität.
→ Postamt = rate 7, Markthal fehlt.

**Nachher (zwei getrennte Schritte):**

1. **Müll-Vorfilter** (hart, deterministisch) — entfernt offensichtlichen Müll *vor* dem Scoring:
   - kein Name / Name ist nur eine Adresse / zu kurz
   - keine Koordinaten
   - `kinds` in Blockliste (parking, hotels, offices, banks …)

2. **Simpler quality_score (0–100)** — nur noch ein grobes Vorsortier-Signal:
   - basiert hauptsächlich auf OpenTripMap-`rate` (z.B. `rate * 12`, gedeckelt auf 100)
   - kleiner Bonus für Museum/Sightseeing-Kategorie (optional)
   - **keine** Magic-Name-Liste mehr, **kein** wikipedia-Bonus (war totes Signal), **kein** −80

**Die eigentliche „ist das sehenswert?"-Bewertung macht jetzt das LLM** (Abschnitt 3).
`quality_score` bleibt nur, um die Kandidaten grob vorzusortieren und als Zahl für die
Phase-A-Fallback-Bewertung (`recommendation.score_activity`) verfügbar zu sein.

---

## 5. Wetter-Berücksichtigung — zwei Ebenen

1. **Im LLM-Prompt** (neu): Das LLM bekommt das Wetter pro Tag und legt Indoor-Orte auf Regentage.
2. **In Phase A / Replanning** (bleibt): `recommendation.score_activity` rechnet `weather_match`
   (Outdoor bei Regen → niedriger Score). `replanning.py` ersetzt Outdoor durch Indoor bei
   Wetter-Events. Diese Logik bleibt unangetastet und greift im Fallback.

---

## 6. Was bleibt unverändert (wichtig für Stabilität)

- Signatur `get_places(destination, interests)` und die Activity-Dict-Struktur
- Signatur `create_plan(request, all_activities, weather)`
- `pick_activities_for_day(...)` als Fallback
- `score_activity(...)`, `budget.calculate_budget(...)`, `replanning.py`
- Mahlzeiten-Anker und Fahrtzeit-Logik in `planning.py`
