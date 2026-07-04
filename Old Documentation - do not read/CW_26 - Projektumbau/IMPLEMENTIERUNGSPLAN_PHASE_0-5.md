# Implementierungspläne — Phase 0 bis 5

> Erstellt auf Basis von `UMBAU_VORSCHLAG.md` (maßgebliche Quelle) und der Tiefenanalyse des
> tatsächlichen Codes in `reiseagent/`. Jeder Plan folgt derselben Struktur:
> **Ziel · Neue Dateien · Geänderte Dateien · Schritt-für-Schritt · Integrationspunkte · Risiken · Testbarkeit · Offene Fragen.**

## Permanente Constraints (gelten für ALLE Phasen)
- **Coding-Stil:** simple Python für Anfänger. Minimale Ausnahmebehandlung, wenig Abstraktion, keine unnötigen Klassen, kein Over-Engineering. Kurz, lesbar, leicht änderbar.
- **`providers/telegram.py` (A3) nicht anfassen.** Wenn Telegram-Daten gebraucht werden, geschieht das **außerhalb** dieser Datei (Aufrufer lesen/schreiben, telegram.py bleibt unverändert).
- **Signaturen nicht brechen** (UMBAU_VORSCHLAG.md §9): `get_places(destination, interests)`, `create_plan(request, all_activities, weather)`, `handle_plan_request(request, use_mock_weather)`, `handle_chat_message(trip, message)`, `pick_activities_for_day(...)` (als Fallback erhalten), `score_activity(...)` (`quality_score`/`overall_score` bleiben Zahl), **Activity-Dict-Shape** vollständig.
- **LLM-Prompts auf Englisch**, Ortsnamen original. **UI-Texte Deutsch.** (Ausnahme Phase 0: bestehende Prompts werden zunächst verhaltensgleich übernommen — siehe dort.)
- **Kategorien:** nur `culture / food / nature / sightseeing / shopping`.

## Abhängigkeits-Überblick (welche Phase braucht welche)
```
Phase 0 (llm.py, prompts.py, Trace)  ── Fundament für alle LLM-Phasen
   └─► Phase 1 (LangGraph-Chat)       braucht Tool-Calling in llm.py
   └─► Phase 2 (Planning/Zeit-Routen) braucht llm.call + Repair-Muster
          └─► Phase 3 (RAG/Memory)    injiziert Kontext in Planning-Prompt (Phase 2)
                 └─► Phase 4 (Scheduler/Kalender-LLM) nutzt RAG + Vorschlags-Agent
                        └─► Phase 5 (Flug-Entscheidung, Finanz, Feedback) nutzt Orchestrator (Phase 1)
```
Phase 0 und 1 sind der aktuelle Fokus; 2–5 folgen, wenn Zeit da ist.

---
---

# Phase 0 — Fundament: zentrales `llm.py` + `prompts.py` + Trace-Logging

### 1. Ziel
Alle Groq-Aufrufe laufen künftig durch **eine** zentrale Stelle mit einheitlichem Logging und Live-Terminal-Trace, und alle System-Prompts liegen als sichtbare Templates an **einem** Ort — ohne dass sich das Verhalten ändert.

### 2. Neue Dateien
- **`reiseagent/llm.py`** — zentraler Groq-Zugang. Eine Funktion `call(...)` (Text rein → Text raus), zentrales Logging pro Aufruf, ein in-memory Trace + Live-`print`. Kein Tool-Calling in Phase 0 (kommt in Phase 1).
- **`reiseagent/prompts.py`** — alle System-/User-Prompt-Templates als benannte Strings mit `{variablen}`. Eine winzige Hilfsfunktion `fill(template, **vars)` (= `template.format(**vars)`), damit fehlende Variablen früh auffallen.

### 3. Geänderte Dateien
| Datei | Was genau ändert sich |
|---|---|
| `agents/daily_brief.py` (Groq-Call Z.62) | Inline-Groq durch `llm.call(...)` ersetzen; Prompt verbatim nach `prompts.py` (`DAILY_BRIEF`). **Nur Transport-Swap, kein Logik-/Prompt-Inhalt geändert** (Tagesbrief bleibt eingefroren). |
| `agents/navigation.py` (Groq-Call Z.28) | Inline-Groq durch `llm.call(...)`; Prompt → `prompts.py` (`NAVIGATION_REMINDER`). Fallback bei fehlendem Key bleibt erhalten. |
| `agents/suggestion_agent.py` (Groq-Call Z.121) | Inline-Groq durch `llm.call(...)`; Prompt → `prompts.py` (`SUGGESTION_DAY`). JSON-Parsing + bestehender `_pick_activities`-Fallback bleiben. |
| `agents/coordinator.py` (`_groq_response` Z.1575) | Inline-Groq durch `llm.call(...)`; Prompt → `prompts.py` (`CHAT_QA`). Bei `None` (kein Key/Fehler) weiterhin `_rule_based_response`. |

### 4. Schritt-für-Schritt-Ablauf
1. **`prompts.py` anlegen.** Die 4 bestehenden Prompttexte 1:1 hineinkopieren (verbatim, inkl. heutiger Sprache — Verhalten bleibt gleich). Helper `fill(template, **vars)` ergänzen.
2. **`llm.py` anlegen** mit:
   - `call(agent_name, prompt, prompt_id="", variables=None, max_tokens=500, model="llama-3.3-70b-versatile")` → liest `GROQ_API_KEY`; kein Key oder Fehler → **`return None`** (Logeintrag „skipped/error"); sonst Groq aufrufen, Text zurückgeben.
   - Logging pro Aufruf: `agent_name`, `prompt_id`, `variables`, `model`, gekürzte Antwort.
   - **Trace-API:** Modul-Liste `STEPS = []`; `reset_trace()`, `log_step(agent, info, tool="")`, `get_trace()`. `call()` ruft intern `log_step` auf und macht einen Live-`print` (z. B. `[suggestion_agent] LLM → 312 Zeichen`).
3. **`daily_brief.py` umstellen:** `client.chat...` → `text = llm.call("daily_brief_agent", prompts.fill(prompts.DAILY_BRIEF, ...), prompt_id="DAILY_BRIEF")`; wenn `text is None`, bestehenden Klartext-Fallback nutzen.
4. **`navigation.py` umstellen** (analog, Fallback erhalten).
5. **`suggestion_agent.py` umstellen** (analog; JSON-Parse + `_pick_activities`-Fallback bleiben).
6. **`coordinator._groq_response` umstellen:** `llm.call(...)`; `None` → `_rule_based_response`.
7. **Trace sichtbar machen (minimal):** in `handle_plan_request` und `handle_chat_message` am Anfang `llm.reset_trace()`; am Ende `llm.get_trace()` als zusätzlichen Schlüssel `"trace"` ins Ergebnis legen (additiv — bestehende Konsumenten lesen feste Keys, brechen also nicht).

### 5. Integrationspunkte
- Hängt an **nichts** Vorherigem (erste Phase).
- Liefert die Grundlage, auf der Phase 1 das **Tool-Calling** in `llm.py` ergänzt und Phase 2 das **Repair-Muster** aufsetzt.

### 6. Risiken & Fallstricke
- **Verhalten darf sich nicht ändern.** Deshalb Prompts verbatim übernehmen (noch nicht ins Englische übersetzen) und alle bestehenden Fallbacks erhalten. Die Englisch-Umstellung passiert je Agent in dessen eigener späterer Phase.
- **`None`-Kontrakt konsequent:** Jeder Aufrufer muss `if text is None:` abfangen, sonst bricht der Pfad ohne API-Key.
- **Import-Pfad:** Projekt nutzt `sys.path.insert(0, reiseagent/)` (siehe `main.py:6`). `import llm` / `import prompts` funktioniert dann flach — nicht `from reiseagent import llm`.
- **Tagesbrief-Spannung:** „eingefroren" vs. „4 Calls umstellen" — siehe offene Frage.

### 7. Testbarkeit
- App/CLI starten, einen Chat-Q&A-Befehl absetzen → im Terminal erscheint eine Trace-Zeile, Antwort inhaltlich wie vorher.
- `GROQ_API_KEY` temporär leeren → alle 4 Stellen fallen sauber auf ihren bisherigen Fallback zurück (kein Crash).
- Einen Vorschlag erzeugen → JSON-Pfad + Fallback prüfen.

### Entschiedene Fragen
- **Tagesbrief-Agent:** ✅ `daily_brief.py` wird auf `llm.call()` umgestellt — reiner Transport-Swap (gleiches Verhalten, gleicher Prompt, nur zentrales Logging).
- **Prompt-Sprache:** ✅ In Phase 0 verbatim lassen (bestehende Prompts unverändert übernehmen, Sprache wie sie ist). Englisch-Umstellung je Agent in späterer Phase.

---
---

# Phase 1 — Orchestrator (Chat) mit LangGraph

### 1. Ziel
Die ~1300 Zeilen Regex-Routing in `handle_chat_message` werden durch einen **LangGraph-Graphen** ersetzt, in dem ein **LLM-Orchestrator per Tool-Calling entscheidet**, welcher bestehende Handler (planen/ändern/löschen/auffüllen/ersetzen/vorschlagen/Kalender-Sync/Q&A) ausgeführt wird.

### 2. Neue Dateien
- **`reiseagent/graph.py`** — baut den LangGraph-`StateGraph` mit gemeinsamem `TripState` (dict: `trip`, `message`, `reply`). Ein Orchestrator-Knoten + ein Knoten pro Tool. Einstiegsfunktion `run_chat(trip, message) -> dict`.

### 3. Geänderte Dateien
| Datei | Was genau ändert sich |
|---|---|
| `reiseagent/llm.py` | **Tool-Calling ergänzen:** `call_tools(agent_name, messages, tools, prompt_id="") -> ("tool", name, args) \| ("text", content)`. (Groq unterstützt OpenAI-style `tools`.) `call()` aus Phase 0 bleibt unverändert. |
| `reiseagent/prompts.py` | Neues Template `ORCHESTRATOR` (Englisch): „You are the travel coordinator. Use a tool to fulfil the user's request. Decide which one." + Tool-Beschreibungen. |
| `agents/coordinator.py` | `handle_chat_message` (Z.262) ruft intern **`graph.run_chat(trip, message)`** statt der Regex-Kette. Die bestehenden Handler-Funktionen (`_change_time_from_chat`, `_replan_day_or_section_from_chat`, `_suggest_alternatives_from_chat`, `_delete_activity_from_chat`, `_fill_plan_from_chat`, `_replace_activity_from_chat`, `_add_activity_from_chat`, `_try_sync_calendar_from_chat`, `_groq_response`) **bleiben als Funktionen erhalten** und werden zu Tool-Implementierungen. Die `_is_clear_*`/`_category_from_text`-Regex-Helfer werden **nicht** mehr zum Routen gebraucht (können vorerst bleiben, später entfernt). |

### 4. Schritt-für-Schritt-Ablauf
1. **LangGraph installieren** (`langgraph` in `requirements.txt`/`package`-Umgebung).
2. **`llm.call_tools` ergänzen** (Tool-Calling + gleiches Logging/Trace wie `call`).
3. **Tool-Liste definieren** (in `graph.py`): je ein Tool-Schema (`name`, `description`, minimale Parameter) für: `change_time`, `replan_day`, `suggest_alternatives`, `delete_activity`, `fill_plan`, `replace_activity`, `add_activity`, `sync_calendar`, `answer_question`. **Wichtig (risikoarm):** Der Orchestrator wählt nur das **Intent/Tool**; die rohe Nutzer-`message` wird an den bestehenden Handler durchgereicht, der sein eigenes Parsing behält. So ersetzt der LLM die **Klassifikation** (1.3), nicht die Handler.
4. **Knoten bauen:** Orchestrator-Knoten ruft `call_tools` → setzt `state["tool"]`. Pro Tool ein Knoten, der den bestehenden Handler `(trip, message)` aufruft und `state["reply"]` setzt.
5. **Kanten:** Einstieg → Orchestrator → (bedingte Kante nach `state["tool"]`) → Tool-Knoten → `END`. Wählt der LLM kein Tool → `answer_question`-Knoten (= `_groq_response`).
6. **`handle_chat_message` umbauen:** `_try_sync_calendar_from_chat`/`_try_apply_plan_change`-Kette entfernen, durch `return graph.run_chat(trip, message)` ersetzen. **Rückgabe-Shape `{message, agent_insights, …}` exakt erhalten** (Handler liefern bereits dieses Format).
7. **Trace anreichern:** Orchestrator-Entscheidung + gewähltes Tool über `llm.log_step` in den Trace (für UI-Expander + Live-Terminal).

### 5. Integrationspunkte
- **Braucht Phase 0** (`llm.py`, `prompts.py`, Trace) — `call_tools` ist die Erweiterung.
- Aufrufer `ui_service.send_chat_command` (Z.68) und `main.py /chat` (Z.217) bleiben unverändert, weil `handle_chat_message`-Signatur/Rückgabe gleich bleiben.

### 6. Risiken & Fallstricke
- **Höchstes Risiko der frühen Phasen:** Viel hängt an `handle_chat_message`. Strikt die Rückgabeform wahren; Handler unverändert lassen.
- **Handler mutieren `trip` in-place** und rufen `_refresh_plan_after_change` (Kalender-Sync + `send_plan_update`). Dieses Verhalten muss erhalten bleiben — die Knoten dürfen die Handler nur aufrufen, nicht umschreiben.
- **A3 Telegram:** Handler nutzen `send_plan_update` — das ist erlaubt (Aufruf), `telegram.py` selbst bleibt unangetastet.
- **LLM wählt falsches/kein Tool:** Default-Knoten `answer_question` als sichere Auffanglinie; optional max. 1 Orchestrator-Schritt, keine Schleifen.
- **Kein API-Key:** `call_tools` muss dann deterministisch auf `answer_question` (→ `_rule_based_response`) zeigen, damit der Chat ohne Key weiter funktioniert.
- **Argument-Extraktion** durch das LLM (z. B. Tag/Uhrzeit) ist in v1 bewusst **nicht** nötig (Handler parsen selbst) — später optionale Verfeinerung.

### 7. Testbarkeit
- Repräsentative Sätze gegen den Graphen: „verschiebe das Abendessen auf 20 Uhr", „lösche Tag 2 das Museum", „gib mir eine Alternative für Tag 1", „fülle den Plan auf", „nimm Vorschlag 2", „schreibe alles in den Kalender", „wie ist das Wetter?". → Jeweils landet der richtige Handler, Plan/Antwort wie zuvor.
- Terminal-Trace zeigt `[Orchestrator] → replace_activity` etc.
- Ohne API-Key: Chat antwortet regelbasiert (kein Crash).

### Offene Fragen
- **Intent-Routing vs. volle Argument-Extraktion:** v1 reicht Intent (Handler parsen weiter selbst). Soll der LLM später auch Tag/Uhrzeit/Kategorie strukturiert liefern (robuster, aber mehr Umbau)?
- **Verbleib der Regex-Helfer:** vorerst stehen lassen (manche Handler nutzen `_extract_*` intern) oder aktiv ausmisten?

---
---

# Phase 2 — Places-Fix + Planning-Agent + Zeit-/Routen-Agent + Qualitäts-Gates

### 1. Ziel
Der Plan wird vom **LLM kuratiert** (Auswahl/Reihenfolge) und **zeitlich vom LLM gelegt** (Uhrzeiten, Dauer, geschätzte Fahrtzeit), die quellenübergreifende **Dublette** („Notre-Dame doppelt") wird strukturell behoben — bei stabilen Signaturen.

### 2. Neue Dateien
- **`reiseagent/agents/time_route_agent.py`** — `schedule_times_and_routes(ordered_activities, day_start) -> slots`. LLM weist Start/Ende + `est_travel_to_next_min` zu. **Kein deterministischer Fallback** (Team-Entscheidung), nur 1× Repair.
- *(Planning-Kurator wird als Funktion `curate_plan(...)` in `llm.py` oder einem kleinen `agents/planning_llm.py` ergänzt — siehe IMPLEMENTIERUNGSPLAN_PHASE_B.md.)*

### 3. Geänderte Dateien
| Datei | Was genau ändert sich |
|---|---|
| `providers/places.py` (`_rank_and_deduplicate` Z.594, Key-Bildung Z.600–601) | **Semantische, quellenübergreifende Dedup:** zusätzlich zur exakten Namens-Normalisierung zwei Orte als gleich behandeln, wenn (a) Koordinaten sehr nah (< ~150 m) **oder** (b) Namen via `difflib.SequenceMatcher` ähnlich (≥ ~0.82) nach Entfernen von Füllwörtern (`cathedral, cathédrale, museum, the, de, la, of`). Stdlib `difflib` → keine neue Abhängigkeit. |
| `agents/planning.py` (`create_plan` Z.69) | **Innen** kapseln: zuerst LLM-Kurator (IDs/Tag) → Qualitäts-Gate → bei Ungültigkeit 1× Repair → sonst Fallback **bestehendes** `pick_activities_for_day`. Danach Zeitlegung via `time_route_agent`. **Signatur `create_plan(request, all_activities, weather)` bleibt.** Deterministische Zeit-Helfer (`_get_duration`, `_get_travel_minutes`, Slot-Loop Z.98–123) werden durch den Zeit-/Routen-Agenten ersetzt (als Fallback-Referenz behalten). |
| `prompts.py` | Neu (Englisch): `CURATE_PLAN` (Auswahl/Tag) und `SCHEDULE_DAY` (Zeiten/Fahrtzeit). |
| `agents/recommendation.py` | `pick_activities_for_day` (Z.105) **unverändert als Fallback**; `score_activity` (Z.29) bleibt (liefert `overall_score`, von Budget/Replanning/Streamlit genutzt). |

### 4. Schritt-für-Schritt-Ablauf
1. **Places-Dedup-Fix** in `_rank_and_deduplicate`: nach heutigem Exakt-Merge eine zweite Runde, die per Koordinaten-Nähe/Namens-Ähnlichkeit zusammenführt und den Eintrag mit höherem `quality_score` behält. (Direkt testbar an Paris: Notre-Dame erscheint nur 1×.)
2. **`CURATE_PLAN`-Prompt + `curate_plan(request, candidates, weather)`**: gibt `{day_number: [activity_id,...]}`. Eingabe: kompakte Kandidatenliste (id, name, category, indoor/outdoor, cost).
3. **Qualitäts-Gate Planning:** JSON valide? IDs ∈ Kandidaten? **keine Dublette im ganzen Plan**? ≥ `MIN_ACTIVITIES_PER_DAY` (=4, vorhandene Konstante)? → bei Verstoß **1× Repair-Prompt** (mit Fehlerbeschreibung), sonst **Fallback** auf `pick_activities_for_day` je Tag.
4. **Aktivitäts-Objekte zusammenbauen:** je gewählter ID das volle Activity-Dict; `estimated_cost_total` + `score` setzen (wie heute in `pick_activities_for_day` Z.119–123), damit Budget/Streamlit-Felder vollständig bleiben.
5. **`time_route_agent.schedule_times_and_routes`**: geordnete Aktivitäten + Koordinaten → LLM legt `start_time`, `end_time`, `est_travel_to_next_min` (Mahlzeiten an Mittag/Abend ankern, ≤ 23:59).
6. **Qualitäts-Gate Zeit/Route:** keine Überschneidungen, `end>start`, Fahrtzeit-Lücke vorhanden, ≤ 23:59 → bei Verstoß **1× Repair**, danach LLM-Ausgabe **übernehmen** (kein det. Fallback).
7. **Slots in bestehender Form schreiben** (`id, start_time, end_time, activity, notes, travel_to_next_minutes`) — exakt wie heute, damit Navigation/Kalender/Budget weiterlaufen.
8. **Finale Plan-Validierung** (Qualitäts-Gate über den ganzen Plan): erneut auf Dubletten prüfen (Name/Koordinaten), sonst Warn-Insight.

### 5. Integrationspunkte
- **Braucht Phase 0** (`llm.call`, Repair-Muster, Trace).
- Aufrufer von `create_plan`/`get_places` (coordinator, streamlit, main, monitoring, test_all) bleiben unverändert (Signaturen gehalten).
- Bereitet **Phase 3** vor: der `CURATE_PLAN`-Prompt bekommt später einen „User context"-Block (RAG).

### 6. Risiken & Fallstricke
- **Activity-Dict-Shape vollständig halten** — `estimated_cost_total`, `score`, `location.lat/lng`, `tags`, `source` müssen gesetzt sein, sonst brechen Budget (`estimated_cost_total`) und Navigation (`location`).
- **Kein Zeit-Fallback (bewusst):** ungültige LLM-Zeiten werden nach 1 Repair akzeptiert — das ist die gewollte ehrliche Experiment-Bedingung; Gate sollte wenigstens „über Mitternacht"/„Ende≤Start" hart abfangen, damit die UI nicht kaputtgeht.
- **Koordinaten fehlen** bei manchen Quellen (`lat/lng = None`, z. B. generische/chat-Aktivitäten) → Zeit-/Routen-Agent braucht Default-Fahrtzeit-Annahme; Dedup per Koordinate nur wenn beide Koordinaten vorhanden.
- **Dedup zu aggressiv** könnte echte Nachbarn (zwei Museen nah beieinander) zusammenlegen → Schwelle konservativ wählen + Namens-Ähnlichkeit zusätzlich verlangen.
- **Token-Budget** des Kurator-Prompts bei ~50 Kandidaten × mehreren Tagen beachten (kompakte Liste, nur Felder die zählen).

### 7. Testbarkeit
- Paris 3 Tage: Notre-Dame/Louvre erscheinen **je 1×** im ganzen Plan; jeder Tag ~4–5 Aktivitäten, Mittag/Abend mit Essen.
- Zeitplan: keine Überschneidungen, Fahrtzeit-Lücken plausibel, nichts nach 23:59.
- Repair-Pfad: künstlich ungültige LLM-Antwort erzwingen (z. B. unbekannte ID) → Repair greift, sonst Fallback `pick_activities_for_day`.
- Budget rechnet weiter korrekt (gleiche Summen-Logik).

### Entschiedene Fragen
- **Dedup-Schwellen:** ✅ 150 m Koordinaten-Radius + 0.82 Namens-Ähnlichkeit als Startwert.
- **Kurator-Eingabemenge:** ✅ Alle ~50 Kandidaten nach dem neuen Quality-Score-Vorfilter (laut IMPLEMENTIERUNGSPLAN_PHASE_B: `[:30]` → `[:50]` in `_rank_and_deduplicate`). Das LLM kuratiert daraus den Plan.

---
---

# Phase 3 — Memory / RAG (Telegram / Mail)

### 1. Ziel
Eingehende Telegram-/Mail-Nachrichten werden **gespeichert** (ein Dokument pro Nachricht) und per **Embeddings + Cosine-Top-k** semantisch durchsuchbar; der passende Kontext wird in die Planning-/Vorschlags-Prompts injiziert.

### 2. Neue Dateien
- **`reiseagent/memory.py`** — `store_message(source, date, text)`, `retrieve_context(query, k=4) -> list[str]`. Hält Embeddings + Cosine-Suche an einer Stelle.

### 3. Geänderte Dateien
| Datei | Was genau ändert sich |
|---|---|
| `profile_store.py` (`init_db` Z.12) | Neue Tabelle `messages(id, source, date, text, extracted_json, embedding)` — **ein Dokument pro Nachricht**. |
| `agents/profile_learner.py` (`run_profile_update` Z.69, `learn_from_*`) | Beim Verarbeiten jeder Nachricht zusätzlich `memory.store_message(...)` aufrufen. **Telegram/Mail werden hier (nicht in `telegram.py`/`gmail.py`) abgegriffen** → A3 bleibt unangetastet. |
| `prompts.py` / `agents/planning.py` (`CURATE_PLAN`) | Optionalen Block „User context (from messages): {context}" einfügen; gefüllt aus `retrieve_context(destination/Anfrage)`. |
| `agents/suggestion_agent.py` (`create_suggestion_for_day` Z.64) | `retrieve_context(...)` in den Vorschlags-Prompt einspeisen (Profil + relevante Nachrichten). |

### 4. Schritt-für-Schritt-Ablauf
1. **Embedding-Quelle wählen** (siehe offene Frage). Empfehlung: lokal `sentence-transformers` (`all-MiniLM-L6-v2`) — einfache API, kein zusätzlicher API-Key (Groq bietet keine Embeddings).
2. **`messages`-Tabelle** in `profile_store.init_db` ergänzen + kleine Insert-/Select-Funktionen.
3. **`memory.store_message`**: Text speichern, Embedding berechnen, als JSON/Blob ablegen (Duplikate via `source+date+text` vermeiden).
4. **`memory.retrieve_context(query, k)`**: Query-Embedding; Cosine gegen gespeicherte Vektoren (numpy); Top-k Texte zurück. (Transparent für die Demo — die Mathematik ist sichtbar.)
5. **`profile_learner`** ruft beim Lernen `store_message` (Telegram/Gmail/IMAP).
6. **Injektion:** `create_plan` und `suggestion_agent` holen `retrieve_context` und füllen den Kontextblock in den Prompt.
7. **Live-Trace:** `[Memory] 3 relevante Nachrichten gefunden` über `llm.log_step`.

### 5. Integrationspunkte
- **Braucht Phase 0** (Trace) und **Phase 2** (`CURATE_PLAN`-Prompt als Injektionsstelle).
- Datengrundlage entsteht beim bestehenden Profil-Update (`main.py /api/profile/update`, Z.373) — kein neuer Trigger nötig.

### 6. Risiken & Fallstricke
- **Neue, ggf. schwere Abhängigkeit** (`sentence-transformers`/`chromadb`) vs. Coding-Stil „einfach". Mitigation: SQLite-Blob + numpy-Cosine ist die schlankste Variante; Chroma nur, wenn das Team die Vektor-DB explizit als Lernziel zeigen will.
- **Erststart-Latenz** beim Laden des Embedding-Modells → einmalig, dokumentieren.
- **A3:** Nachrichten **nicht** in `telegram.py` abgreifen — nur im Aufrufer (`profile_learner`).
- **Datenschutz/Größe:** profile.db wächst; ggf. Limit/Älteste-löschen (einfach halten).
- **Leerer Kontext** darf den Prompt nicht verfälschen (Block weglassen, wenn nichts gefunden).

### 7. Testbarkeit
- Testnachricht „Wir wollen mit den Kindern nach Paris, eher Museen" speichern → `retrieve_context("Paris")` liefert sie als Top-Treffer.
- Plan für Paris zeigt im Trace, dass der Kontext im Prompt landete; Vorschläge werden „kinderfreundlicher".

### Offene Fragen
- **Embedding-Backend:** `sentence-transformers` + SQLite/numpy (schlank, transparent) **oder** `chromadb` (näher an „Vektor-DB" fürs Lehrziel)? Beides ist mit Groq kompatibel, da Embeddings lokal laufen.
- **Was wird injiziert** — nur Telegram/Mail oder auch gelernte `interests`/`past_events` als zweiter Block?

---
---

# Phase 4 — Proaktiv + Scheduler (Kalender-LLM → Vorschlagskarte im Chat)

### 1. Ziel
Einmal pro Woche (z. B. samstags) liest das System den Kalender, lässt das **LLM die freien Tage interpretieren** und zeigt einen proaktiven **Vorschlag als Karte im Chat** mit [Ja]/[Nein] (Human-in-the-Loop).

### 2. Neue Dateien
- **`reiseagent/agents/calendar_agent.py`** — `interpret_calendar(events) -> [{date, status: free/partly/busy, reason}]` (LLM). Feiertage = frei, „Arbeit 8–16" = teilbelegt, Gym/Arzt = weitgehend frei, Urlaub/Brückentage erkennen.
- **`reiseagent/scheduler.py`** *(oder Thread in `main.py`)* — wöchentlicher Trigger (Samstag) → `interpret_calendar` → `suggestion_agent` → Vorschlag persistieren.

### 3. Geänderte Dateien
| Datei | Was genau ändert sich |
|---|---|
| `providers/calendar.py` (`find_free_days` Z.80, Marker-Logik Z.85) | Roh-Events (`get_calendar_events` Z.54) liefern künftig **Summary/Beschreibung** an den `calendar_agent`; die marker-only-Heuristik wird durch LLM-Interpretation ersetzt (deterministische Wochenend-/Datumsmathematik bleibt als Stütze). |
| `agents/free_time_detector.py` (`detect_and_save_free_days` Z.4) | Statt nur `find_free_days` → `calendar_agent.interpret_calendar`; nur `status=free` (und ggf. `partly`) als freie Tage speichern (`profile_store.replace_free_days`). |
| `main.py` (Threads ab Z.90) | Vierter Hintergrund-Thread **wöchentlich** (Samstag, „last-run"-Datums-Guard) → ruft Detektion + Vorschlagserzeugung. |
| `prompts.py` | Neu (Englisch): `INTERPRET_CALENDAR`. |
| `streamlit_app.py` | Pending-Vorschläge als **Karte im Chat** rendern: „Du hattest am Wochenende Lust auf Paris — soll ich planen? [Ja]/[Nein]". [Ja] → `handle_plan_request`/Plan erstellen. |

### 4. Schritt-für-Schritt-Ablauf
1. **`INTERPRET_CALENDAR`-Prompt + `calendar_agent.interpret_calendar`** (Eingabe: Events der nächsten Wochen; Ausgabe: pro Tag `free/partly/busy` + Begründung).
2. **Qualitäts-Gate:** Feiertage als frei gewertet, plausible Einstufung, Begründung vorhanden → 1× Repair, sonst deterministische `find_free_days`-Mathematik als Rückfall.
3. **`free_time_detector`** auf `interpret_calendar` umstellen; freie Tage speichern.
4. **Scheduler-Thread**: einmal/Woche samstags (Guard gegen Mehrfachlauf am selben Tag) → Detektion → `suggestion_agent.create_suggestions_for_upcoming_free_days`.
5. **Vorschlagskarte im Chat** (Streamlit): `profile_store.get_pending_suggestions()` anzeigen; [Ja] erstellt einen Plan (Human-in-the-Loop), [Nein] → `update_suggestion_status('rejected')` (+ optional Ersatz wie heute).
6. **Profil-Trennung umsetzen** (Entscheidung 2026-06-27): Auto-Vorschläge mergen Profil-Interessen; **manuelle** Reisen **nicht** (siehe Phase-übergreifende Notiz unten).
7. **Trace/Live-Terminal:** `[Kalender] Sa–So frei (Montag Feiertag)` etc.

### 5. Integrationspunkte
- **Braucht Phase 0** (LLM/Trace) und profitiert von **Phase 3** (RAG-Kontext im Vorschlag).
- Nutzt vorhandene Bausteine: `suggestion_agent`, `profile_store.free_days/suggestions`, bestehende Accept/Reject-Endpunkte (`main.py` Z.405/426).

### 6. Risiken & Fallstricke
- **Frequenz/Workflow noch offen** (UMBAU §10.6) — bewusst einfach halten: ein Thread + Wochentag-Guard statt komplexer Scheduler-Lib.
- **Kalender-Zugriff** braucht Google-Credentials; ohne → `get_calendar_events` liefert `[]`, Pfad muss leer-tolerant sein.
- **Profil-Trennung** ist ein echter Verhaltenswechsel an `coordinator.handle_plan_request` (Merge Z.37–47) → nur für Auto-Trips mergen; manueller Pfad darf Profil **nicht** ziehen. Sorgfältig, da `handle_plan_request`-Signatur bleibt (Unterscheidung z. B. über ein `request`-Flag `auto=True`).
- **Doppelte Vorschläge** vermeiden (Status-Handling wie heute: `update_pending_suggestions_status`).

### 7. Testbarkeit
- Mock-Events (Feiertag + „Arbeit 8–16" + „Gym") → `interpret_calendar` stuft korrekt ein.
- Scheduler-Funktion **manuell** auslösen (nicht auf Samstag warten) → Vorschlag erscheint als Chat-Karte; [Ja] erzeugt Plan, [Nein] verwirft.
- Manuelle Reise zieht **keine** Profil-Interessen mehr; Auto-Vorschlag schon.

### Offene Fragen
- **Scheduler-Mechanik:** eigener Thread mit Wochentag-Guard (schlank) **oder** APScheduler (mehr Komfort, neue Abhängigkeit)? Und exakter Lauf-Zeitpunkt (Samstag früh?).
- **`partly`-Tage:** als planbar behandeln (mit Hinweis) oder nur volle `free`-Tage vorschlagen?
- **Profil-Trennung-Flag:** Wie wird „manuell vs. auto" technisch markiert (z. B. `request["auto"]`)? — bitte festlegen, da es `handle_plan_request` berührt.

---
---

# Phase 5 — Flug-als-Entscheidung, Finanz, Feedback

### 1. Ziel
Der **Flug-Check wird zur Agenten-Entscheidung** (LLM ruft das Tool, statt `if flight_number`), plus optionale Erweiterungen: einfaches Finanzmodell, Feedback-Schleife, Tagesausflüge.

### 2. Neue Dateien
- *(Keine zwingend.)* Optional **`reiseagent/agents/finance.py`** (deterministisches Sparszenario) und/oder **`reiseagent/feedback.py`** (gelernte Zu-/Abneigungen).

### 3. Geänderte Dateien
| Datei | Was genau ändert sich |
|---|---|
| `graph.py` / `prompts.py` (aus Phase 1) | Neue Orchestrator-Tools `check_flight` / `search_flight`. Der LLM entscheidet, ob ein Flug-Call sinnvoll ist (z. B. nur Starthafen genannt → Flug suchen). |
| `agents/coordinator.py` (`handle_plan_request` Flug-Block Z.74–96) | Der harte Trigger `if request.get("flight_number")` wird zur **Tool-Entscheidung**; `providers/flights.py` bleibt unverändert (nur der Auslöser wandert). |
| `agents/monitoring.py` (`_refresh_flights` Z.223, Trigger Z.226) | Bleibt für Hintergrund-Überwachung; ggf. LLM-Bewertung der Relevanz ergänzen. **Schwellen/Intervalle (`required_interval_seconds` Z.341) unverändert lassen.** |
| `prompts.py` | Englische Templates für Flug-Entscheidung; optional Finanz/Feedback. |

### 4. Schritt-für-Schritt-Ablauf
1. **Flug-Tools** in den Orchestrator (Phase 1) aufnehmen: `check_flight(flight_number)`, `search_flight(origin, date, …)` → rufen `providers.flights.get_flight_status_for_trip`.
2. **Trigger verlagern:** in `handle_plan_request` den `if flight_number`-Zweig durch die Tool-Entscheidung ersetzen; bestehende `_adjust_first_day_for_flight`-Logik (Z.175) als Tool-Folge behalten.
3. **(Optional) Finanzmodell** `finance.py` (deterministisch — Budget rechnet exakt): einfache Spar-/Tagesbudget-Szenarien; nur wenn vom Team gewünscht.
4. **(Optional) Feedback-Schleife:** „das kenne ich schon" → in `profile_store` als Abneigung, fließt in Auswahl/Vorschlag ein.
5. **(Optional) Tagesausflüge** als spezieller 1-Tages-Plan über den bestehenden Pfad.

### 5. Integrationspunkte
- **Braucht Phase 1** (Orchestrator/Tool-Calling) und profitiert von Phase 2 (Plan-Bau).
- `providers/flights.py` und die FastAPI-Flug-Endpunkte bleiben unverändert.

### 6. Risiken & Fallstricke
- **Höheres Risiko / am wenigsten spezifiziert** — bewusst zuletzt. Klein anfangen: nur die Flug-Entscheidung, Rest optional.
- **Monitoring nicht stören:** Hintergrund-Flug-/Wetter-Überwachung (Threads in `main.py`) und Telegram-Proposal-Flow (A3) unverändert lassen.
- **Doppelte Flug-Calls** (Orchestrator + Monitoring) vermeiden — klare Zuständigkeit: Orchestrator bei Planung, Monitoring im Hintergrund.
- **Kosten/Quota** der Flug-API (Aviationstack) beachten, wenn der LLM häufiger triggert.

### 7. Testbarkeit
- „Ich fliege morgen mit LH123" → Orchestrator ruft `check_flight`, Tag 1 wird an Ankunft angepasst (wie heute, nur LLM-getriggert).
- „Ich starte in BER, plane mir was in Rom" (ohne Flugnummer) → `search_flight` greift (falls implementiert) oder sauberer Hinweis.
- Monitoring-Verhalten bei Verspätung unverändert (Telegram-Proposal wie gehabt).

### Offene Fragen
- ~~**Scope Phase 5:** nur Flug-als-Entscheidung umsetzen, oder Finanz/Feedback/Tagesausflüge mitnehmen?~~
- ~~**Finanzmodell:** überhaupt bauen? Falls ja — welche konkreten Szenarien?~~

**Update 2026-07-03:** Diese beiden Fragen sind nach Professor-Review + Team-Brainstorming beantwortet. Voller Scope wird umgesetzt (Flug-Entscheidung, dynamisches Finanzmodell inkl. simuliertem Bankkonto, Feedback-Agent) — zusätzlich wird auch der Orts-Vorfilter/Quality-Score (Phase 2) komplett durch LLM-Tool-Calling ersetzt. Details, Begründungen und die Aufteilung auf 4 Teammitglieder stehen in `BRAINSTORMING_PHASE5_2026-07-03.md` und `PHASE5_TEAM_PLAN_2026-07-03.md`. Diese Dateien haben Vorrang vor den obigen (jetzt überholten) Annahmen.

---
---

## Phasenübergreifende Notiz: Profil-Trennung manuell/Auto
Die Entscheidung 2026-06-27 (manuelle Reisen übernehmen Profil-Interessen **nicht** automatisch) berührt `coordinator.handle_plan_request` (Merge Z.37–47). Sie ist **klein und additiv** und kann unabhängig (idealerweise mit Phase 4) umgesetzt werden, indem der Merge nur bei Auto-Vorschlägen greift (z. B. `request.get("auto")`). Signatur bleibt unverändert.
