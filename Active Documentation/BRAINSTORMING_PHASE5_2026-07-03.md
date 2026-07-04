# Brainstorming-Session Phase 5 — 2026-07-03

Grundlage: Review-Session mit dem Professor (Feedback zum Ortsfilter/Quality-Score) plus anschließendes Team-Brainstorming zu Flight-Check, Finanzmodell und Feedback-Loop. Ziel des Professors: das Projekt so weit wie möglich "100% agentisch" machen — keine deterministische Vorverarbeitung mehr, wo ein guter Prompt reicht.

Alle Punkte unten sind entschieden (nicht mehr offen), Grundlage für den nächsten Implementierungsplan.

## 1. Ortsfilter & Quality Score entfernen

**Ist-Zustand** (`providers/places.py`): Nach dem OpenTripMap-Abruf läuft eine mehrstufige deterministische Pipeline — Blocklisten `BAD_NAME_WORDS`/`BAD_KIND_WORDS` und Allowlist `IMPORTANT_NAME_WORDS` (`_is_bad_place`, `_is_bad_place_name`), ein regelbasierter 0–100-`_quality_score()` (OpenTripMap-`rate` × 6 plus Kategorie-Boni), Dedup + Sortierung + Kategorie-Kappung (`_rank_and_deduplicate`, `_balance_categories`), semantische Zweitrunde (Koordinaten <150m oder Namensähnlichkeit ≥0.82), finaler Cutoff `quality_score >= 10`. Der Score fließt zusätzlich in `agents/recommendation.py:score_activity()` als ein Signal vor der LLM-Kuration in `planning.py` ein.

**Entscheidung:** Volles Tool-Calling — der LLM-Planer ruft OpenTripMap selbst als Tool auf (analog zum bestehenden `llm.call_tools()`-Mechanismus im Chat-Orchestrator `graph.py`) und übernimmt Filterung, Deduplizierung und Qualitätsurteil per Prompt. Kein Python-Vorfilter, kein Score — auch kein minimaler technischer Datencheck (fehlender Name/Koordinaten wird nicht mehr in Python aussortiert, geht bewusst konsequent alles ans LLM).

**Umfang:** Größerer Umbau als reines Code-Löschen, braucht eine neue Tool-Definition plus Prompt in der Planungskette (`planning.py`/`graph.py`).

## 2. Flight-Check als Orchestrator-Tool

**Ist-Zustand:** `agents/monitoring.py:_refresh_flights()` prüft Verspätungen gegen eine feste 30-Minuten-Schwelle (`FLIGHT_DELAY_THRESHOLD_MINUTES`) und ruft bei Überschreitung direkt `replanning.create_flight_delay_proposal()` auf, die sämtliche Zeitslots von Tag 1 stur um den Verspätungsbetrag verschiebt — ohne jede LLM-Beteiligung. Die Polling-Frequenz wird über `required_interval_seconds()` anhand der Zeit bis zum Abflug gestaffelt (15 Min. wenn ≤2h entfernt, 1h wenn ≤6h, 6h wenn ≤24h, keine Prüfung wenn weiter weg oder in der Vergangenheit).

**Kritikpunkt:** Weder die Erkennung von Relevanz (feste 30-Minuten-Schwelle ignoriert Kontext wie eng getaktete Tage) noch die Reaktion (mechanische Zeitverschiebung ohne Rücksicht auf Öffnungszeiten oder Budget) nutzen das vorhandene LLM-Orchestrierungssystem. Die Polling-Frequenz-Logik selbst ist davon ausgenommen — das ist reine Infrastruktur-Optimierung ohne inhaltliches Urteilsvermögen und muss nicht "agentisch" werden.

**Entscheidung:** Der Monitoring-Agent bleibt als deterministischer Trigger bestehen (Polling-Intervall bleibt Code). Sobald eine relevante Statusänderung erkannt wird, wird aber nicht mehr direkt die feste Proposal-Funktion aufgerufen, sondern derselbe LLM-Orchestrator wie im Chat (`graph.py`, bestehender `replan_day`-Pfad) mit einer synthetischen Nachricht angestoßen (z.B. "Flug LH123 hat 45 Minuten Verspätung, prüfe Auswirkung auf den Tagesplan"). Die inhaltliche Neuplanung — inklusive Öffnungszeiten- und Budget-Prüfung — übernimmt der bestehende Chat-Pfad, statt einer separaten, stumpfen Verschiebe-Logik.

## 3. Finanzmodell — dynamische Kostenschätzung

**Ist-Zustand:** `providers/places.py:_estimate_cost()` vergibt pauschal 20€ (food) / 12€ (culture) / 0€ sonst, unabhängig vom konkreten Ort. `agents/budget.py` ist reine Arithmetik (Summierung, Vergleich mit `budget_total`) — bewusst ohne KI.

**Entscheidung:** Ein neuer Agent schätzt die Kosten pro Aktivität individuell (ortsspezifisch, Personenzahl berücksichtigt). Die Summenbildung und der Vergleich mit dem Budget in `budget.py` bleiben deterministische Arithmetik — dafür ist kein LLM nötig, das bleibt unverändert.

**Budget-Überschreitung:** Vollautomatische Iterationsschleife — der Agent passt den Plan bei Überschreitung intern mehrfach an, bis er unters Budget kommt (braucht eine Obergrenze an Versuchen gegen Endlosschleifen — konkrete Zahl noch für den Implementierungsplan offen).

**Websuche — final verworfen (2026-07-03):** Zwei Ansätze wurden diskutiert und beide wieder verworfen: erst `groq/compound-mini` (kostet Geld), dann eigenes `providers/tavily.py` (Free-Tier, aber zusätzliches Modul + Credit-Management). Team-Entscheidung: **keine Websuche.** Das bestehende `llama-3.3-70b-versatile` schätzt Preise direkt aus seinem Trainingswissen (Ort, Kategorie, Personenzahl im Prompt) — kein neuer Key, kein neues Modul, keine Rate-Limits. Grenze bewusst akzeptiert: keine live-aktuellen Preise, aber für ein Uni-Projekt/MVP reicht eine plausible Kategorie-/Stadt-Ebene-Schätzung völlig aus.

## 4. Simuliertes Bankkonto (interaktiv via Telegram)

Neue Tabelle(n) in `profile_store.py`: Fixkosten, Einnahmen/Gehalt, freier Betrag, Reisebudget-Rücklage. Statt Web-Formular fragt das System am Monatsersten proaktiv per Telegram nach Einnahmen und Fixkosten und schlägt einen Reisebudget-Betrag vor. Bei Trip-Erstellung (manuell oder Annahme eines Telegram-Vorschlags vom wöchentlichen Scheduler) werden die geschätzten Reisekosten vom simulierten Kontostand abgezogen.

**Entschieden (aktualisiert):** Die Subtraktions-Logik wird normal implementiert, sobald der Kostenschätzungs-Agent (Punkt 3) einen Kostenwert liefert — keine gesonderte Verzögerung. Negativer Kontostand ist während der Testphase explizit erlaubt (kein Fehler, keine Warnung), da wiederholtes manuelles Testen (mehrere Trips/Vorschläge annehmen) den simulierten Kontostand sonst verfälschen würde; vor einer Demo wird die Tabelle zurückgesetzt.

## 5. Feedback-/Rating-Agent am Trip-Ende

Trigger: Trip-Enddatum (Kalender/DB) entspricht dem heutigen Datum → Telegram-Nachricht fragt nach Zufriedenheit (z.B. Museen, Essen). Die Antwort des Nutzers wird von einem Agenten interpretiert, registriert und gespeichert.

**Entscheidung (Schema):** Neue eigene Tabelle `trip_feedback` in `profile_store.py` (trip_id, Ziel, Kategorie, Rating 1–5, Freitext-Kommentar, Datum) statt Vermischung mit der bestehenden `interests`-Tabelle — sauber trennbar für spätere Auswertung (z.B. "wie haben Museen in Paris abgeschnitten"), kann später zusätzlich als Signal in `agents/recommendation.py:score_activity()` einfließen.

**Wichtiger Zusatzfund (2026-07-03):** Es gibt aktuell **keinen Mechanismus**, der eine Freitext-Antwort gezielt als Feedback erkennt. `providers/telegram.py:get_recent_messages()` holt unterschiedslos alle Nachrichten eines Zeitfensters, und `agents/profile_learner.py:learn_from_telegram()` schiebt jede davon blind durch Keyword-Extraktion + `memory.store_message()` in die Vektor-DB — ohne jede Rating-Erkennung. Es gibt auch keinen Live-Poller für normalen Text (nur `_telegram_callback_loop` pollt, aber ausschließlich Button-Klicks). Nötig: eine neue `pending_prompts`-Tabelle (merkt sich offene Fragen) + eine neue additive Funktion `providers/telegram.py:get_message_updates(offset)` (Offset-Cursor-Muster wie das bestehende `get_callback_updates()`, aber für `allowed_updates: ["message"]`) + ein Poller, der eingehende Nachrichten bei offenem Pending-Prompt an den richtigen Interpreter routet statt an die generische Pipeline. Diese Infrastruktur wird von Feedback-Agent UND Bankkonto-Monatscheck gemeinsam gebraucht — Details siehe `PHASE5_TEAM_PLAN_2026-07-03.md`, Modul D.

## Zusätzlich: Aufräumen vor Phase 5

Toter Code in `coordinator.py`: `_try_apply_plan_change()` (Z. 276–313) plus die Helfer `_is_clear_time_change_request`, `_is_clear_replan_request`, `_is_clear_replace_request` (Z. 395–434) — seit der LangGraph-Umstellung (Phase 2) unbenutzt, kann komplett entfernt werden.

## Offen für die Implementierungsplanung (kein Zieldefinitions-Thema mehr)

- Anzahl der Iterationsversuche in der Budget-Loop (Punkt 3).
- Genaues DB-Schema für `trip_feedback` final festlegen.
- Aufteilung der 5 Bereiche auf 4 Teammitglieder (2er-Konstellationen erlaubt, jedes Mitglied mit möglichst unabhängigem Fokusbereich) — nächster Schritt.
