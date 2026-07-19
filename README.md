# Reiseagent USW

Dieses Projekt ist ein Reiseplanungs-Agent mit FastAPI-Backend, Streamlit-Oberflaeche und mehreren spezialisierten Agenten. Der Agent erstellt Reiseplaene, bewertet Aktivitaeten, beruecksichtigt Wetter, Budget, Kalender, Navigation und Telegram-Nachrichten und kann Vorschlaege automatisch anpassen.

## Studenten

- Valeriu Viziri
- Vu Thang Bui
- Suhaib Adel Saif Al-Odaini
- Ibrahim Danisman

## Ziel des Projekts

Der Reiseagent soll Nutzer bei der Planung und Begleitung einer Reise unterstuetzen. Dazu werden Reiseziel, Zeitraum, Interessen, Budget und weitere Kontextdaten verarbeitet. Aus diesen Informationen entsteht ein strukturierter Tagesplan mit Aktivitaeten, Kosten, Wetterinformationen und optionaler Synchronisation mit externen Diensten.

## Hauptfeatures

### Reiseplanung

- Erstellung neuer Reiseplaene ueber die API.
- Demo-Reise zum schnellen Testen.
- Tagesplaene mit mehreren Aktivitaeten pro Tag.
- Beruecksichtigung von Interessen wie Kultur, Essen, Natur, Sehenswuerdigkeiten und Shopping.
- Auswahl und Kuratierung von Orten aus externen Ortsdaten.
- Zeitplanung fuer Aktivitaeten inklusive Tagesstruktur.

### Budget und Kosten

- Berechnung einer Budgetuebersicht fuer geplante Reisen.
- Schaetzung von Aktivitaetskosten.
- Bankkonto-/Reisebudget-Funktion fuer Telegram:
  - `/bank`
  - `/bank_status`
  - `/bank_reset`
- Automatische Abbuchung geplanter Reisekosten vom simulierten Reisebudget.

### Wetter und Replanning

- Wetterdaten werden fuer Reiseplaene abgefragt.
- Bei schlechtem Wetter koennen alternative Aktivitaeten vorgeschlagen werden.
- Replanning-Vorschlaege koennen angenommen oder abgelehnt werden.
- Wetteraenderungen werden im Hintergrund ueberwacht.

### Flugueberwachung

- Optionales Monitoring von Flugnummern.
- Erkennung von Flugverspaetungen.
- Bei relevanten Verspaetungen kann ein angepasster Reiseplan vorgeschlagen werden.
- Telegram-Benachrichtigung bei Flug- oder Plananpassungen.

### Navigation

- Routenabfrage zwischen geplanten Aktivitaeten.
- Gehzeiten und Entfernungen koennen fuer einzelne Tagespunkte angezeigt werden.
- Automatische Navigationserinnerungen vor Aktivitaeten.

### Kalenderintegration

- Synchronisation von Reiseplaenen mit dem Kalender.
- Erstellung einzelner Kalendereintraege.
- Erkennung freier Tage aus Kalenderdaten.
- Nutzung freier Tage fuer automatische Freizeit- oder Reisevorschlaege.

### Profil und Personalisierung

- Speicherung von Interessen, vergangenen Ereignissen und freien Tagen.
- Lernen aus Telegram- und E-Mail-Kontexten.
- Wiederverwendung bekannter Interessen fuer bessere Vorschlaege.
- Lokale Speicherung in SQLite-Datenbanken.

### Telegram-Integration

- Versand von Reiseplaenen und Updates in Telegram.
- Callback-Buttons zum Annehmen oder Ablehnen von Vorschlaegen.
- Verarbeitung eingehender Telegram-Nachrichten.
- Telegram-Kommandos fuer Reisebudget und Reisefeedback.
- Bot-Mention in Gruppen wird bei Kommandos unterstuetzt, zum Beispiel `/feedback@BotName Berlin`.

### Reisefeedback

- Nach einer Reise kann Feedback gespeichert werden.
- Bewertungen werden nach Kategorien gespeichert:
  - Kultur
  - Essen
  - Natur
  - Sehenswuerdigkeiten
  - Shopping
- Gespeichertes Feedback kann in Telegram abgefragt werden:
  - `/feedback`
  - `/feedback Berlin`
  - `/bewertung Berlin`
  - `/bewertungen Berlin`
  - `/reise_feedback Berlin`
- Natuerliche Fragen wie `Wie war meine Reise in Berlin?` koennen erkannt werden, wenn bereits Feedback zu diesem Reiseziel vorhanden ist.

### Automatische Scheduler

- Woechentliche Vorschlaege fuer freie Tage.
- Monatliche Bankkonto-/Budget-Abfrage.
- Feedback-Abfrage nach beendeten Reisen.
- Hintergrundprozesse starten automatisch mit der Anwendung.

### Chat-Funktion

- Zu bestehenden Reisen kann per API eine Chat-Nachricht gesendet werden.
- Der Koordinator entscheidet, ob eine Frage beantwortet oder eine Aktion wie Replanning, Kalender-Sync oder Navigation ausgefuehrt wird.

## Wichtige Agenten

- `coordinator`: zentrale Steuerung und Auswahl der passenden Aktion.
- `planning_agent`: erstellt Tagesplaene.
- `recommendation_agent`: bewertet und sortiert Aktivitaeten.
- `budget_agent`: berechnet Reisekosten.
- `cost_estimation_agent`: schaetzt Preise fuer Aktivitaeten.
- `time_route_agent`: plant Uhrzeiten und Routen.
- `monitoring_agent`: ueberwacht Wetter und Fluege.
- `replanning_agent`: erstellt Alternativplaene.
- `navigation_agent`: erzeugt Navigationserinnerungen.
- `daily_brief_agent`: erstellt Tageszusammenfassungen.
- `profile_learner`: lernt Interessen aus Nachrichten.
- `suggestion_agent`: erstellt Vorschlaege fuer freie Tage.
- `bank_agent`: erkennt und speichert Budgetdaten.
- `feedback_agent`: erkennt und speichert Reisefeedback.

## Projektstruktur

```text
reiseagent/
  main.py              FastAPI-Anwendung und Telegram-Routing
  streamlit_app.py     Streamlit-Oberflaeche
  scheduler.py         Automatische Hintergrundaufgaben
  store.py             Speicherung von Reisen
  profile_store.py     Profil-, Budget- und Feedback-Speicherung
  prompts.py           Prompts fuer LLM-Agenten
  llm.py               LLM-Aufrufe und Logging
  agents/              Spezialisierte Agenten
  providers/           Externe Dienste wie Telegram, Kalender, Wetter, Orte
  data/                Projektdaten
```

## Starten

Abhaengigkeiten installieren:

```powershell
cd reiseagent
pip install -r requirements.txt
```

FastAPI-Backend starten:

```powershell
uvicorn main:app --reload
```

Streamlit-Oberflaeche starten:

```powershell
streamlit run streamlit_app.py
```

## Konfiguration

Die Konfiguration erfolgt ueber `.env`. Eine Vorlage liegt in `reiseagent/.env.example`. Je nach gewuenschten Features koennen API-Keys oder Zugangsdaten fuer Telegram, Kalender, Wetter, Orte, E-Mail oder LLM-Dienste notwendig sein.

Secrets und echte Tokens sollten nicht in die README geschrieben und nicht in Git committed werden.

## Tests und Checks

Ein einfacher Syntax-Check:

```powershell
cd reiseagent
python -m py_compile main.py profile_store.py providers\telegram.py agents\feedback_agent.py prompts.py
```

Weitere vorhandene Tests:

```powershell
python test_all.py
python test_calendar.py
python test_telegram_buttons.py
python test_flight_orchestrator.py
```

## Datenhaltung

Das Projekt nutzt lokale SQLite-Dateien:

- `trips.db` fuer Reiseplaene und Vorschlaege.
- `profile.db` fuer Profilinformationen, Bankkonto-Demo-Daten, Pending Prompts und Reisefeedback.

## Hinweis

Das Projekt ist ein Studienprojekt und dient zur Demonstration eines agentenbasierten Reiseplaners mit mehreren Integrationen. Einige externe Funktionen haengen von korrekt gesetzten API-Keys, Zugangsdaten und erreichbaren Diensten ab.
