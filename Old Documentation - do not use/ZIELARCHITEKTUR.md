# Zielarchitektur & Entwicklungsplan — Reiseplanungs-Agent

> **Zweck dieses Dokuments:** Dieses Dokument beschreibt den **Ziel-Zustand** des Systems und den Weg dorthin.
> Es baut auf zwei Grundlagen auf:
> 1. der **bestehenden Code-Architektur** (was bereits implementiert ist), und
> 2. der **Vision** aus [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) (die bereinigten Notizen).
>
> Es dient als gemeinsame Vorstellung davon, *wie der Agent funktionieren soll, was er enthalten soll und in welcher Reihenfolge wir ihn umbauen.* Es ist die Basis für alle späteren Implementierungs-Prompts.

---

## 1. Leitprinzipien

Diese fünf Prinzipien gelten für jede Designentscheidung im Projekt:

1. **Proaktiv statt reaktiv** — Der Agent wartet nicht nur auf Eingaben, sondern beobachtet (Kalender, Wetter, Flüge, Nachrichten) und schlägt von sich aus vor.
2. **LLM-gestützt statt regelbasiert** — Entscheidungen, die Kontext, Sprache oder Geschmack betreffen, übernimmt ein LLM. Reines Rechnen bleibt deterministischer Code.
3. **Persistent statt flüchtig** — Alles, was ein Agent über die Zeit überwachen oder erinnern muss (Trips, Profil, Budget), liegt in einer Datenbank.
4. **Human-in-the-Loop** — Der Agent schlägt vor; der Nutzer entscheidet. Vorschläge haben immer einen Status (pending → accepted/rejected).
5. **Tool-Calling als Kern** — Agenten rufen externe Welt (APIs, DB) über klar definierte Tools auf, die das LLM selbst auswählen kann.

---

## 2. Ist-Zustand → Ziel-Zustand: Agenten-Mapping

Übersicht, was mit jedem bestehenden Baustein passiert:

| Baustein (heute) | Typ heute | Entscheidung | Ziel-Zustand |
|---|---|---|---|
| `agents/coordinator.py` | Python-Orchestrierung | **Umbauen** | Wird zum LangGraph-Graphen (Orchestrierung als expliziter State-Graph) |
| `agents/planning.py` | regelbasiert | **Löschen → ablösen** | Ersetzt durch LLM-**Planning-Agent** |
| `agents/recommendation.py` | regelbasiert (Scoring) | **Löschen → ablösen** | Geht im LLM-Planning-Agent auf (semantisches Matching statt Score-Gewichte) |
| `agents/checklist.py` | regelbasiert (If/Else) | **Löschen → ablösen** | Ersetzt durch LLM-**Checklist-Agent** |
| `agents/budget.py` | deterministisch (rechnen) | **Behalten + erweitern** | Bleibt deterministisch, wird mit Finanzmodell verbunden |
| `agents/replanning.py` | regelbasiert | **Umbauen** | Kernlogik bleibt, Auswahl der Alternativen wird LLM-gestützt |
| `agents/profile_learner.py` | Keyword/Regex | **Behalten + erweitern** | Bleibt; zusätzlich LLM-Extraktion + Feedback-Aufnahme |
| `agents/free_time_detector.py` | regelbasiert | **Behalten** | Bleibt (Kalenderlogik ist deterministisch sinnvoll) |
| `agents/suggestion_agent.py` | LLM (Groq) | **Behalten + erweitern** | Bleibt; bekommt Budget-Bewusstsein dazu |
| `agents/daily_brief.py` | LLM (Groq) | **Behalten** | Bleibt |
| `agents/navigation.py` | LLM (Groq) | **Behalten** | Bleibt |
| `store.py` | In-Memory | **Ersetzen** | Persistente Trip-Speicherung in DB |
| `profile_store.py` | SQLite | **Behalten + erweitern** | Neue Tabellen (users, finances, ratings) |
| `providers/*` | API-Anbindungen | **Behalten** | Bleiben; neu dazu: `providers/flights.py` |

**Neue Komponenten:**
- `llm.py` — zentraler LLM-Zugriff (eine Stelle, austauschbar)
- `graph.py` — LangGraph-Orchestrierung (State + Knoten + Kanten)
- `agents/monitoring.py` — Hintergrund-Überwachung (Wetter + Flüge)
- `agents/finance.py` — Finanzmodell, Budget-Prognose, Sparszenarien
- `providers/flights.py` — Flugstatus-API
- `scheduler.py` — zeitgesteuerte Automatisierung (täglich/stündlich)

---

## 3. Ziel-Architektur im Überblick

```
                          ┌─────────────────────────────────────────┐
   TRIGGER                │              LANGGRAPH-GRAPH              │
 ┌──────────┐             │         (zentrale Orchestrierung)        │
 │ Nutzer-  │────────────►│                                          │
 │ anfrage  │             │   ┌────────────┐    ┌───────────────┐    │
 └──────────┘             │   │  Planning  │───►│   Checklist   │    │
                          │   │   Agent    │    │     Agent     │    │
 ┌──────────┐             │   │   (LLM)    │    │     (LLM)     │    │
 │ Kalender │             │   └─────┬──────┘    └───────┬───────┘    │
 │ -Trigger │────────────►│         │                   │            │
 └──────────┘             │   ┌─────▼──────┐    ┌───────▼───────┐    │
                          │   │   Budget   │    │   Suggestion  │    │
 ┌──────────┐             │   │   Agent    │    │     Agent     │    │
 │Scheduler │             │   │(determin.) │    │     (LLM)     │    │
 │(zeitlich)│────────────►│   └────────────┘    └───────────────┘    │
 └──────────┘             │   ┌────────────┐    ┌───────────────┐    │
                          │   │ Monitoring │───►│   Replanning  │    │
                          │   │   Agent    │    │     Agent     │    │
                          │   └────────────┘    └───────────────┘    │
                          │                                          │
                          │   Shared State (TripState) fließt durch  │
                          └──────────────┬───────────────────────────┘
                                         │
          ┌──────────────────────────────┼──────────────────────────────┐
          ▼                               ▼                              ▼
   ┌─────────────┐                ┌──────────────┐               ┌──────────────┐
   │  TOOLS /    │                │  DATENBANK   │               │  HUMAN-IN-   │
   │  PROVIDER   │                │              │               │  THE-LOOP    │
   ├─────────────┤                ├──────────────┤               ├──────────────┤
   │ Wetter      │                │ profile.db   │               │ Vorschläge   │
   │ POI/Places  │                │  - users     │               │ akzeptieren/ │
   │ Flüge       │                │  - interests │               │ ablehnen     │
   │ Navigation  │                │  - finances  │               │              │
   │ Telegram    │                │  - free_days │               │ (UI / Chat / │
   │ Gmail       │                │  - trips     │               │  Telegram)   │
   │ Kalender    │                │  - ...       │               │              │
   └─────────────┘                └──────────────┘               └──────────────┘
```

---

## 4. Die Agenten im Ziel-Zustand

Für jeden Agenten: **Aufgabe · Eingaben (woher) · Verarbeitung · Ausgabe (wohin) · LLM?**

### 4.1 Planning-Agent *(neu, ersetzt planning + recommendation)*
- **Aufgabe:** Erstellt aus Anfrage + Profil + Wetter + verfügbaren POIs einen kohärenten Tagesplan.
- **Eingaben:** Nutzeranfrage, Nutzerprofil (DB), Wetter (Provider), POIs (Provider), verfügbares Budget (Finanz-Agent).
- **Verarbeitung:** LLM wählt und ordnet Aktivitäten nach Interessen, Wetter (indoor/outdoor), Budget und Reisekontext. Kann Tools aufrufen (POI-Suche, Wetter).
- **Ausgabe:** Strukturierter Plan (Tage, Zeitslots, Aktivitäten) → TripState → DB.
- **LLM:** Ja.

### 4.2 Checklist-Agent *(neu, ersetzt checklist)*
- **Aufgabe:** Personalisierte Pack-/Vorbereitungsliste.
- **Eingaben:** Reiseplan, Wetter, Reiseart, Profil.
- **Verarbeitung:** LLM generiert kontextbezogene Items (statt fester If/Else-Listen).
- **Ausgabe:** Checkliste → DB.
- **LLM:** Ja.

### 4.3 Budget-Agent *(behalten + erweitern)*
- **Aufgabe:** Kosten eines Plans berechnen + gegen verfügbares Reisebudget prüfen.
- **Eingaben:** Plan-Aktivitäten, Finanzmodell (verfügbares Reisebudget).
- **Verarbeitung:** Deterministische Summierung, Kategorisierung, Status (im/nahe/über Budget).
- **Ausgabe:** Budget-Zusammenfassung → TripState.
- **LLM:** Nein (bewusst — Rechnen braucht kein LLM).

### 4.4 Finanz-Agent *(neu)*
- **Aufgabe:** Verwaltet das virtuelle Finanzmodell, berechnet verfügbares Reisebudget, prognostiziert zukünftige Budgets, simuliert Sparszenarien.
- **Eingaben:** Manuelle Monatseingabe des Nutzers (Gehalt, Fixkosten, gewünschtes Freizeitbudget), Budget-Historie (DB).
- **Verarbeitung:** Deterministische Berechnung + LLM für die Formulierung von Sparvorschlägen ("Wenn du 3 Monate je 300 € sparst …").
- **Ausgabe:** Verfügbares Budget, Prognosen → DB; Sparvorschläge → Vorschlags-Agent.
- **LLM:** Teilweise (Rechnen deterministisch, Vorschlagstext per LLM).

### 4.5 Monitoring-Agent *(neu)*
- **Aufgabe:** Überwacht laufend Wetter und Flugstatus für aktive/geplante Trips.
- **Eingaben:** Aktive Trips (DB), Wetter-API, Flug-API.
- **Verarbeitung:** Erkennt kritische Änderungen (Starkregen bei Outdoor-Plan, Flugausfall/-verspätung) und ihre Folgeeffekte (z. B. Reservierung nicht mehr erreichbar). Stößt bei Bedarf den Replanning-Agent an.
- **Ausgabe:** Warnungen + Auslöser für Umplanung → Human-in-the-Loop.
- **LLM:** Ja (Bewertung der Lage + Formulierung der Warnung).
- **Ausgelöst durch:** Scheduler (zeitlich).

### 4.6 Replanning-Agent *(umbauen)*
- **Aufgabe:** Erstellt bei Stör-Events (Wetter, Flug) einen angepassten Planvorschlag.
- **Eingaben:** Aktiver Plan, Stör-Event, verfügbare Alternativen (POIs), Profil.
- **Verarbeitung:** Kernlogik bleibt (betroffene Aktivitäten identifizieren), aber die Auswahl der Alternativen wird LLM-gestützt (statt reinem Score-Ranking).
- **Ausgabe:** Proposal mit Vorher/Nachher → Human-in-the-Loop.
- **LLM:** Ja (für Alternativenauswahl).

### 4.7 Profil-Lern-Agent *(behalten + erweitern)*
- **Aufgabe:** Lernt Vorlieben aus Nachrichten und Reise-Feedback.
- **Eingaben:** Telegram, Gmail, Reise-Feedback ("Wie hat dir X gefallen?").
- **Verarbeitung:** Heute Keyword/Regex; zusätzlich LLM-Extraktion für robusteres Verständnis + Aufnahme von Bewertungen.
- **Ausgabe:** Interessen + bewertete Events → DB.
- **LLM:** Ja (neu hinzu).

### 4.8 Freizeit-Erkenner *(behalten)*
- **Aufgabe:** Erkennt freie Tage im Kalender.
- **Eingaben:** Google Calendar.
- **Verarbeitung:** Deterministisch (Tag belegt bei Ganztagstermin oder ≥2 Terminen).
- **Ausgabe:** Freie Tage → DB.
- **LLM:** Nein.

### 4.9 Vorschlags-Agent *(behalten + erweitern)*
- **Aufgabe:** Generiert proaktive, personalisierte Vorschläge für freie Tage.
- **Eingaben:** Profil, freie Tage, POIs, **neu:** verfügbares Budget (Finanz-Agent).
- **Verarbeitung:** LLM kombiniert alles zu konkreten Vorschlägen (jetzt auch budgetbewusst).
- **Ausgabe:** Vorschläge (pending) → DB → Human-in-the-Loop.
- **LLM:** Ja.

### 4.10 Tagesbrief- & Navigations-Agent *(behalten, unverändert)*
- Bereits LLM-gestützt und funktionsfähig. Werden in den Graphen eingehängt, aber inhaltlich nicht umgebaut.

---

## 5. LangGraph-Orchestrierung

**Warum:** Mit wachsender Agentenzahl und bedingten Abläufen (Flug verspätet → dann X) wird Plain-Python-Orchestrierung unwartbar. LangGraph macht den Workflow zu einem expliziten Graphen mit strukturiertem State.

**Zentraler State (`TripState`):** Ein typisiertes Objekt, das durch alle Knoten fließt und u. a. enthält: Anfrage, Profil, Wetter, POIs, aktueller Plan, Budget, Vorschläge, Insights, offene Proposals.

**Knoten = Agenten.** **Kanten = Übergänge**, teils bedingt (z. B. „nur wenn Monitoring ein kritisches Event meldet → Replanning").

**Mehrere Einstiegspunkte (Graph-Entries):**
- *Reise planen:* Planning → Budget → Checklist
- *Proaktiv vorschlagen:* FreieTage → Finanz → Vorschlag
- *Überwachen:* Monitoring → (bedingt) Replanning

---

## 6. Datenhaltung

### profile.db (erweitert)

| Tabelle | Status | Inhalt |
|---|---|---|
| `users` | **neu** | Basisprofil (ID, Name, Alter, Heimatstadt) |
| `interests` | vorhanden | Vorlieben mit Score + Quelle |
| `past_events` | **erweitern** | + Bewertung (Feedback-Score) pro Event |
| `free_days` | vorhanden | Erkannte freie Tage |
| `suggestions` | vorhanden | Vorschläge mit Status |
| `finances` | **neu** | Monatliche Einnahmen, Fixkosten, Freizeitbudget |
| `budget_history` | **neu** | Budget pro Monat (für Prognosen/Sparszenarien) |
| `trips` | **neu** | Persistente Reisepläne (ersetzt In-Memory `store.py`) |

**Finanzmodell-Eingabe:** Der Nutzer pflegt am 1. des Monats manuell: Gehalt, erwartete Fixkosten bis zum nächsten Lohn, gewünschtes Freizeitbudget. Daraus wird das verfügbare Reisebudget berechnet.

---

## 7. Externe Konnektoren

| Konnektor | Status | Zweck |
|---|---|---|
| Open-Meteo (Wetter) | vorhanden | Planung + Monitoring |
| OpenTripMap (POI) | vorhanden | Aktivitäten/Restaurants finden |
| Nominatim (Geocoding) | vorhanden | Koordinaten |
| OpenRouteService (Navigation) | vorhanden | Routen/Gehzeiten |
| Telegram | vorhanden | Interessen lernen, Feedback |
| Gmail | vorhanden | Buchungen, Hinweise, Interessen |
| Google Calendar | vorhanden | Freie Slots |
| **Flug-API** | **neu** | Flugstatus/Verspätung/Ausfall (Monitoring) |

---

## 8. Trigger & Automatisierung

Drei Wege, das System zu aktivieren:

1. **Manuell** — Nutzer stellt eine Reiseanfrage (bestehend).
2. **Kalender-Trigger** — Freizeit-Erkenner findet freie Tage → Vorschlags-Agent.
3. **Scheduler (neu, `scheduler.py`)** — zeitgesteuerte Hintergrundläufe:
   - *Stündlich/regelmäßig:* Monitoring-Agent (Wetter + Flüge für aktive Trips).
   - *Täglich morgens:* Tagesbrief-Agent.
   - *Täglich/wöchentlich:* Profil-Update (Telegram/Gmail) + Vorschlagsgenerierung.

   Damit wird die Folien-Anforderung „automate/perform regular tasks on a daily/hourly basis" erfüllt.

---

## 9. LLM-Strategie

- **Aktuell:** Groq (`llama-3.3-70b-versatile`) — kostenlos, schnell, unterstützt Tool-Calling. Adressiert direkt die Folien-Challenge „Pay per use for cloud models".
- **Zentralisierung:** Aller LLM-Zugriff läuft über ein einziges Modul `llm.py`. Dadurch ist das Modell an **einer** Stelle austauschbar (z. B. Wechsel zu Claude API, falls Qualität es erfordert), ohne jeden Agenten anzufassen.
- **Tool-Calling:** Agenten definieren ihre Tools (POI-Suche, Wetter, DB-Zugriff) und lassen das LLM selbst entscheiden, wann es sie aufruft — der Schritt von „fest verdrahtet" zu „echt agentisch".

---

## 10. Entwicklungsplan (phasiert)

Reihenfolge nach Abhängigkeiten — jede Phase ist lauffähig abschließbar.

### Phase 0 — Fundament (keine Verhaltensänderung)
- `llm.py` als zentralen LLM-Zugriff anlegen, bestehende Groq-Aufrufe darauf umstellen.
- Persistente Trip-Speicherung (`trips`-Tabelle) statt `store.py`.
- `profile.db` erweitern (`users`, `finances`, `budget_history`, Bewertung in `past_events`).
- **Ergebnis:** Saubere Basis, alles läuft wie bisher — nur persistent und zentralisiert.

### Phase 1 — LangGraph-Skelett
- LangGraph einführen, `TripState` definieren, bestehenden Coordinator-Ablauf als Graph nachbauen.
- **Ergebnis:** Gleiche Funktion, aber als expliziter Graph — Grundlage für alles Weitere.

### Phase 2 — Regelbasierte Agenten ablösen
- Planning-Agent (LLM) baut Planning + Recommendation ab.
- Checklist-Agent (LLM) baut alten Checklist-Agent ab.
- Replanning-Agent auf LLM-Alternativenauswahl umstellen.
- Budget-Agent behalten.
- **Ergebnis:** Subsystem A ist nicht mehr regelbasiert, sondern LLM-gestützt.

### Phase 3 — Finanz-Subsystem
- Finanzmodell (manuelle Monatseingabe) + Finanz-Agent (verfügbares Budget, Prognose, Sparszenarien).
- Vorschlags- und Budget-Agent budgetbewusst machen.
- **Ergebnis:** Vorschläge passen zu Zeit **und** Geld.

### Phase 4 — Proaktive Automatisierung
- Flug-Provider + Monitoring-Agent (Wetter + Flüge).
- `scheduler.py` für regelmäßige Läufe (Monitoring, Tagesbrief, Vorschläge).
- **Ergebnis:** Echtes proaktives, zeitgesteuertes Verhalten.

### Phase 5 — Feedback-Schleife
- Reise-Feedback erfassen ("Wie hat dir X gefallen?") via Chat/Telegram → Profil-Lern-Agent.
- **Ergebnis:** Das System lernt mit jeder Reise dazu.

---

## 11. Offene Punkte (für später)

- **Flug-API:** Konkrete Wahl der API noch offen.
- **Feedback-Kanal:** Über welchen Weg fragt der Agent nach Reise-Feedback (In-App-Chat vs. Telegram)?
- **UI vs. API-Konsistenz:** Streamlit nutzt teils HTTP, teils direkten Import — beim Umbau vereinheitlichen.
- **Telegram-Senden:** Aktuell nur Lesen; für proaktive Push-Vorschläge ggf. auch Senden nötig.
