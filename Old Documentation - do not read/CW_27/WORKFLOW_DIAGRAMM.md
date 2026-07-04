# Workflow-Übersicht — Reiseplanungs-Agent (Stand 28.06.2026)

> Diese Diagramme sind in **Mermaid** geschrieben. Zum Anzeigen einfach den Code-Block kopieren
> und auf **https://mermaid.live/** einfügen — oder direkt in GitHub/VS-Code rendern lassen.

---

## 1. Gesamtarchitektur (Schichten)

Wie die Bausteine zusammenhängen — von der Oberfläche über die Orchestrierung und die Agenten
bis zur geteilten Infrastruktur und den externen Diensten.

```mermaid
flowchart TB
    subgraph UI["🖥️ Oberfläche"]
        ST["Streamlit App<br/>(Web-UI)"]
        API["FastAPI<br/>(main.py + Hintergrund-Threads)"]
    end

    subgraph ORCH["🧠 Orchestrierung"]
        COORD["coordinator.py<br/>handle_plan_request / handle_chat_message"]
        GRAPH["graph.py<br/>LangGraph-Orchestrator"]
        SCHED["scheduler.py<br/>wöchentlicher Trigger (Sa)"]
    end

    subgraph AGENTS["🤖 Agenten"]
        PLAN["planning.py"]
        TIME["time_route_agent.py"]
        SUGG["suggestion_agent.py"]
        CALAG["calendar_agent.py"]
        PROF["profile_learner.py"]
        MON["monitoring.py"]
    end

    subgraph INFRA["⚙️ Geteilte Infrastruktur"]
        LLM["llm.py + prompts.py<br/>(zentraler LLM-Zugang + Trace)"]
        MEM["memory.py<br/>(RAG / Embeddings)"]
        STORE["store.py<br/>(trips.db)"]
        PSTORE["profile_store.py<br/>(profile.db)"]
    end

    subgraph EXT["🌐 Externe Dienste"]
        GROQ["Groq LLM"]
        GCAL["Google Calendar"]
        TG["Telegram"]
        MAIL["Gmail / IMAP"]
        DATA["OpenTripMap /<br/>Wetter / Flüge"]
    end

    ST --> API --> COORD
    COORD --> GRAPH
    COORD --> PLAN
    SCHED --> CALAG
    SCHED --> SUGG

    PLAN --> TIME
    PLAN --> MEM
    SUGG --> MEM
    PROF --> MEM
    PROF --> PSTORE

    AGENTS --> LLM --> GROQ
    CALAG --> GCAL
    PROF --> MAIL
    SUGG --> TG
    MON --> TG
    MON --> DATA
    PLAN --> DATA
    COORD --> STORE
```

---

## 2. Ablauf A — Manuelle Reiseplanung (Nutzer stößt an)

Der klassische Weg: Der Nutzer füllt das Formular aus, das System orchestriert die Agenten
und liefert einen fertigen Tagesplan zurück.

```mermaid
flowchart TD
    U["👤 Nutzer füllt Formular aus"] --> A["coordinator.handle_plan_request"]
    A --> W["Wetter-Agent<br/>(Wetterdaten laden)"]
    A --> P["get_places<br/>(Orte laden + Dubletten entfernen)"]
    P --> C["planning.create_plan<br/>LLM kuratiert den Plan"]
    M["memory.retrieve_context<br/>(RAG: passende Nachrichten)"] --> C
    C --> T["time_route_agent<br/>LLM legt Uhrzeiten + Fahrtzeiten"]
    T --> B["budget.py + checklist.py"]
    B --> S["store.py<br/>Plan speichern (trips.db)"]
    S --> CAL["Google Calendar<br/>Plan eintragen"]
    S --> R["📋 Fertiger Plan in Streamlit"]

    LLM["llm.py + prompts.py → Groq"] -.-> C
    LLM -.-> T
```

---

## 3. Ablauf B — Chat-Befehl (LangGraph-Orchestrator)

Statt Regex entscheidet jetzt ein LLM per Tool-Calling, welcher Handler eine Chat-Nachricht
ausführt.

```mermaid
flowchart TD
    U["👤 Chat-Nachricht<br/>z.B. 'verschiebe Abendessen auf 20 Uhr'"] --> H["coordinator.handle_chat_message"]
    H --> G["graph.run_chat<br/>(LangGraph)"]
    G --> O{"🧠 Orchestrator-Knoten<br/>LLM wählt Tool"}

    O -->|change_time| T1["Zeit ändern"]
    O -->|replan_day| T2["Tag neu planen"]
    O -->|delete_activity| T3["Aktivität löschen"]
    O -->|suggest_alternatives| T4["Alternative vorschlagen"]
    O -->|sync_calendar| T5["Kalender synchronisieren"]
    O -->|answer_question| T6["Frage beantworten"]

    T1 --> RES["Plan aktualisiert<br/>+ Kalender-Sync + Antwort"]
    T2 --> RES
    T3 --> RES
    T4 --> RES
    T5 --> RES
    T6 --> RES

    O -.->|kein Key → Fallback| FB["regelbasierte Antwort"]
```

---

## 4. Ablauf C — Proaktiver Scheduler + Telegram (das neue Herzstück)

Einmal pro Woche denkt das System selbst voraus, erkennt freie Tage und schlägt per Telegram
eine Reise vor. Der Nutzer entscheidet per Knopfdruck.

```mermaid
flowchart TD
    CLK["⏰ scheduler.py<br/>läuft samstags (oder /api/scheduler/run)"] --> FD["calendar_agent.get_truly_free_days"]
    FD --> GC["Google Calendar lesen<br/>(Mehrtages-Events aufgespalten)"]
    GC --> INT["🧠 LLM interpretiert jeden Tag<br/>free / busy + Begründung"]
    INT --> SUG["suggestion_agent<br/>erstellt Vorschlag (mit RAG + Profil)"]
    SUG --> TG["📲 Telegram-Nachricht<br/>mit [✅ Ja] / [❌ Nein]"]

    TG --> DEC{"Nutzer drückt"}
    DEC -->|❌ Nein| REJ["Vorschlag als abgelehnt markiert"]
    DEC -->|✅ Ja| ACC["handle_plan_request (auto=True)"]
    ACC --> PLAN["Plan erstellt"]
    PLAN --> CALS["Google Calendar eintragen"]
    PLAN --> SEND["📋 Plan per Telegram senden"]
```

---

## 5. Hintergrund — Profil-Lernen & Monitoring (läuft dauerhaft)

Zwei Hintergrund-Stränge, die das System „intelligent" und „aufmerksam" machen.

```mermaid
flowchart LR
    subgraph LEARN["📥 Profil-Lernen"]
        MSG["Telegram / Gmail / IMAP<br/>Nachrichten"] --> PL["profile_learner.py"]
        PL --> INT2["Interessen<br/>→ profile.db"]
        PL --> EMB["Volltext + Embedding<br/>→ memory.py (RAG)"]
    end

    subgraph WATCH["🔍 Monitoring"]
        LOOP["monitoring.py<br/>(Hintergrund-Thread)"] --> WX["Wetter prüfen"]
        LOOP --> FL["Flug prüfen"]
        FL --> DELAY{"Verspätung?"}
        DELAY -->|ja| REPLAN["Neuplanung + Telegram-Vorschlag"]
    end
```

---

## Kernbotschaft für die Präsentation

- **Ein zentraler LLM-Zugang** (`llm.py`) speist alle KI-Funktionen — mit Live-Trace zum Mitverfolgen.
- **Drei Eintrittspunkte:** manuelle Planung, Chat (LangGraph), proaktiver Scheduler.
- **Gedächtnis (RAG):** das System merkt sich Nachrichten und personalisiert damit Pläne.
- **Human-in-the-Loop:** proaktive Vorschläge kommen automatisch, aber der Mensch entscheidet per Knopf.
- **Robust by design:** ohne API-Key oder bei Fehlern fällt alles sauber auf die alten, regelbasierten Wege zurück.
