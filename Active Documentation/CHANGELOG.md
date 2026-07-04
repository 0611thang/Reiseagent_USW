# Changelog — Reiseplanungsagent

Alle Änderungen am Projekt werden hier dokumentiert.  
Sortierung: **neueste Einträge oben**.

---

## [2026-06-28] Fix: Angenommene Telegram-Vorschläge in Google Calendar eintragen

**Status:** Merged  
**Datum & Uhrzeit:** 2026-06-28  
**Autor:** Valeriu  

### Zweck
Wenn ein Freizeitvorschlag über den Telegram-Button „✅ Ja, planen!" angenommen wurde, entstand zwar ein Reiseplan (sichtbar in Streamlit), aber er wurde **nicht** in den Google-Kalender eingetragen. Der Vorschlags-Handler rief — anders als der Flug-Verspätungs-Handler — keine Kalender-Synchronisation auf.

### Was wurde geändert

**`reiseagent/main.py`** (`_handle_telegram_suggestion_decision`, accept-Zweig):
- Nach dem Erstellen und Speichern des Plans wird jetzt `sync_full_plan_to_calendar(new_plan, trip["id"])` aufgerufen — analog zum Flug-Handler. Die Kalendereinträge werden mit der `trip_id` markiert, damit sie später sauber wieder gelöscht werden können.
- `send_plan_update` bekommt jetzt den echten `calendar_synced`-Status statt implizit `False`.

### Betroffene Dateien
- `reiseagent/main.py`

### Tests
- Import-/Syntax-Check bestanden; `sync_full_plan_to_calendar` ist im Handler vorhanden.
- Vorschlag über Telegram annehmen → Plan erscheint in Streamlit **und** als „Reiseplan Tag 1"-Eintrag im Google-Kalender am freien Tag.

### Hinweis
- Bereits zuvor angenommene Pläne werden nicht rückwirkend eingetragen — der Sync greift nur bei neuen Annahmen.
- Voraussetzung: `credentials.json` / `calendar_token.json` liegen im Ordner `reiseagent/`.

**Breaking Change:** Nein — additiver Aufruf im bestehenden accept-Zweig.

---

## [2026-06-28] Fix: Phase 4 Nachbesserungen — Kalender-Erkennung + Telegram-Vorschlags-Buttons

**Status:** Merged  
**Datum & Uhrzeit:** 2026-06-28  
**Autor:** Valeriu  

### Zweck
Beim Testen von Phase 4 traten drei Fehler in der Kalender-Erkennung und ein fehlendes Feature im Telegram-Flow auf: (1) mehrtägige Kalender-Events (z.B. 3-Tage-Urlaub als Serie) wurden nur am Starttag erkannt, (2) Tage ohne Termin wurden dem LLM gar nicht gezeigt, sodass echte freie Tage unsichtbar blieben, (3) der Test lud die `.env` nicht, wodurch der LLM-Aufruf still auf den Fallback fiel und alle Tage als „frei" markierte, und (4) der „Ja, planen!"-Button in Telegram funktionierte nicht — die Empfangs-Seite für Vorschläge fehlte komplett.

### Was wurde geändert

**`reiseagent/providers/calendar.py`** (`get_calendar_events`):
- Mehrtägige ganztägige Events werden jetzt in **einen Eintrag pro Tag** aufgespalten. Google liefert eine Serie (z.B. 3.–5. Juli) als ein einzelnes Event mit Start- und Enddatum (Ende exklusiv); bisher wurde nur der Starttag erfasst. Jetzt iteriert der Code von Start bis Ende und legt für jeden Tag einen Eintrag an.
- Variablen-Shadowing behoben (`start`/`end` der Zeitfenster-Berechnung hießen wie die Event-Felder) → umbenannt zu `window_start`/`window_end`.

**`reiseagent/agents/calendar_agent.py`**:
- Neue Hilfsfunktion `_build_day_lines(events, days_ahead)`: erzeugt für **jeden** Tag im Zeitraum eine Prompt-Zeile — auch für Tage ohne Termin („kein Termin"). Bisher sah das LLM nur Tage mit Einträgen, wodurch leere (= freie) Tage nie bewertet wurden.
- `interpret_calendar(events, days_ahead=14)`: nutzt jetzt `_build_day_lines`, schickt alle Tage an das LLM. `max_tokens` auf 1200 erhöht (14 Tage JSON).
- Fallback verbessert: statt der alten Marker-only-Logik (`find_free_days`) gilt jetzt „Tag mit Termin = belegt, sonst frei". Dadurch sind auch ohne LLM Arbeits-/Urlaubstage korrekt belegt.
- `get_truly_free_days`: reicht `days_ahead` an `interpret_calendar` durch; `find_free_days`-Import entfernt.

**`reiseagent/test_calendar.py`**:
- `load_dotenv()` am Anfang ergänzt — **kritisch**: ohne `.env` ist `GROQ_API_KEY` leer, der LLM-Aufruf scheitert still und der Fallback markiert alle Tage als frei. Das war der Grund, warum im Test Arbeitstage fälschlich als „frei" erschienen.
- Schritt 2 nutzt jetzt `_build_day_lines`, damit der angezeigte Prompt exakt dem entspricht, was das LLM wirklich bekommt (inkl. leerer Tage).

**`reiseagent/providers/telegram.py`**:
- `_create_callback_token(...)` bekommt einen Parameter `kind="flight"` (Default unverändert → Flug-Flow bleibt gleich). Damit lassen sich Vorschlags-Callbacks von Flug-Verspätungs-Callbacks unterscheiden.
- `send_suggestion_proposal(trip, suggestion, home_city="Berlin")`: erzeugt Tokens mit `kind="suggestion"` und legt `suggestion_date` + `home_city` in den Token-Daten ab, damit der Callback-Handler daraus einen Plan bauen kann.

**`reiseagent/scheduler.py`**:
- `run_weekly_suggestions` reicht `home_city` an `send_suggestion_proposal` durch.

**`reiseagent/main.py`**:
- Neue Funktion `_handle_telegram_suggestion_decision(action, callback_data)` — die bisher fehlende Empfangs-Seite: bei `accept` wird ein echter 1-Tages-Plan für die Heimatstadt am freien Tag erstellt (`coordinator.handle_plan_request` mit `auto=True`), als Trip gespeichert, per Telegram gesendet und der Vorschlag als angenommen markiert. Bei `reject` werden die Vorschläge des Tages in `profile_store` als abgelehnt markiert.
- Callback-Loop verzweigt jetzt nach `callback_data["kind"]`: `suggestion` → neuer Handler, sonst → bestehender Flug-Handler `_handle_telegram_proposal_decision`.

### Betroffene Dateien
- `reiseagent/providers/calendar.py`
- `reiseagent/agents/calendar_agent.py`
- `reiseagent/test_calendar.py`
- `reiseagent/providers/telegram.py`
- `reiseagent/scheduler.py`
- `reiseagent/main.py`

### Tests
- Import-/Syntax-Check aller geänderten Dateien bestanden.
- Mehrtägiges Event (Urlaub 3.–5. Juli) → erscheint als drei getrennte Tageseinträge statt nur am 3. Juli.
- `_build_day_lines` mit gemischten Events → leere Tage erscheinen als „kein Termin", Termine korrekt zugeordnet.
- Flug-Callback unverändert: `_create_callback_token` ohne `kind` → Default `"flight"` → alter Pfad.
- Vorschlags-Callback: `kind="suggestion"` → neuer Handler greift, erstellt Plan bzw. lehnt ab.

### Bekannte Einschränkungen
- Alte Telegram-Buttons (vor diesem Fix erzeugt) bleiben ungültig — nur nach Server-Neustart neu erzeugte Vorschläge funktionieren.
- Beim Annehmen kann der Telegram-Lade-Kreisel kurz verzögern, da die KI den Plan erst erstellt; der Plan wird trotzdem zuverlässig gesendet.

**Breaking Change:** Nein — `_create_callback_token` ist abwärtskompatibel (`kind` hat Default), Flug-Verspätungs-Flow unverändert. `get_calendar_events`-Rückgabeshape pro Eintrag unverändert (nur mehr Einträge bei Mehrtages-Events).

---

## [2026-06-28] Feature: Phase 4 — Proaktiver Scheduler + Telegram-Vorschlagskarte

**Status:** Merged  
**Datum & Uhrzeit:** 2026-06-28  
**Autor:** Valeriu  

### Zweck
Der Agent war bisher rein reaktiv — er hat nur gehandelt, wenn der Nutzer explizit etwas angefragt hat. Phase 4 macht ihn proaktiv: Einmal pro Woche (samstags) liest das System den Google-Kalender, lässt ein LLM die Einträge intelligent interpretieren (nicht mehr nur „kein Termin = frei"), erstellt für wirklich freie Tage personalisierte Freizeitvorschläge und schickt sie per Telegram mit [Ja, planen!] / [Nein, danke]-Buttons an den Nutzer. Der Nutzer behält die Kontrolle — der Agent schlägt vor, der Mensch entscheidet.

Zusätzlich wurde die Profil-Trennung umgesetzt: Automatische Vorschläge mischen Profil-Interessen ein, manuelle Reisen (Nutzer füllt Formular aus) tun das nicht mehr.

### Was wurde geändert

**`reiseagent/agents/calendar_agent.py`** *(neu)*:
- `interpret_calendar(events)` — schickt rohe Kalendereinträge an das LLM mit dem `INTERPRET_CALENDAR`-Prompt. Das LLM stuft jeden Tag als `free` oder `busy` ein und begründet das kurz. Erkennt z.B. „Arbeit 8–18 Uhr" als belegt und Feiertage als frei.
- `_parse_calendar_response(raw)` — parst die JSON-Antwort des LLM; bei ungültigem JSON `None` zurückgeben.
- Qualitäts-Gate + Fallback: Bei fehlerhafter LLM-Antwort greift die deterministische `find_free_days`-Methode als Rückfall. `llm.log_step` nach jedem Interpretationsaufruf.
- `get_truly_free_days(days_ahead=14)` — Einstiegsfunktion: liest Kalender, lässt LLM interpretieren, gibt nur vollständig `free` eingestufte Tage zurück (keine `partly`-Tage).

**`reiseagent/prompts.py`**:
- Neues Template `INTERPRET_CALENDAR` (Deutsch): Regeln für free/busy-Einstufung, Feiertage = frei, kurze Termine (Gym, Arzt < 2h) = frei. Antwort als JSON-Liste.

**`reiseagent/agents/free_time_detector.py`**:
- Komplett umgeschrieben: nutzt jetzt `calendar_agent.get_truly_free_days()` statt der alten Marker-only-Heuristik (`REISEAGENT_BLOCK_MARKER`). Speichert erkannte freie Tage in `profile_store.replace_free_days`.

**`reiseagent/providers/telegram.py`**:
- Neue Funktion `send_suggestion_proposal(trip, suggestion)` — schickt einen Freizeitvorschlag per Telegram mit Inline-Buttons `✅ Ja, planen!` und `❌ Nein, danke`. Nutzt denselben Callback-Token-Mechanismus wie `send_flight_delay_proposal`. `telegram.py` selbst wurde dabei strukturell nicht verändert — nur eine neue Funktion ergänzt.

**`reiseagent/scheduler.py`** *(neu)*:
- `scheduler_loop()` — Hintergrundthread, der stündlich prüft ob heute Samstag ist.
- `_should_run_today()` — Wochentag-Guard (`weekday() == 5`), verhindert Mehrfachlauf am selben Tag via `_last_run_date`.
- `run_weekly_suggestions()` — Hauptablauf: freie Tage erkennen → Vorschläge erstellen (max. 3) → per Telegram senden. Nutzt den neuesten gespeicherten Trip für die Callback-Tokens; falls kein Trip vorhanden, wird ein leerer Platzhalter-Trip angelegt.

**`reiseagent/agents/coordinator.py`**:
- Profil-Interessen (`PROFILE_TO_INTEREST`-Mapping) werden jetzt **nur noch** eingemischt, wenn `request.get("auto") == True`. Manuelle Reisen (Nutzer-Formular) erhalten die Profil-Interessen nicht mehr automatisch. `request["interests"]` bleibt in beiden Fällen vollständig gesetzt.

**`reiseagent/main.py`**:
- `import scheduler` ergänzt, `send_suggestion_proposal` zum Telegram-Import hinzugefügt.
- Neue Variable `_scheduler_thread_started` als Einmal-Startschutz.
- In `start_background_threads`: vierter Thread `scheduler.scheduler_loop` (daemon) gestartet.
- Neuer Endpoint `POST /api/scheduler/run` — manueller Trigger für Tests: `POST /api/scheduler/run` in Swagger aufrufen — der komplette Ablauf (Kalender lesen → LLM interpretieren → Vorschläge erstellen → Telegram senden) läuft sofort durch, ohne auf Samstag warten zu müssen.

### Betroffene Dateien
- `reiseagent/agents/calendar_agent.py` *(neu)*
- `reiseagent/prompts.py`
- `reiseagent/agents/free_time_detector.py`
- `reiseagent/providers/telegram.py`
- `reiseagent/scheduler.py` *(neu)*
- `reiseagent/agents/coordinator.py`
- `reiseagent/main.py`

### Tests
- Syntax-Check aller geänderten Dateien bestanden (`OK — alle Dateien geladen ohne Fehler`).
- `POST /api/scheduler/run` manuell auslösen → Vorschläge werden erstellt und in DB gespeichert; bei konfiguriertem Telegram-Bot erscheinen sie mit Buttons in der Gruppe.
- Wochentag-Guard: zweimaliges Aufrufen von `run_weekly_suggestions` am selben Tag → zweiter Aufruf übersprungen.
- Manuelle Reise ohne `auto`-Flag → Profil-Interessen werden nicht eingemischt.
- Kein Kalender konfiguriert → `get_truly_free_days` gibt leere Liste zurück, kein Crash.
- LLM-Fehler bei Kalender-Interpretation → deterministischer Fallback greift, kein Crash.

**Breaking Change:** Nein — `handle_plan_request`-Signatur unverändert. Bestehende Aufrufe ohne `auto`-Flag verhalten sich jetzt korrekt (kein Profil-Merge mehr bei manuellen Reisen — das war der gewollte Verhaltenswechsel). `providers/telegram.py` strukturell nicht verändert.

---

## [2026-06-28] Feature: Phase 3 — Memory / RAG (Semantisches Nutzergedächtnis)

**Status:** Merged  
**Datum & Uhrzeit:** 2026-06-28  
**Autor:** Valeriu  

### Zweck
Der Reiseplan war bisher vollständig generisch — die KI wusste nichts darüber, wer der Nutzer ist. Telegram-Nachrichten und E-Mails wurden zwar schon eingelesen und auf Schlüsselwörter untersucht, aber niemals als Kontext an den Planer weitergegeben. Phase 3 gibt dem System ein semantisches Gedächtnis: Jede eingelesene Nachricht wird zusammen mit einem mathematischen Inhalts-Fingerabdruck (Embedding) gespeichert. Beim Erstellen eines Reiseplans oder Freizeitvorschlags sucht das System automatisch die thematisch passendsten Nachrichten heraus und fügt sie dem Prompt hinzu — damit die KI einen personalisierten statt generischen Plan erstellt.

### Was wurde geändert

**`reiseagent/memory.py`** *(neu)*:
- `store_message(source, date, text)` — speichert eine Nachricht mit ihrem Embedding (sentence-transformers `all-MiniLM-L6-v2`) in der Datenbank. Duplikate (gleiche `source + date + text`) werden übersprungen. Bei mehr als 500 gespeicherten Nachrichten werden die ältesten automatisch gelöscht.
- `retrieve_context(query, k=4)` — berechnet den Embedding-Vektor für eine Suchanfrage, vergleicht ihn per Cosine-Ähnlichkeit (`numpy`) mit allen gespeicherten Vektoren und gibt die Top-k Nachrichten zurück.
- Modell-Lazy-Loading: Das Embedding-Modell wird einmalig beim ersten Aufruf geladen (~5–10 s) und danach im Speicher gehalten. Terminal-Meldung beim Laden.

**`reiseagent/profile_store.py`**:
- Neue Tabelle `messages(id, source, date, text, embedding BLOB, saved_at)` in `init_db` — ein Eintrag pro Nachricht, `UNIQUE(source, date, text)` verhindert Duplikate.

**`reiseagent/agents/profile_learner.py`**:
- `import memory` ergänzt.
- `learn_from_telegram`, `learn_from_gmail`, `learn_from_imap`: je ein `memory.store_message(...)` Aufruf am Ende der Schleife hinzugefügt — Nachrichten werden ab jetzt zusätzlich zur Schlüsselwort-Extraktion auch als Volltexte mit Embedding gespeichert.

**`reiseagent/prompts.py`**:
- `CURATE_PLAN`: optionaler Block `{context_block}` vor den Regeln eingefügt — wenn Kontext vorhanden, erscheint „Nutzer-Kontext (aus Nachrichten): ..."; wenn leer, bleibt der Prompt unverändert.
- `SUGGESTION_DAY`: analog — `{context_block}` vor dem JSON-Antwort-Block eingefügt.

**`reiseagent/agents/planning.py`**:
- `import memory` ergänzt.
- `_curate_plan`: ruft `memory.retrieve_context(destination, k=4)` auf, baut `context_block` und fügt ihn in den `CURATE_PLAN`-Prompt ein. `llm.log_step("memory", ...)` nach jedem Abruf.

**`reiseagent/agents/suggestion_agent.py`**:
- `import memory` ergänzt.
- `create_suggestion_for_day`: ruft `memory.retrieve_context(free_date + home_city, k=4)` auf, baut `context_block` und fügt ihn in den `SUGGESTION_DAY`-Prompt ein. `llm.log_step("memory", ...)` nach jedem Abruf.

**`reiseagent/requirements.txt`**:
- `sentence-transformers` und `numpy` eingetragen.

### Betroffene Dateien
- `reiseagent/memory.py` *(neu)*
- `reiseagent/profile_store.py`
- `reiseagent/agents/profile_learner.py`
- `reiseagent/prompts.py`
- `reiseagent/agents/planning.py`
- `reiseagent/agents/suggestion_agent.py`
- `reiseagent/requirements.txt`

### Tests
- `memory.store_message("telegram", "2026-06-28", "Wir wollen mit den Kindern nach Paris, eher Museen")` gespeichert → `retrieve_context("Paris")` liefert sie als Top-Treffer.
- Zweite Nachricht (Jazz-Konzertticket) gespeichert → `retrieve_context("Musik Veranstaltung")` liefert sie als Top-Treffer.
- Semantische Trennung korrekt: Paris-Query findet Paris-Nachricht zuerst, Musik-Query findet Konzert-Nachricht zuerst.
- Leere Datenbank → `retrieve_context` gibt `[]` zurück, `context_block` wird weggelassen, kein Crash.
- Duplikat-Schutz: gleiche Nachricht zweimal einspeichern → nur ein Eintrag in der DB.

**Breaking Change:** Nein — `CURATE_PLAN`- und `SUGGESTION_DAY`-Prompts erhalten `context_block` als neues Pflichtfeld, das von `planning.py` und `suggestion_agent.py` immer befüllt wird (entweder mit Inhalt oder leerem String). Alle anderen Signaturen unverändert. `providers/telegram.py` nicht angefasst.

---

## [2026-06-28] Refactor: Phase 2 Nachtrag — Places-Fix (PHASE_B Teil 1)

**Status:** Merged  
**Datum & Uhrzeit:** 2026-06-28  
**Autor:** Valeriu  

### Zweck
Die in `IMPLEMENTIERUNGSPLAN_PHASE_B.md` beschriebenen Places-Fixes waren in Phase 2 noch offen: Der Kandidaten-Pool war zu klein und zu stark gefiltert, sodass das LLM (Phase 2) nicht genug gute Orte zur Auswahl bekam. Außerdem waren Restaurants vom Filter blockierbar, und stadtspezifische Hardcode-Listen verhinderten echte API-basierte Pläne.

### Was wurde geändert

**`reiseagent/providers/places.py`**:
- **`_category_allowed_by_interests`:** `food` gibt jetzt immer `True` zurück — Restaurants werden nie mehr durch fehlende Interesse-Angabe blockiert.
- **`_quality_score` vereinfacht:** Hauptsignal ist jetzt `rate * 6` (OpenTripMap-Rate 0–7 → 0–42 Punkte) plus kleiner Kategorie-Bonus. Entfernt: `IMPORTANT_NAME_WORDS`-Bonus (+60), `wikipedia`-Bonus (+10), `wikidata`-Bonus (+6) und die −80-Strafen (Müll wird bereits durch `_is_bad_place` hart gefiltert). `IMPORTANT_NAME_WORDS` bleibt für `_is_bad_place_name` erhalten.
- **Hard-Cutoff gesenkt:** `quality_score >= 35` → `>= 10` — damit überleben ~50 statt ~9 Kandidaten den Filter und das LLM bekommt einen vollständigen Pool.
- **`CITY_HIGHLIGHTS`-Dict entfernt** (163 Zeilen, Hardcode-Listen für Paris, Rom, Berlin, London etc.) samt `_get_city_key`, `_get_city_highlight_activities`.
- **`GENERIC_ACTIVITIES`-Liste entfernt** (5 generische Platzhalter-Aktivitäten). Bei API-Ausfall gibt `get_places` jetzt eine leere Liste zurück statt Dummy-Aktivitäten.
- **`_tags_for_category` entfernt** (wurde nur von `_get_city_highlight_activities` genutzt).
- **`get_places` vereinfacht:** Ruft direkt `_fetch_from_opentripmap` auf — keine Highlight-/Berlin-Fallback-Zweige mehr.
- **`from data.mock_berlin import BERLIN_ACTIVITIES`** Import entfernt.

### Betroffene Dateien
- `reiseagent/providers/places.py`

### Tests
- Syntax-Check bestanden.
- `_category_allowed_by_interests('food', [])` → `True` (vorher: `False`).
- `_quality_score` gibt Werte im Bereich 0–100 zurück, ohne IMPORTANT_NAME_WORDS-Abhängigkeit.
- `get_places` gibt bei fehlendem API-Key leere Liste zurück (kein Crash, kein Fallback auf Dummy-Daten).

**Breaking Change:** Nein — `get_places(destination, interests)`-Signatur unverändert. `_normalize_category` erhalten (wird von `_rank_and_deduplicate` genutzt). `providers/telegram.py` nicht angefasst.

---

## [2026-06-28] Feature: Phase 2 — Semantische Dedup, LLM-Kurator, Zeit-/Routen-Agent

**Status:** Merged  
**Datum & Uhrzeit:** 2026-06-28  
**Autor:** Valeriu  

### Zweck
Drei Kernprobleme behoben: (1) Sehenswürdigkeiten wie Notre-Dame tauchten doppelt auf, weil Namens-Varianten aus verschiedenen Quellen nicht erkannt wurden. (2) Die Aktivitätsauswahl war rein deterministisch — jetzt kuratiert ein LLM den gesamten Plan. (3) Uhrzeiten wurden mechanisch berechnet — jetzt weist ein LLM realistische Start-/Endzeiten und Fahrtzeiten zu.

### Was wurde geändert

**`reiseagent/providers/places.py`**:
- `import random` entfernt, `import math`, `import difflib`, `import unicodedata` ergänzt.
- Drei neue Hilfsfunktionen: `_ascii_normalize` (Akzente entfernen), `_strip_fill_words` (Füllwörter wie „cathedral", „museum", „de" entfernen), `_is_same_place` (Kernlogik der semantischen Dedup).
- `_is_same_place` erkennt Duplikate wenn: Koordinaten < 150 m voneinander entfernt **oder** Namens-Ähnlichkeit via `difflib.SequenceMatcher` ≥ 0.82 (nach Akzent-/Füllwort-Normalisierung).
- `_rank_and_deduplicate`: zweite Dedup-Runde mit `_is_same_place` nach der bisherigen Exakt-Namens-Dedup. `random.shuffle` entfernt (LLM sieht stabile, nach `quality_score` sortierte Liste). Pool-Grenze `[:30]` → `[:50]`.

**`reiseagent/prompts.py`**:
- `CURATE_PLAN` (Deutsch): weist das LLM an, aus bis zu 50 Kandidaten einen abwechslungsreichen Mehrtagsplan zu kuratieren. Regeln: keine Duplikate, ≥ 4 Aktivitäten/Tag, max. 2 gleiche Kategorie, mind. 1 food/Tag. Antwort als JSON `{"tage": {"1": [ids...], ...}}`.
- `SCHEDULE_DAY` (Deutsch): weist das LLM an, für eine geordnete Aktivitätsliste realistische Uhrzeiten und Fahrtzeiten festzulegen. Regeln: Mahlzeiten-Anker (Mittag ≥ 12:00, Abend ≥ 18:30), kein Slot nach 23:59. Antwort als JSON-Liste.

**`reiseagent/agents/time_route_agent.py`** *(neu)*:
- `schedule_times_and_routes(ordered_activities, day_start) -> list`: LLM legt `start_time`, `end_time`, `travel_to_next_minutes` für jeden Slot fest.
- Qualitäts-Gate: JSON parsierbar? Richtige Anzahl Einträge? Alle IDs bekannt? `end > start`? Nichts nach 23:59? Keine Überschneidungen?
- Bei Verstoß: 1× Repair-Prompt. Danach LLM-Ausgabe übernehmen (kein deterministischer Fallback — Team-Entscheidung).
- Bei komplett leerem Ergebnis: `planning.py` greift auf deterministisches Slot-Ting zurück.

**`reiseagent/agents/planning.py`**:
- Neue Hilfsfunktionen: `_build_candidate_text`, `_build_weather_summary`, `_validate_curate_response`, `_parse_curate_response`, `_curate_plan`, `_resolve_activities`.
- `_curate_plan`: LLM kuratiert **den gesamten Mehrtagsplan auf einmal** (alle Tage, Top-50-Kandidaten). Qualitäts-Gate → bei Fehler 1× Repair → bei erneutem Fehler Fallback auf `pick_activities_for_day` je Tag.
- `_resolve_activities`: IDs aus LLM-Antwort → vollständige Activity-Dicts mit `estimated_cost_total` und `score` (Budget/Streamlit-Felder vollständig).
- `_deterministic_slots`: bisheriges Zeitslotting als Sicherheitsnetz (nur wenn Zeit-Agent komplett leer liefert).
- `create_plan`: ruft zuerst `_curate_plan`, dann `time_route_agent.schedule_times_and_routes` auf. Beide mit Fallback abgesichert. **Signatur unverändert.**

### Betroffene Dateien
- `reiseagent/providers/places.py`
- `reiseagent/prompts.py`
- `reiseagent/agents/time_route_agent.py` *(neu)*
- `reiseagent/agents/planning.py`

### Tests
- Syntax-Check aller 4 Dateien bestanden.
- Notre-Dame-Varianten (18 m Abstand) → korrekt als Duplikat erkannt.
- Louvre/Tuileries (503 m, verschiedene Namen) → korrekt als verschieden erkannt.
- `Louvre Musée` vs `Louvre Museum` (keine Koordinaten, Namens-Ähnlichkeit) → korrekt zusammengeführt.

**Breaking Change:** Nein — `create_plan`- und `get_places`-Signaturen unverändert, Activity-Dict-Shape vollständig erhalten. `providers/telegram.py` nicht angefasst.

---

## [2026-06-28] Refactor: Phase 1 — LangGraph-Orchestrator für Chat-Routing

**Status:** Merged  
**Datum & Uhrzeit:** 2026-06-28  
**Autor:** Valeriu  

### Zweck
Die ~1300 Zeilen Regex-Routing in `handle_chat_message` wurden durch einen LangGraph-Graphen ersetzt, in dem ein LLM-Orchestrator per Tool-Calling entscheidet, welcher bestehende Handler ausgeführt wird. Die Handler selbst und ihre gesamte Parse-Logik bleiben unverändert; nur die Klassifikation übernimmt jetzt das LLM.

### Was wurde geändert

**`reiseagent/llm.py`**:
- `call_tools(agent_name, messages, tools, prompt_id, model)` ergänzt — schickt eine Nachrichtenliste mit Tool-Schemas an Groq und gibt `("tool", name, args)` oder `("text", content, {})` zurück. Bei fehlendem API-Key oder Fehler: `("text", "", {})` (kein Crash).

**`reiseagent/prompts.py`**:
- Neues Template `ORCHESTRATOR` (Deutsch): weist das LLM an, genau ein Tool für die Nutzeranfrage auszuwählen.

**`reiseagent/graph.py`** *(neu)*:
- `TripState` TypedDict: `trip`, `message`, `reply`, `tool_name`.
- 9 Tool-Schemas (Deutsch): `change_time`, `replan_day`, `suggest_alternatives`, `delete_activity`, `fill_plan`, `replace_activity`, `add_activity`, `sync_calendar`, `answer_question`.
- `_orchestrator_node`: ruft `llm.call_tools()` auf, setzt `tool_name`; ungültiges/kein Tool → Default `answer_question`.
- Ein Handler-Knoten pro Tool (lazy import von coordinator, vermeidet Circular Import).
- Bedingte Kante Orchestrator → Tool-Knoten → END.
- Graph wird einmalig kompiliert (`_compiled_graph`-Cache).
- `run_chat(trip, message) -> dict`: Einstiegsfunktion für coordinator.

**`reiseagent/agents/coordinator.py`**:
- `handle_chat_message`: Regex-Kette (`_try_sync_calendar_from_chat` / `_try_apply_plan_change` / `_groq_response`) entfernt, ersetzt durch `graph.run_chat(trip, message)`.
- Alle Handler-Funktionen (`_change_time_from_chat`, `_replan_day_or_section_from_chat`, `_suggest_alternatives_from_chat`, `_delete_activity_from_chat`, `_fill_plan_from_chat`, `_replace_activity_from_chat`, `_add_activity_from_chat`, `_try_sync_calendar_from_chat`, `_groq_response`) bleiben vollständig erhalten — sie werden jetzt als Tool-Implementierungen aufgerufen.
- Regex-Helfer (`_is_clear_*`, `_category_from_text` etc.) vorerst stehen gelassen.

**`reiseagent/requirements.txt`**:
- `langgraph` eingetragen.

### Betroffene Dateien
- `reiseagent/llm.py`
- `reiseagent/prompts.py`
- `reiseagent/graph.py` *(neu)*
- `reiseagent/agents/coordinator.py`
- `reiseagent/requirements.txt`

### Tests
- Syntax-Check aller 4 geänderten/neuen Dateien bestanden.
- `call_tools` ohne API-Key: gibt `("text", "", {})` zurück, kein Crash.
- Graph kompiliert ohne Fehler.
- `run_chat` ohne API-Key: Orchestrator wählt `answer_question` → `_rule_based_response` antwortet korrekt.

**Breaking Change:** Nein — `handle_chat_message`-Signatur und Rückgabe-Shape (`message`, `agent_insights`, `trace`) identisch. Aufrufer `ui_service.send_chat_command` und `main.py /chat` unverändert. `providers/telegram.py` nicht angefasst.

---

## [2026-06-28] Refactor: Phase 0 — Zentrales `llm.py`, `prompts.py` und Trace-Logging

**Status:** Merged  
**Datum & Uhrzeit:** 2026-06-28  
**Autor:** Valeriu  

### Zweck
Alle vier verstreuten Groq-Inline-Aufrufe wurden durch eine einzige zentrale Schnittstelle ersetzt. Ziel: einheitliches Logging, ein sichtbarer Live-Trace pro Planungsauftrag und alle Prompt-Texte an einem Ort — ohne dass sich das Verhalten ändert.

### Was wurde geändert

**`reiseagent/llm.py`** *(neu)*:
- `call(agent_name, prompt, prompt_id, variables, max_tokens, model)` — einziger Groq-Zugang im Projekt. Kein API-Key oder Fehler → `return None` (kein Crash).
- Internes Logging pro Aufruf: Agent-Name, Prompt-ID, gekürzte Antwort.
- Live-`print` im Terminal bei jedem LLM-Aufruf (z. B. `[suggestion_agent] LLM → 312 Zeichen`).
- Trace-API: `reset_trace()`, `log_step(agent, info, tool)`, `get_trace()` — speichert alle Schritte einer Planung in einer Modul-Liste.

**`reiseagent/prompts.py`** *(neu)*:
- Vier benannte Prompt-Templates verbatim übernommen: `DAILY_BRIEF`, `NAVIGATION_REMINDER`, `SUGGESTION_DAY`, `CHAT_QA`.
- Hilfsfunktion `fill(template, **vars)` — wirft `KeyError` bei fehlender Variable, damit Fehler früh auffallen.

**`reiseagent/agents/daily_brief.py`**:
- Inline-Groq-Aufruf (Z. 62) durch `llm.call(..., prompt_id="DAILY_BRIEF")` ersetzt.
- Fallback-Text bei `None` erhalten.

**`reiseagent/agents/navigation.py`**:
- Inline-Groq-Aufruf (Z. 28) durch `llm.call(..., prompt_id="NAVIGATION_REMINDER")` ersetzt.
- Fallback-Text bei `None` erhalten.

**`reiseagent/agents/suggestion_agent.py`**:
- Inline-Groq-Aufruf (Z. 121) durch `llm.call(..., prompt_id="SUGGESTION_DAY")` ersetzt.
- JSON-Parse-Block und `_pick_activities`-Fallback vollständig erhalten.

**`reiseagent/agents/coordinator.py`**:
- `_groq_response()`: Inline-Groq durch `llm.call(..., prompt_id="CHAT_QA")` ersetzt; bei `None` → `_rule_based_response`.
- `handle_plan_request()`: `llm.reset_trace()` am Anfang, `"trace": llm.get_trace()` additiv im Rückgabe-Dict.
- `handle_chat_message()`: analog — Trace in alle drei Rückgabepfade (calendar_sync, plan_change, groq_response) eingefügt.

### Betroffene Dateien
- `reiseagent/llm.py` *(neu)*
- `reiseagent/prompts.py` *(neu)*
- `reiseagent/agents/daily_brief.py`
- `reiseagent/agents/navigation.py`
- `reiseagent/agents/suggestion_agent.py`
- `reiseagent/agents/coordinator.py`

### Tests
- Syntax-Check aller 6 Dateien bestanden.
- Smoke-Test ohne API-Key: `llm.call()` gibt `None` zurück, Trace enthält `skipped`-Eintrag, `fill()` wirft `KeyError` bei fehlender Variable.
- Fallback-Test `navigation_agent`: Route ohne API-Key liefert korrekten Text inkl. 10-Minuten-Puffer.

**Breaking Change:** Nein — alle bestehenden Signaturen unverändert, Prompts verbatim, `"trace"`-Key additiv (bestehende Konsumenten ignorieren ihn). `providers/telegram.py` nicht angefasst.

---

## [2026-06-23] Fix: Phase A — Kategorie-Vokabular und intelligente Tagesplanung

**Status:** Merged  
**Datum & Uhrzeit:** 2026-06-23  
**Autor:** Valeriu  

### Zweck
Der Empfehlungs- und Planungsagent verhielt sich unintelligent: Restaurants tauchten nie im Plan auf, alle Aktivitäten dauerten 90 Minuten, und 4 Museen am Stück waren möglich. Root Cause war ein stiller Vokabular-Mismatch — `places.py` lieferte normalisierte Kategorienamen (`culture`, `food`, `nature`, `sightseeing`, `shopping`), aber `recommendation.py` und `planning.py` suchten nach den alten Namen (`museum`, `restaurant`, `walk`). Alle Lookups liefen ins Leere.

### Was wurde geändert

**`reiseagent/agents/recommendation.py`:**
- Toten Code entfernt: `TIME_SLOTS_TEMPLATE`, `PREFERRED_MORNING`, `PREFERRED_LUNCH`, `PREFERRED_AFTERNOON`, `PREFERRED_EVENING` (wurden nie benutzt, Kategorienamen waren falsch).
- Neue Konstante `MAX_PER_CATEGORY` — begrenzt wie oft eine Kategorie pro Tag vorkommt (z.B. `culture: 2`, `food: 2`, `sightseeing: 3`). Verhindert „4 Museen am Stück".
- Neue Konstante `MIN_ACTIVITIES_PER_DAY = 4` — Mindest-Aktivitäten pro Tag.
- `pick_activities_for_day()` komplett neu geschrieben mit explizitem Tagesrhythmus:
  - Restaurants werden separat gehalten (`food`-Liste) und nur für Mittag und Abend eingesetzt.
  - Fester Taktung: Vormittag → später Vormittag → **Mittagessen** → Nachmittag → **Abendessen**.
  - Auffüllen mit weiteren Sehenswürdigkeiten wenn kein Restaurant verfügbar.
- Alle Kategorienamen auf normalisiertes Vokabular umgestellt: `culture / food / nature / sightseeing / shopping`.

**`reiseagent/agents/planning.py`:**
- `DURATION_BY_CATEGORY` auf normalisierte Kategorienamen umgestellt:
  - `"food": 75`, `"culture": 120`, `"sightseeing": 90`, `"nature": 60`, `"shopping": 90`
  - Vorher waren alle alten Keys (`museum`, `restaurant`, `walk`) falsch — jede Aktivität fiel auf den Default 90 Min.
- Neue Konstanten `LUNCH_TIME = "12:30"` und `DINNER_TIME = "19:00"`.
- Mahlzeiten-Ankern in `create_plan()`: Wenn eine `food`-Aktivität an der Reihe ist, wird die aktuelle Zeit auf mindestens Mittag- bzw. Abendessenszeit vorgestellt. Das schafft vor dem Restaurant eine freie Pause und stellt sicher, dass Essen nie um 09:15 eingeplant wird.

### Betroffene Dateien
- `reiseagent/agents/recommendation.py`
- `reiseagent/agents/planning.py`

### Tests
- München-Plan generiert: Restaurants erscheinen korrekt um ~12:40 (Mittag) und ~19:00 (Abend).
- Dauern korrekt: Museum 120 Min, Restaurant 75 Min, Park 60 Min (statt immer 90 Min).
- Keine 4 Museen in Folge mehr.
- Syntax-Check erfolgreich.

**Breaking Change:** Nein — Ausgabeformat `time_slots` identisch, keine neuen Abhängigkeiten.

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

