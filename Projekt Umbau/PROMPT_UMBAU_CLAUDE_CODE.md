# Prompt für Claude Code (Opus 4.8) — Umbau-Analyse & Vorschlag

> **Verwendung:** Den Inhalt zwischen den `===`-Linien als einen einzigen Prompt an Claude Code geben.
> **Ergebnis dieses Prompts:** KEINE Implementierung, sondern ein **schriftlicher, detaillierter Umbau-Vorschlag**
> (Markdown-Dokument), nachdem Claude Code den gesamten Code tief analysiert hat.
>
> Grundlage: Review-Session mit dem Professor (HTW Berlin, GenAI-Modul) am 2026-06-23.

---

============================ PROMPT START ============================

## Rolle

Du bist ein **Senior-Softwarearchitekt für agentische KI-Systeme**. Du wirst gleich ein bestehendes
Studienprojekt (Multi-Agenten-Reiseplanungssystem) analysieren. Deine Aufgabe in diesem Durchlauf ist
**NICHT zu implementieren**, sondern den vorhandenen Code **vollständig und im Detail zu analysieren**
und daraus einen **konkreten, umsetzbaren Umbau-Vorschlag** zu erstellen, der das Projekt von einem
überwiegend **regelbasierten** System zu einem echten **agentengetriebenen KI-System** weiterentwickelt.

Am Ende dieses Durchlaufs erwarte ich ein gut strukturiertes Markdown-Dokument
(`UMBAU_VORSCHLAG.md`) — kein Code. Frage nach, bevor du irgendetwas implementierst.

## Projektkontext

- **Modul:** „Unternehmenssoftware / GenAI", HTW Berlin. Ziel des Kurses: praktische Erfahrung mit der
  **Entwicklung von KI-/Agenten-Systemen** sammeln (nicht: ein rein regelbasiertes System bauen).
- **Projekt:** Multi-Agenten-Reiseplanungssystem. Ein Nutzer plant Reisen; mehrere Agenten
  (Coordinator, Recommendation, Planning, Budget, Checklist, Replanning, Monitoring, Daily-Brief,
  Suggestion …) erzeugen Tagespläne inkl. Wetter, Flügen, Fahrtzeiten, Budget.
- **Stack:** Python · Streamlit (Frontend) · FastAPI (Backend) · SQLite (`trips.db`, `profile.db`) ·
  **Groq LLM** (`llama-3.3-70b-versatile`) · OpenTripMap (POIs) · OpenRouteService (Fahrtzeiten) ·
  Aviationstack (Flüge) · zusätzlich Telegram-, Gmail/IMAP- und Google-Calendar-Anbindung.
- **Aktueller Stand:** Vieles ist **regelbasiert** (Workflow fest verdrahtet im `coordinator.py`, viele
  `if/else`-Entscheidungen, Regex-basierter Chat). LLM wird bisher nur punktuell genutzt.
- **Note bisher:** 1,7. Der Professor möchte einen klaren Schritt Richtung „echtes Agentensystem".

## Was der Professor in der Review-Session verlangt hat (die Anforderungen)

Arbeite den Umbau-Vorschlag so aus, dass er **alle** folgenden Punkte adressiert:

1. **Klarer Mehrwert ggü. ChatGPT.** Es muss erkennbar werden, dass im Hintergrund **Agenten
   orchestrieren** und **mehr leisten**, als wenn man einfach Präferenzen in ChatGPT eintippt und einen
   Tagesplan bekommt. Der Unterschied muss im System und in der Demo deutlich sein.

2. **Paradigmenwechsel: Agenten entscheiden selbst.** Weg vom fest definierten Workflow (Regeln, if/else,
   feste Reihenfolge) — hin zu Agenten, die **als Funktionen/Fähigkeiten mit eigenen Tools und
   System-Prompts** beschrieben sind und **selbst entscheiden**, wann was ausgeführt wird und welche Daten
   an welchen weiteren Agenten gehen. Der Orchestrierungs-Agent routet anhand von Kontext, nicht anhand
   harter Regeln. (Es ist ausdrücklich ok, wenn das anfangs weniger gut funktioniert als die Regel-Variante.)

3. **Qualitätssicherung pro Agent.** Zentrales Thema. Für **jeden (Sub-)Agenten** muss klar sein: welcher
   **System-Prompt**, welche **Tools**, und **wie der Agent die Qualität seines eigenen Outputs sicherstellt**
   (Validierung / Selbstprüfung / LLM-as-Judge / Schema-Checks). In der Demo waren fehlerhafte Daten zu
   sehen (z.B. **Notre-Dame doppelt** im Tagesplan) — solche Qualitätsfehler müssen durch Prüf-Mechanismen
   verhindert werden.

4. **Kontext-Integration als Alleinstellungsmerkmal.** Telegram, E-Mail (Gmail/IMAP), Google Calendar,
   **Budget/Kontostand** und sogar **familiäre Situation** (z.B. Kinder, Hund) sind genau das, was das
   System von ChatGPT abhebt. Der Vorschlag muss **konkret** machen:
   - Was genau wird aus Telegram/E-Mail/Kalender entnommen und wie fließt es in die Tagesplanung ein?
   - **Wie werden diese Daten gespeichert und durchsucht?** Vektordatenbank ja/nein? Ein Dokument pro
     Telegram-Nachricht oder alle zusammen? Wie wird eine Nutzeranfrage mit bisherigem Telegram-/Mail-Inhalt
     **gematcht** (Retrieval / RAG)? Diese Fragen sind aktuell offen und müssen architektonisch beantwortet werden.

5. **Rechnen ist nicht Kernkompetenz des LLM.** Für Kalkulationen (Uhrzeiten, Routen/Fahrtzeiten, Budget)
   gilt: LLMs rechnen schlecht. Erarbeite die **Schnittstelle**, an welchen Stellen das System
   - **deterministisch / regelbasiert** bleibt (z.B. exakte Zeit-/Routenberechnung über Tools), oder
   - das **LLM selbst ein kleines Code-Snippet generiert**, das die Kalkulation durchführt.
   Das LLM soll *entscheiden* und *kuratieren*, aber das **Rechnen an Tools oder generierten Code delegieren**.
   Genau diese Grenze (wo Regel, wo LLM, wo LLM-generierter Code) ist das Interessante und soll klar
   herausgearbeitet werden.

6. **Proaktive, konversationsgetriebene Interaktion (Ease of Use).** Neben dem bestehenden Formular soll es
   einen **Chat-/Agenten-Modus** geben, bei dem der Nutzer nur sagt: *„Ich hab Lust, mal wegzukommen."* —
   und der Agent **eigenständig loslegt**: nutzt bekannte Präferenzen, beobachtete Telegram-/Mail-Inhalte,
   Kalender-Freizeit, Budget/Kontostand, familiäre Situation, und **schlägt proaktiv** eine Reise / einen
   Tagesplan vor (z.B. Benachrichtigung: *„Du hattest am Wochenende Lust auf Paris — soll ich planen?"*,
   bestätigen mit einem Klick). Danach **iterative Verfeinerung wie im Reisebüro** (*„Das Restaurant kenne
   ich schon, gib mir ein anderes"*). Die Agenten entscheiden selbst, welche Tools (Flug-API, Booking etc.)
   sie dafür aufrufen.
   - **Wichtig:** Das bestehende **Formular „eigene Reise planen" bleibt erhalten** — beide Modi werden
     **kombiniert** (Formular für „schnell mal abchecken", Chat/Proaktiv für den agentischen Weg).

7. **Flug-Logik als Agenten-Entscheidung.** Aktuell wird die Flug-API rein regelbasiert getriggert (wenn
   eine Flugnummer im Feld steht). Ziel: Der Agent **entscheidet selbst**, dass eine Flug-API-Anfrage nötig
   ist (z.B. nur Starthafen wählen → Agent sucht passenden Flug, zieht Datum/Ankunft selbst).

8. **Beobachtbarkeit / Flowchart „unter der Motorhaube".** Für die nächste Präsentation muss man an einem
   **Beispiel-Nutzerprompt** nachvollziehen können: Orchestrierungs-Agent entscheidet → Agent X → ruft
   Tool A, dann Tool B → leitet an Agent Y weiter → usw. Und hinter **jeder Entscheidung** soll der
   zugrundeliegende **Prompt** sichtbar sein (simpler Prompt vs. **Prompt-Template mit gefüllten Variablen**).
   Der Umbau soll dies ermöglichen: zentrale, sichtbare Prompt-Templates + nachvollziehbares Tracing/Logging
   des Agenten- und Tool-Ablaufs.

## Zielvision (in einem Satz)

Ein **agentengetriebenes** Reise-System, das den Nutzer und seinen Kontext (Telegram, Mail, Kalender,
Budget, Familie) kennt, **proaktiv** Vorschläge macht, dessen Agenten **selbst** über Tool-Aufrufe und
Routing **entscheiden**, das seine **Ausgabequalität pro Agent absichert**, und das **Rechen-Aufgaben sauber
an deterministische Tools oder LLM-generierten Code delegiert** — klar unterscheidbar von einem reinen
ChatGPT-Chat.

## Deine Aufgabe — in zwei Phasen

### Phase 1 — Tiefenanalyse des bestehenden Codes (gründlich!)
Lies und verstehe den **gesamten** relevanten Code, bevor du etwas vorschlägst. Mindestens:
- `reiseagent/agents/` — **alle** Agenten (coordinator, recommendation, planning, budget, checklist,
  replanning, monitoring, daily_brief, free_time_detector, profile_learner, suggestion_agent, navigation).
- `reiseagent/providers/` — places, navigation, weather, flights, calendar, telegram, gmail, geocoding.
- `reiseagent/` — `streamlit_app.py`, `ui_service.py`, `main.py`, `store.py`, `models.py`, `profile_store.py`.
- Bestehende Konzept-Dokumente, die du berücksichtigen und mit deinem Vorschlag **abgleichen** musst:
  `ZIELARCHITEKTUR.md`, `SYSTEM_ARCHITECTURE.md`, `ARCHITEKTUR_PLANUNG_LLM.md`,
  `IMPLEMENTIERUNGSPLAN_PHASE_B.md`, `ZUKUNFT_NOTIZEN.md`, `CHANGELOG.md`.

Halte dabei fest:
- Welche Agenten sind heute **regelbasiert**, welche nutzen das LLM, und **wo genau** sitzt die
  Entscheidungslogik (insb. im `coordinator.py`)?
- Wo entstehen heute **Qualitätsfehler** (z.B. Dubletten wie „Notre-Dame doppelt", falsche Daten)?
- Wie werden Telegram/Mail/Kalender heute genutzt und gespeichert?
- Wo wird gerechnet (Zeiten, Routen, Budget) und wie ist das an Tools gebunden?
- Welche öffentlichen Funktions-Signaturen werden breit aufgerufen und dürfen beim Umbau **nicht
  unbemerkt brechen** (Abhängigkeiten kartieren)?

### Phase 2 — Umbau-Vorschlag (`UMBAU_VORSCHLAG.md`)
Erstelle ein Dokument mit mindestens diesen Abschnitten:
1. **Ist-Analyse (kompakt):** aktuelle Architektur, was regelbasiert ist, wo Qualitätsfehler entstehen.
2. **Ziel-Architektur:** das agentengetriebene Zielbild. Empfiehl konkret einen Orchestrierungs-Ansatz
   (z.B. LLM-Tool-Calling / LangGraph / o.ä.) **mit Begründung** und Abgleich zur vorhandenen
   `ZIELARCHITEKTUR.md`. Zeige den Routing-Mechanismus (Agent entscheidet, nicht fester Workflow).
3. **Agenten-Katalog:** pro Agent eine Tabelle/Spezifikation mit *Verantwortung · Tools · Skizze des
   System-Prompts (ggf. als Template mit Variablen) · Qualitätssicherung des Outputs*.
4. **Kontext-/Memory-Schicht:** konkreter Vorschlag, wie Telegram/Mail/Kalender gespeichert und
   abgefragt werden (Vektordatenbank? RAG? Schema „ein Dokument pro Nachricht"?), und wie der Kontext in
   die Planung einfließt.
5. **Rechen-Schnittstelle:** klare Festlegung, wo deterministische Tools, wo LLM-generierter Code,
   wo Regeln — inkl. Begründung pro Fall (Zeiten, Routen, Budget, Flug).
6. **Interaktions-/UX-Umbau:** Chat-/Proaktiv-Modus + Beibehaltung des Formulars (kombiniert),
   iterative Verfeinerung „wie im Reisebüro", proaktive Vorschläge inkl. Bestätigungs-Flow.
7. **Beobachtbarkeit / Flowchart:** wie der Ablauf (Agent → Tools → Prompt → nächster Agent) für einen
   **Beispiel-Nutzerprompt** sichtbar/loggbar gemacht wird; liefere **ein durchgespieltes Beispiel** als Flowchart (Text/Mermaid).
8. **Migrationsplan (phasiert):** realistische Reihenfolge vom heutigen Code zum Ziel, mit
   **Abhängigkeiten, Risiken** und was **nicht brechen** darf. Markiere, was MVP-tauglich für die nächste
   Präsentation ist.
9. **Offene Fragen** an das Team / den Professor, die vor der Implementierung geklärt werden müssen.

## Randbedingungen (zwingend einhalten)
- **Coding-Stil (für spätere Implementierung):** *Write simple Python code that a beginner can easily
  understand. Use basic Python features, minimal exception handling, very little abstraction, no
  unnecessary classes, no over-engineering. Keep it short, readable, and easy to modify.* Empfiehl nichts,
  was diesen Stil grob verletzt; wenn ein komplexeres Framework nötig ist, begründe den Mehrwert.
- **Kategorie-Vokabular** durchgehend: `culture / food / nature / sightseeing / shopping`.
- **LLM-Prompts auf Englisch**, **Ortsnamen original** belassen. UI-Texte bleiben Deutsch.
- **Bestehende, funktionierende Features** (gespeicherte Reisen, Kalender-Sync, Flug-Anpassung,
  Tagesplan-Ansichten) müssen erhalten bleiben oder sauber migriert werden.
- **Pragmatismus erlaubt:** Für die Demo dürfen einzelne Bausteine bewusst regelbasiert bleiben — das ist
  laut Professor ok. Aber der **Kern muss agentisch** werden, und die Grenze ist zu begründen.
- Stack-Vorgabe beibehalten (Groq `llama-3.3-70b-versatile`), sofern du keinen begründeten Wechsel
  empfiehlst.

## Wichtig
- **Implementiere noch nichts.** Liefere nur die Analyse + den Vorschlag als `UMBAU_VORSCHLAG.md`.
- Triff **Annahmen explizit** und liste Unklarheiten als offene Fragen, statt zu raten.
- Sei **konkret** (Dateinamen, Funktionsnamen, Datei:Zeile), nicht generisch.

============================ PROMPT ENDE =============================
