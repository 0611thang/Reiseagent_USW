# Systemarchitektur — Aktueller Stand

Dieses Dokument beschreibt das System so, wie es **heute tatsächlich funktioniert** — nicht wie es werden soll. Es richtet sich an Teammitglieder, die den Code noch nicht kennen, und erklärt den Datenfluss, die Verantwortlichkeiten der einzelnen Komponenten und die bekannten Schwachstellen.

---

## Überblick: Was das System tut

Der Reiseplanungsagent nimmt eine Nutzeranfrage (Zielort, Budget, Dauer, Interessen) und erstellt daraus automatisch einen vollständigen Reiseplan mit Tagesablauf, Budget-Aufschlüsselung und Packliste. Nach der Erstellung kann der Nutzer den Plan per Chat anpassen und wird im Hintergrund über Wetter- und Flugänderungen informiert.

**Technologiestack:**
- **Backend:** Python + FastAPI (REST API)
- **Frontend:** Streamlit (separat, kommuniziert per HTTP mit dem Backend)
- **LLM:** Groq API (`llama-3.3-70b-versatile`) — nur für Planerstellung und freie Chat-Fragen
- **Datenbank:** SQLite (`profile.db`) — nur für Nutzerprofil und Vorschläge, **nicht** für Reisedaten
- **Externe APIs:** OpenTripMap (Sehenswürdigkeiten), OpenWeatherMap (Wetter), Aviationstack (Flüge), OpenRouteService (Navigation), Google Calendar, Telegram

---

## Wie eine neue Reise entsteht: Der Planungsprozess

Wenn ein Nutzer einen Reiseplan anfordert (POST `/api/trips/plan`), läuft folgender Prozess ab:

### 1. Coordinator startet die Pipeline (`agents/coordinator.py`)

Der Coordinator ist das Herzstück des Systems. Er nimmt die Anfrage entgegen und ruft nacheinander alle anderen Agenten auf. Er sammelt deren Ergebnisse und fügt sie zu einem fertigen Plan zusammen.

```
Nutzeranfrage
     │
     ▼
Coordinator
     ├── Wetter laden (OpenWeatherMap)
     ├── POIs laden (OpenTripMap)
     ├── Planning Agent → Tagesablauf erstellen
     ├── Budget Agent → Kosten berechnen
     ├── Checklist Agent → Packliste generieren
     └── Recommendation Agent → Aktivitäten bewerten
```

### 2. Planning Agent erstellt den Tagesablauf (`agents/planning.py`)

Dieser Agent ruft das LLM (Groq) auf und gibt ihm: Zielort, Dauer, Interessen, Wetterdaten und eine Liste verfügbarer POIs. Das LLM gibt einen strukturierten Tagesplan zurück — mit konkreten Uhrzeiten, Aktivitäten und Standortdaten.

### 3. Budget Agent berechnet die Kosten (`agents/budget.py`)

Kein LLM — rein deterministisch. Der Agent nimmt den erstellten Plan und schätzt Kosten für Unterkunft, Mahlzeiten, Transport und Aktivitäten basierend auf dem angegebenen Budget und der Reiseart.

### 4. Checklist Agent generiert die Packliste (`agents/checklist.py`)

Ebenfalls LLM-gestützt. Erstellt eine reisespezifische Checkliste — abhängig von Reisedauer, Klima (aus den Wetterdaten) und Reisestil.

### 5. POI Agent lädt Sehenswürdigkeiten (`providers/places.py`)

Kein Agent im klassischen Sinne, sondern ein Provider. Ruft OpenTripMap ab, filtert nach den Interessen des Nutzers und berechnet für jeden Ort einen Quality Score (0–100), der Beliebtheit, Bewertungen und Relevanz kombiniert. Dieser Score beeinflusst, welche Orte der Planning Agent empfohlen bekommt.

### 6. Ergebnis wird gespeichert und synchronisiert

Nach der Planerstellung passiert automatisch:
- Plan wird im **In-Memory Store** (`store.py`) abgelegt
- Vollständiger Plan wird in **Google Calendar** synchronisiert (`providers/calendar.py`)
- Telegram-Nachricht mit dem Plan wird verschickt (`providers/telegram.py`)

---

## Wo Daten gespeichert werden

Das ist der wichtigste Punkt zum Verständnis des Systems — und seine größte Schwachstelle:

### In-Memory Store (`store.py`) — für Reisedaten

```python
trips: dict = {}  # globales Dictionary, lebt nur solange der Server läuft
```

Alle aktiven Reisepläne, Chat-Verläufe, Proposals und Monitoring-Daten leben als Python-Dictionary im Arbeitsspeicher. **Beim Neustart des Servers sind alle Reisedaten verloren.** Das bedeutet auch, dass das Hintergrund-Monitoring nach einem Neustart keine Reisen mehr findet und nicht mehr aktiv ist.

### SQLite (`profile.db`) — für Nutzerprofil

Das Nutzerprofil wird persistent in einer SQLite-Datenbank gespeichert. Sie enthält vier Tabellen:

| Tabelle | Inhalt |
|---|---|
| `interests` | Erkannte Interessen mit Score (z.B. "Museen": 4.5) |
| `past_events` | Vergangene Events aus Telegram/Gmail |
| `free_days` | Erkannte freie Tage aus dem Kalender |
| `suggestions` | LLM-generierte Aktivitätsvorschläge für freie Tage |

---

## Chat-Steuerung: Wie Plananpassungen funktionieren

Der Chat (`POST /api/trips/{trip_id}/chat`) verwendet eine dreistufige Verarbeitungskette:

### Stufe 1: Kalender-Sync-Erkennung

Enthält die Nachricht Wörter wie "kalender" + "synchronisiere"/"aktualisiere", wird direkt eine Google-Kalender-Synchronisation ausgelöst.

### Stufe 2: Plan-Änderungs-Erkennung (Keyword/Regex)

Der Text wird in ASCII normalisiert (Umlaute → ae/oe/ue) und gegen eine Liste von Schlüsselwörtern geprüft. Je nach erkannter Absicht wird eine von sechs Aktionen ausgeführt:

| Erkannte Absicht | Aktion |
|---|---|
| "vorschlag", "alternative", "anders" | Alternativen aus POI-Datenbank vorschlagen |
| "verschiebe", "uhrzeit" | Uhrzeit einer Aktivität ändern |
| "lösche", "entferne" | Aktivität aus dem Plan löschen |
| "shuffle", "mische", "neu" | Ganzen Tag neu planen |
| "fülle", "vervollständige" | Leere Slots mit POIs auffüllen |
| "ersetze", "tausch" | Eine Aktivität durch andere ersetzen |

Wenn kein Schlüsselwort erkannt wird: direkt zu Stufe 3.

### Stufe 3: LLM-Fallback (Groq)

Alle anderen Nachrichten werden als freier Chat an Groq weitergeleitet. Das LLM bekommt den aktuellen Plan als Kontext und antwortet auf die Frage — kann aber dabei **keine Planänderungen vornehmen** (kein Tool-Calling implementiert).

---

## Hintergrund-Monitoring: Was automatisch passiert

Beim Serverstart werden zwei Hintergrundprozesse in eigenen Threads gestartet:

### Wetter- und Flug-Monitoring (alle 30 Minuten)

Läuft in `_monitoring_loop()` → ruft `monitoring.monitor_all_active_trips()` auf.

Für jede aktive Reise:
1. Aktuelles Wetter von OpenWeatherMap abrufen
2. Wetterdaten im Plan aktualisieren (wenn sich etwas geändert hat)
3. Bei schlechtem Wetter (Regen, Sturm, Schnee): automatisch einen Replanning-Vorschlag erstellen
4. Flugstatus abrufen (über `providers/flights.py`)

Vorschläge erscheinen in der UI als "Proposals" — der Nutzer kann sie annehmen oder ablehnen.

### Navigations-Erinnerungen (jede Minute)

Läuft in `_navigation_reminder_loop()`. Prüft jede Minute, ob eine Aktivität demnächst beginnt. Wenn ja:
- Route berechnen (Fußweg + Auto, über OpenRouteService)
- Telegram-Erinnerung senden: "In X Minuten beginnt [Aktivität]"
- Die Vorlaufzeit = Fußweg-Dauer + 15 Minuten Puffer

---

## Proaktive Vorschläge: Der Suggestion Agent

Das System erkennt freie Tage im Google Kalender und generiert proaktiv Aktivitätsvorschläge.

**Ablauf:**
1. `free_time_detector.py` fragt Google Calendar ab → findet freie Tage in den nächsten 21 Tagen → speichert in `free_days`-Tabelle
2. `suggestion_agent.py` liest freie Tage + Interessen aus `profile.db` → ruft Groq auf → speichert Vorschläge in `suggestions`-Tabelle
3. Nutzer sieht pending Vorschläge (`GET /api/suggestions/pending`) und kann annehmen oder ablehnen
4. Bei Annahme: automatisch in Google Calendar eintragen
5. Bei Ablehnung: Groq generiert sofort einen Ersatzvorschlag

---

## Nutzerprofil-Lernen

Der `profile_learner.py` Agent liest Telegram-Nachrichten und Gmail-E-Mails der letzten 72 Stunden und extrahiert mit Groq Interessen und vergangene Events daraus. Diese werden mit einem Score in der `interests`-Tabelle akkumuliert — je öfter ein Interesse erkannt wird, desto höher der Score.

Das Profil beeinflusst, welche Orte der POI Agent bevorzugt lädt und welche Vorschläge der Suggestion Agent generiert.

---

## Bekannte Schwachstellen

### 1. In-Memory Store (kritisch)

Reisedaten überleben keinen Server-Neustart. Das macht das Hintergrund-Monitoring unzuverlässig: nach einem Neustart findet es keine Reisen mehr. **Geplante Lösung:** Migration auf SQLite (`trips.db`).

### 2. Groq-Client verteilt im Code

Der Groq-Client wird in mehreren Agenten direkt instanziiert (`from groq import Groq; client = Groq(...)`). Es gibt kein zentrales LLM-Modul. Das erschwert den Wechsel des LLM-Providers. **Geplante Lösung:** Zentrales `llm.py` erstellen.

### 3. Chat-Steuerung über Regex (fragil)

Die Keyword-Erkennung im Chat funktioniert nur für genau die einprogrammierten deutschen Formulierungen. Synonyme, Tippfehler oder andere Satzstellungen werden nicht erkannt. **Geplante Lösung:** LLM-Tool-Calling in Phase 2.

### 4. Kein Zustand zwischen Server-Neustarts im Monitoring-Thread

Der `sent_reminders`-Set für Navigations-Erinnerungen lebt im Arbeitsspeicher des Threads — nach Neustart werden Erinnerungen für den aktuellen Tag erneut gesendet.

---

## Verzeichnisstruktur

```
reiseagent/
├── main.py                    # FastAPI-App, Startup, Endpunkte
├── store.py                   # In-Memory Store für Reisedaten (!)
├── profile_store.py           # SQLite-Zugang für Nutzerprofil
├── agents/
│   ├── coordinator.py         # Orchestrierung + Chat-Steuerung (~1300 Zeilen)
│   ├── planning.py            # LLM-Tagesplanung
│   ├── budget.py              # Deterministische Kostenkalkulation
│   ├── checklist.py           # LLM-Packlisten-Generierung
│   ├── recommendation.py      # Aktivitätsbewertung
│   ├── replanning.py          # Wetter-basierte Planänderungen
│   ├── monitoring.py          # Wetter- und Flug-Monitoring
│   ├── suggestion_agent.py    # Proaktive Vorschläge für freie Tage
│   ├── free_time_detector.py  # Freie-Tage-Erkennung aus Kalender
│   ├── profile_learner.py     # Interessen-Extraktion aus Nachrichten
│   ├── navigation.py          # Erinnerungstext-Generierung
│   └── daily_brief.py         # Tages-Zusammenfassung
└── providers/
    ├── places.py              # OpenTripMap + Quality Scoring
    ├── weather.py             # OpenWeatherMap
    ├── flights.py             # Aviationstack Flugstatus
    ├── navigation.py          # OpenRouteService Routenberechnung
    ├── calendar.py            # Google Calendar Sync
    ├── telegram.py            # Telegram Bot
    ├── gmail.py               # Gmail-Lesezugang
    └── geocoding.py           # Koordinaten-Auflösung
```
