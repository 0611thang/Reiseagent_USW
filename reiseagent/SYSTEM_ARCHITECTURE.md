# Systemarchitektur — Reiseplanungs-Agent

## Vision

Der Agent soll kein passives Tool sein, das nur auf Anfragen reagiert. Er soll **proaktiv** handeln: Kalender beobachten, Budget kennen, Vorlieben lernen — und daraus selbstständig personalisierte Reise- und Freizeitvorschläge machen, die zu Zeit, Geld und persönlichem Geschmack passen.

---

## Einstiegspunkte (Trigger)

**1. Manuelle Nutzeranfrage**
Der Nutzer gibt aktiv eine Anfrage ein: Ziel, Reisedaten, Budget, Personenanzahl, Interessen (gut essen, Museen, Outdoor usw.).

**2. Proaktiver Kalender-Trigger**
Der Agent überwacht ständig den Kalender und erkennt freie Zeitfenster selbstständig. Beispiel: Freitag ist frei, Sonntag steht ein Termin an → Agent schlägt eine Reise von Freitag bis Samstag 18:00 Uhr vor, damit der Nutzer rechtzeitig zurück ist.

---

## Komponenten & Agenten

### 1. Kalender-Agent
- Liest den persönlichen Kalender des Nutzers
- Erkennt freie Tage, freie Wochenenden, Urlaubs-Fenster
- Berücksichtigt umliegende Termine beim Planen
- Speichert erkannte freie Slots in der Datenbank

### 2. Finanz-Agent
- Verwaltet ein **virtuelles Finanzmodell** des Nutzers in der Datenbank
- Nutzer pflegt manuell am 1. des Monats:
  - Monatliches Gehalt
  - Fixkosten (Miete, Lebensmittel, Versicherungen etc.)
  - Gewünschtes Freizeit-/Reisebudget für den Monat
- Kann zukünftige Budgets prognostizieren
- Erkennt Sparpotenziale: „Wenn du 3 Monate je 300 € zurücklegst, hast du im Juli 2.400 € Reisebudget."
- Alle Reise- und Aktivitätsvorschläge werden an die tatsächliche finanzielle Lage angepasst

### 3. Profil-Lern-Agent
- Erstellt und aktualisiert ein persistentes **Nutzerprofil** in der Datenbank
- Lernt Vorlieben aus mehreren Quellen:
  - Nachrichten (Telegram, E-Mail): z. B. jemand schlägt ein Konzert vor, Nutzer stimmt begeistert zu → Interesse an Musik erhöht sich
  - Feedback während und nach Reisen: Agent fragt aktiv „Wie hat dir das gefallen?" und speichert die Bewertung
  - Vergangene Buchungen und besuchte Orte
- Beispiel: Chinesisches Essen wurde nie hoch bewertet, Italienisch immer → Agent sucht gezielt nach italienischen Restaurants

### 4. Überwachungs-Agent (Monitoring)
Läuft im Hintergrund mit konfigurierbaren Zeitintervallen und prüft laufend:
- **Wetter** am Reiseort: Bei schlechtem Wetter und geplanten Outdoor-Aktivitäten → Plan anpassen
- **Flugstatus**: Verspätungen oder Ausfälle erkannt → Folgeeffekte analysieren (z. B. Restaurantreservierung nicht mehr erreichbar) → Nutzer proaktiv informieren und neuen Plan vorschlagen
- Weitere relevante Informationen (lokale Events, Streiks)

Bei kritischen Änderungen → neuer Planvorschlag → Nutzer bestätigt oder lehnt ab (Human-in-the-Loop).

### 5. Vorschlags- & Planungs-Agent
- Kombiniert: freie Slots (Kalender) + verfügbares Budget (Finanz) + Vorlieben (Profil) + aktuelle Bedingungen (Wetter, Flüge)
- Generiert personalisierte Vorschläge:
  - Spontane Kurztrips für freie Wochenenden
  - Langfristige Reiseplanung für größere Budgets
  - Aktivitätsvorschläge für einzelne freie Tage
- Stellt dem Nutzer Optionen vor — keine Einzelentscheidungen
- Beispiele:
  - „Du hast dieses Wochenende frei und 200 € Budget — Kurztrip nach Hamburg?"
  - „Im Juli hast du 2 Wochen frei und könntest bis dahin 1.800 € ansparen — soll ich Reisen dafür suchen?"

### 6. Tagesbrief-Agent *(bereits implementiert)*
- Morgens einen personalisierten Tagesbrief generieren
- Kombiniert: Tagesplan + Wetter + relevante Mails/Nachrichten (Buchungsbestätigungen, Hinweise, Absagen)

### 7. Navigations-Agent *(bereits implementiert)*
- Berechnet Routen zwischen Aktivitäten
- Sendet Push-Erinnerungen mit Abfahrtszeit (inkl. Puffer)

---

## Externe Datenquellen & Konnektoren

| Quelle | Zweck |
|---|---|
| **Google Calendar** | Freie Slots erkennen, Termine berücksichtigen |
| **Telegram** | Interessen aus Nachrichten lernen, Verabredungen erkennen |
| **Gmail** | Buchungsbestätigungen, Ereignisse, Interessen aus E-Mails |
| **Wetter-API** (Open-Meteo) | Echtzeit-Wetter für Überwachung und Planung |
| **Flug-API** | Flugstatus, Verspätungen, Ausfälle |
| **POI-API** (OpenTripMap o. ä.) | Aktivitäten, Restaurants, Sehenswürdigkeiten suchen |
| **Navigations-API** (OpenRouteService) | Routen und Gehzeiten zwischen Aktivitäten |

---

## Datenbankstruktur (Profil & Persistenz)

### profile.db — persistente SQLite-Datenbank

| Tabelle | Inhalt |
|---|---|
| `users` | Basisprofil (ID, Name, Alter, Heimatstadt) |
| `interests` | Vorlieben mit kumulativem Score und Quelle |
| `past_events` | Besuchte Orte/Events mit Bewertung und Datum |
| `free_days` | Erkannte freie Tage aus Kalender |
| `suggestions` | Generierte Vorschläge mit Status (pending/accepted/rejected) |
| `finances` | Einnahmen, Fixkosten, verfügbares Monatsbudget |
| `budget_history` | Historisches Budget pro Monat (für Prognosen) |

### Trips — persistente Speicherung (zu entscheiden)
Aktive Reisepläne und laufende Trips sollen persistent gespeichert werden (nicht mehr In-Memory), da der Überwachungs-Agent während einer laufenden Reise auf die Daten zugreifen muss — auch nach einem Server-Neustart.

---

## Offene Entscheidungen

| # | Frage | Status |
|---|---|---|
| 1 | Regelbasierte Agenten (Planning, Recommendation, Budget): ersetzen oder ablösen? | Werden durch LLM-gestützte Logik ersetzt; bei fehlendem Mehrwert für die Zielvision gelöscht und durch neue Agenten abgelöst |
| 2 | Trips persistent in DB statt In-Memory? | Architektonisch empfohlen (siehe oben) |
| 3 | LangGraph als Orchestrator? | Noch offen |
| 4 | WhatsApp-Anbindung? | Nein — Telegram reicht |
| 5 | Finanzmodell: manuell oder Banking-API? | Manuell durch Nutzer (monatliche Eingabe) |
