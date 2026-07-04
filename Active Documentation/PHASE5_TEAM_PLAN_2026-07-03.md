# Phase 5 — Modularer Implementierungsplan für 4 Teammitglieder

Basis: `BRAINSTORMING_PHASE5_2026-07-03.md` (Zieldefinition) + `IMPLEMENTIERUNGSPLAN_PHASE_0-5.md` (technischer Vorentwurf, jetzt aktualisiert). Vier Module, jedes unabhängig startbar. 2er-Teams sind möglich (siehe "Team-Aufteilung" am Ende), aber jedes Modul ist auch solo bearbeitbar.

## Permanente Spielregeln (gelten für ALLE Module)

- **Coding-Stil:** einfaches Anfänger-Python, keine Klassen, minimale Fehlerbehandlung, flache Imports (`import llm`, nicht `from reiseagent import ...`). Aus `reiseagent/` starten.
- **`providers/telegram.py` strukturell nicht anfassen** — nur additive neue Funktionen, bestehende nicht verändern.
- **Bestehende Signaturen nicht brechen:** `get_places(destination, interests)`, `create_plan(request, all_activities, weather)`, `handle_plan_request(...)`, `handle_chat_message(trip, message)`, `pick_activities_for_day(...)` (als Fallback erhalten), `score_activity(...)`, Activity-Dict-Shape vollständig.
- **Alter Pfad bleibt Fallback:** Wenn `GROQ_API_KEY` fehlt oder ein LLM-/Tool-Call fehlschlägt, muss das System nicht abstürzen — bestehende deterministische Logik bleibt als Rückfallebene nutzbar (Vorbild: `llm.call()` gibt `None` zurück, Aufrufer fangen das ab).
- **LLM-Prompts auf Englisch, Ortsnamen original, UI-Texte Deutsch.** Kategorien bleiben `culture / food / nature / sightseeing / shopping`.
- `GROQ_API_KEY` muss in `reiseagent/.env` stehen, sonst laufen alle LLM-Aufrufe nur im Fallback. `credentials.json`/`calendar_token.json` liegen in `reiseagent/`, nicht im Projekt-Root.

---

## Modul A — Ortsfilter → Agentisches Tool-Calling

**Betrifft:** `providers/places.py`, `planning.py`, `graph.py`, `prompts.py`

**Ziel:** Vorfilter (`_is_bad_place`, `BAD_NAME_WORDS`/`BAD_KIND_WORDS`), `_quality_score()` und den Cutoff `quality_score >= 10` entfernen. Der LLM-Planer bekommt ein Tool, um OpenTripMap selbst aufzurufen (wie `llm.call_tools()` es im Chat-Orchestrator schon vormacht), und übernimmt Filterung/Dedup/Qualitätsurteil per Prompt.

**Kernaufgaben:**
1. Neues Tool definieren, das die rohe OpenTripMap-Abfrage kapselt (Wrapper um die bestehende Fetch-Logik in `_fetch_from_opentripmap`, aber **ohne** den Filter-/Score-Teil) — Rohdaten gehen unverändert durch.
2. Prompt schreiben, der dem LLM erklärt: schlechte Namen (Straßen, Parkplätze, Denkmäler o.ä.) ausschließen, Duplikate (gleicher Ort, ähnlicher Name) zusammenführen, nach Relevanz/Qualität sortieren, Kategorie-Balance beachten.
3. `get_places(destination, interests)` bleibt als äußere Funktion bestehen — innen ruft sie jetzt den Tool-Calling-Pfad auf, mit der bisherigen gefilterten Logik als Fallback, falls kein API-Key oder der Tool-Call fehlschlägt.
4. Nur die **Feldnamen** des Activity-Dicts (`estimated_cost_per_person`, `location`, `category` etc.) bleiben exakt gleich — nicht die Werte darin. `budget.py` und andere Stellen lesen diese Felder namentlich; würden sie umbenannt, bräche alles andere.
5. **Entwickler-Sichtbarkeit (neu, 2026-07-03 ergänzt):** Kleines Dump-Skript (z.B. `scripts/debug_places_raw.py`, Stil wie `test_all.py`), das nur den rohen Fetch-Wrapper (ohne Filter) aufruft und die volle unbereinigte Liste als JSON in eine Datei schreibt — zum manuellen Prüfen, wie viele Rohdaten fehlende Namen/Koordinaten haben. Zusätzlich den Filter-Prompt so schreiben, dass das LLM kurz begründet, welche Kandidaten verworfen wurden und warum (z.B. "kein Name", "Duplikat von X") — über `llm.log_step()` mitloggen (bestehendes Trace-System, `llm.get_trace()`), taucht dann automatisch in den Trip-Insights auf. Ergänzend ein Testfall mit synthetischen Lücken (fehlender Name, fehlende Koordinaten, Duplikate) gegen den neuen Filter-Prompt, mit lockerer Assertion (LLM-Output ist nicht 100% deterministisch).

**Schnittstelle zu Modul C:** Modul C ersetzt komplett, *wie* der Wert von `estimated_cost_per_person`/`estimated_cost_total` berechnet wird (aktuell die Pauschale aus `places.py:_estimate_cost()`) — das ist ausdrücklich gewollt. Die einzige Absprache: der **Schlüsselname** bleibt gleich, damit `budget.py` unverändert funktioniert.

---

## Modul B — Flight-Check als Orchestrator-Tool

**Betrifft:** `agents/monitoring.py` (`_refresh_flights`, Trigger bei Z. 226), `graph.py` (Tool-Pfad/`replan_day`), `agents/replanning.py` (`create_flight_delay_proposal` wird Fallback), `agents/coordinator.py:81` (Erstanpassung bei Trip-Erstellung)

**Ziel:** Bei erkannter Verspätung ruft der Monitoring-Agent nicht mehr direkt die starre `create_flight_delay_proposal()` (die stur alle Tag-1-Slots verschiebt), sondern stößt den bestehenden LLM-Orchestrator (`graph.py`, `replan_day`-Pfad) mit einer synthetischen Nachricht an ("Flug X hat Y Minuten Verspätung — prüfe Auswirkung auf den Tagesplan"). Der Orchestrator übernimmt die inhaltliche Anpassung inkl. Öffnungszeiten-/Budget-Prüfung.

**Kernaufgaben:**
1. Klären, wie eine "synthetische" Chat-Nachricht ohne echten Nutzer-Input in `graph.run_chat(trip, message)` eingespeist wird (kein neuer User-Turn, sondern intern ausgelöst).
2. Polling-Intervall-Logik (`required_interval_seconds()`, Z. 341) **unverändert lassen** — reine Infrastruktur, kein LLM-Urteil nötig.
3. Alte `create_flight_delay_proposal()`-Logik als Fallback behalten, falls der Orchestrator-Call fehlschlägt (kein API-Key, Timeout etc.).
4. **Wichtig:** Doppelte Flug-API-Calls vermeiden — klare Zuständigkeit zwischen Monitoring (Hintergrund-Polling) und Orchestrator (inhaltliche Neuplanung nach erkannter Änderung), nicht beide unabhängig voneinander die Flight-API abfragen lassen.

**Schnittstelle zu anderen Modulen:** keine direkte Abhängigkeit — kann parallel zu A, C, D starten.

---

## Modul C — Finanzmodell: Kostenschätzungsagent + Budget-Loop

**Betrifft:** neue Datei `agents/cost_estimation.py`, `planning.py` (Integration nach Plan-Erstellung), `agents/budget.py` (bleibt reine Arithmetik, bekommt aber bessere Werte), `prompts.py`

**Ziel:** Statt Pauschalpreisen (`places.py:_estimate_cost()`: 20€ food / 12€ culture / 0€ sonst) schätzt ein neuer Agent die Kosten pro Aktivität individuell — ortsspezifisch, unter Berücksichtigung der Personenzahl. Bei Budgetüberschreitung passt eine automatische Iterationsschleife den Plan mehrfach an, bis er passt.

**Kernaufgaben:**
1. Kostenschätzungs-Agent bauen: pro Aktivität einen Prompt mit Ort/Kategorie/Personenzahl aufrufen, `estimated_cost_per_person`/`estimated_cost_total` aktualisieren.
2. **Keine Websuche (final entschieden 2026-07-03, ersetzt sowohl Groq-Compound- als auch Tavily-Idee):** Team hat sich bewusst für die einfachste Variante entschieden — kein separater Such-Provider, keine Extra-API, kein Cache-Management. Stattdessen: das bestehende `llama-3.3-70b-versatile` (dasselbe Modell wie überall sonst im Projekt) schätzt aus seinem Trainingswissen einen plausiblen Preis pro Aktivität (Ort, Kategorie, Personenzahl im Prompt). Kein neuer Key, kein neues Modul, keine Rate-Limits zu beachten. Grenze: keine live-aktuellen Preise, für ein Uni-Projekt/MVP aber ausreichend genau (Kategorie-/Stadt-Ebene reicht, exakte Cent-Beträge waren nie das Ziel).
3. Budget-Vergleich bleibt in `budget.py` (reine Summierung, kein LLM) — nur die Eingabewerte werden jetzt besser.
4. Iterationsschleife: bei `status == "over_budget"` (aus `calculate_budget()`) den Plan erneut anpassen lassen (günstigere Alternativen, weniger Aktivitäten). **Obergrenze an Versuchen einbauen** (z.B. 3), um Endlosschleifen zu vermeiden — konkrete Zahl mit Team abstimmen.

**Schnittstelle zu Modul A:** braucht die stabilen Feldnamen des Activity-Dicts aus Modul A, nicht die alten Werte — die werden ja gerade hier in Modul C neu berechnet.
**Schnittstelle zu Modul D:** liefert den finalen Trip-Gesamtpreis für die Kontostand-Subtraktion in Modul D.

---

## Modul D — Simuliertes Bankkonto + Feedback-Agent

Gebündelt, weil beide Teile dieselbe Infrastruktur brauchen: neue Tabellen in `profile_store.py` und einen proaktiven Telegram-Trigger nach dem Vorbild des bestehenden `scheduler.py` (dort: wöchentlicher Samstags-Check; hier: monatlicher Check bzw. täglicher Trip-Ende-Check).

**Betrifft:** `profile_store.py` (neue Tabellen), `scheduler.py` (neue Trigger-Funktionen nach bestehendem Muster), `providers/telegram.py` (nur additive neue Funktionen), `main.py` (ggf. manueller Test-Endpunkt wie `/api/scheduler/run`)

**Vorarbeit für beide Teile — Pending-Prompt-Routing (neu, 2026-07-03 ergänzt):**
Aktuell gibt es **keinen** Mechanismus, der Freitext-Telegram-Antworten gezielt zuordnet. `providers/telegram.py:get_recent_messages()` holt unterschiedslos alles im Zeitfenster, und `agents/profile_learner.py:learn_from_telegram()` schiebt jede Nachricht blind durch Keyword-Extraktion + `memory.store_message()` (Vektor-DB). Es gibt auch keinen Live-Poller für normalen Text — nur `_telegram_callback_loop` (main.py:569) pollt, aber ausschließlich `allowed_updates: ["callback_query"]` (Button-Klicks). Damit Bankkonto-Check-in UND Feedback-Antworten korrekt ankommen (statt in der generischen Interessen-Pipeline zu versickern), zuerst bauen:
1. Neue Tabelle `pending_prompts` (type: `feedback`/`bank_checkin`, trip_id nullable, created_at, resolved).
2. Neue additive Funktion in `providers/telegram.py`, z.B. `get_message_updates(offset)` — exakt wie das bestehende `get_callback_updates(offset)` (Z. 287), aber mit `allowed_updates: ["message"]` statt `["callback_query"]`, inkl. Offset-Cursor.
3. Poller (kann bestehenden 5-Sekunden-Loop erweitern): neue Nachricht → offenen `pending_prompts`-Eintrag? Ja → an passenden Interpreter routen (Bankkonto- oder Feedback-Agent), als erledigt markieren. Nein → unverändertes Verhalten von heute (generischer Batch-Pfad).

**Teil 1 — Bankkonto:**
1. Neue Tabelle(n): Fixkosten, Einnahmen, freier Betrag, Reisebudget-Rücklage.
2. Monatlicher Telegram-Trigger (Check "ist heute der 1.?", analog zum bestehenden Samstags-Check in `scheduler.py`) fragt nach Einnahmen/Fixkosten, legt `pending_prompts`-Eintrag (`bank_checkin`) an, schlägt nach Antwort ein Reisebudget vor.
3. Subtraktion bei Trip-Erstellung/-Annahme: normal implementieren, sobald Modul C einen Kostenwert liefert — keine gesonderte Verzögerung.
4. Negativer Kontostand ist während der Testphase erlaubt (kein Fehler/keine Warnung); vor einer Demo wird die Tabelle zurückgesetzt.

**Teil 2 — Feedback-Agent:**
1. Neue Tabelle `trip_feedback` (trip_id, Ziel, Kategorie, Rating 1–5, Freitext-Kommentar, Datum).
2. Täglicher Trigger: prüft anhand Trip-Enddatum + neuem Flag `feedback_requested`, ob heute eine Frage fällig ist → Telegram-Nachricht fragt nach Zufriedenheit, legt `pending_prompts`-Eintrag (`feedback`) an.
3. Trifft die nächste Nachricht ein, während der Eintrag offen ist: `agents/feedback_agent.py:interpret_feedback(trip, text)` extrahiert per LLM ein Rating 1–5 + Kurzkommentar pro erwähnter Kategorie (culture/food/nature/sightseeing/shopping; nicht erwähnte Kategorien werden weggelassen) und speichert je Kategorie eine Zeile in `trip_feedback`.
4. Warum eigene Tabelle statt Integration in `interests`: `interests.score` bedeutet aktuell "passiv gezählte Keyword-Treffer" — ein bewusstes 1–5-Rating ist semantisch etwas anderes und würde entweder die Bedeutung von `score` verwässern oder eine Diskriminator-Spalte nötig machen (baut effektiv doch wieder eine zweite Struktur). Trip-Bezug, Datum und Freitext-Kommentar passen zudem nicht ins bestehende `interests`-Schema (category, keyword, score, source).
5. Optional (spätere Ausbaustufe, nicht Teil des MVP): Rückkopplung in `agents/recommendation.py:score_activity()` als zusätzliches Signal.

---

## Team-Aufteilung — zwei mögliche Schnitte

**Variante 1 — vier Solo-Foki (empfohlen, wenn jede Person unabhängig arbeiten will):**
- Person 1: Modul A (Ortsfilter)
- Person 2: Modul B (Flight-Check)
- Person 3: Modul C (Finanzmodell)
- Person 4: Modul D (Bankkonto + Feedback)

**Variante 2 — zwei 2er-Teams nach thematischer Nähe:**
- Team 1 (Modul A + B): beide sind "Deterministik → LLM-Tool-Calling"-Refactors, beide erweitern `graph.py` um neue Tools — ähnliches Vorgehen, gute gegenseitige Code-Reviews.
- Team 2 (Modul C + D): beide drehen sich um Geld/Nutzerverhalten, beide brauchen neue `profile_store.py`-Tabellen und Telegram-Interaktion nach demselben Muster.

## Empfohlene Reihenfolge / Sync-Punkte

- Alle vier Module können sofort parallel starten.
- Einziger nötiger Sync: Modul A und Modul C sollten sich zu Beginn kurz auf die Feldnamen des Activity-Dicts einigen (bleiben wie in `models.py` dokumentiert) — danach keine weitere Kopplung nötig.
- Modul D (Bankkonto-Subtraktion) braucht lediglich einen fertigen Kostenwert aus Modul C, um zu greifen — ansonsten keine Reihenfolge-Vorgabe mehr.
