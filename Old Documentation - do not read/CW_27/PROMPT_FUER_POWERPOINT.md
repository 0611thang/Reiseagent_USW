# Prompt für Claude — PowerPoint erstellen

> **So benutzt du es:** Kopiere ALLES unterhalb der Linie und füge es in Claude (claude.ai) ein.
> Claude hat die PPTX-Skill und baut daraus die Präsentation als Download-Datei.

---

Erstelle mir eine professionelle PowerPoint-Präsentation (.pptx) über unser Studienprojekt „Reiseplanungs-Agent". Sprache: **Deutsch**. Zielpublikum: unser Professor in einer Review-Session. Nutze das Format 16:9 (LAYOUT_WIDE).

## Design-Vorgaben (bitte einhalten)

- **Farbpalette (Reise + KI, ruhig & seriös):**
  - Dunkel (Titel-/Schlussfolien-Hintergrund): `0E2A2A` (Tiefes Petrol)
  - Primär (Titel, Akzentboxen): `0D7377` (Teal)
  - Akzent (Highlights, Nummern): `D9962F` (warmes Amber/Gold)
  - Text dunkel: `1B2D2D` · Gedämpfter Text: `5E7472`
  - Karten-Hintergrund hell: `F3F8F7` · Teal-Tönung: `E4F0EF`
  - Inhaltsfolien auf weißem Hintergrund, Titel-/Schlussfolie auf dunklem Petrol.
- **Schriften:** Überschriften in Cambria (bold), Fließtext in Calibri.
- **Motiv:** nummerierte Kreise (Amber/Teal) für Schritte; Karten mit leichtem Schatten und dünner Linie. **Keine** Akzentstreifen/Farbbalken, **keine** Linien unter Titeln.
- **Layout:** linksbündiger Fließtext, nur Titel zentriert nötig; mind. 1,3 cm Rand; jede Folie hat ein visuelles Element (Boxen, Pfeile, Kreise).
- Titel 33–36 pt, Abschnittsüberschrift 18–20 pt, Fließtext 14–15 pt, Bildunterschrift 12–13 pt.

## Folien (genau diese 9, in dieser Reihenfolge)

**Folie 1 — Titel & Übersicht (dunkler Hintergrund)**
- Kleiner Kicker oben: „UNTERNEHMENSSOFTWARE · PROJEKT" (Amber)
- Großer Titel: „Reiseplanungs-Agent"
- Untertitel: „Ein Multi-Agenten-System, das Reisen automatisch plant — gesteuert von einem Sprachmodell (LLM), mit Gedächtnis und proaktiven Vorschlägen."
- Drei nummerierte Kästen unten:
  1. **Spezialisierte Agenten** — Jeder Agent macht eine Sache: Orte, Wetter, Planung, Zeiten, Kalender.
  2. **LLM im Kern** — Das Sprachmodell trifft die kreativen Entscheidungen, über eine zentrale Schnittstelle.
  3. **Robust & sicher** — Fällt das LLM aus, übernimmt automatisch der bewährte regelbasierte Weg.

**Folie 2 — Gesamtüberblick / Architektur (4 Schichten als gestapelte Reihen)**
Titel: „Vier Schichten — vom Nutzer bis zu den externen Diensten". Jede Reihe: links Schicht-Name, rechts 3 Boxen.
- EINTRITTSPUNKTE: Manuelle Planung · Chat-Befehl · Proaktiv (samstags)
- ORCHESTRIERUNG & AGENTEN: coordinator.py · graph.py (LangGraph) · calendar_agent.py
- KI-KERN & DATEN: llm.py + prompts.py · memory.py (RAG) · Datenbanken
- EXTERNE DIENSTE: Groq LLM · Google Calendar · Telegram · Mail · APIs
- Fußnote: „Ein zentraler LLM-Zugang (llm.py) speist alle KI-Funktionen — mit Live-Trace zum Mitverfolgen."

**Folie 3 — Manuelle Reiseplanung: Ablauf (5 nummerierte Schritte nebeneinander, mit Pfeilen)**
Titel: „Der Ablauf: vom Formular zum fertigen Plan".
1. **Eingabe** — Nutzer füllt Formular aus: Ziel, Tage, Interessen.
2. **Orte + Vorfilter** — Orte laden, Müll filtern, Doubletten entfernen.
3. **LLM-Planner** — KI wählt Aktivitäten und ordnet sie den Tagen zu. *(Amber hervorheben)*
4. **Zeit & Routen** — Agent legt Uhrzeiten und Laufwege fest.
5. **Finale Ausgabe** — Budget, Checkliste, fertiger Plan in Streamlit.
- Fußnote: „Die KI trifft die kreativen Entscheidungen (Schritt 3), der Code macht die exakten Berechnungen (Filter, Budget, Wege)."

**Folie 4 — Orte & Vorfilter (3 Spalten-Karten)**
Titel: „Orte laden — Vorfilter und Doubletten-Erkennung".
- **1 · Müll-Vorfilter** (Harter Ja/Nein-Filter): Name zu kurz oder mit Ziffern → raus; gesperrte Wörter (z. B. Haltestellen) → raus; nur echte, brauchbare Orte bleiben.
- **2 · Qualitäts-Score** (Weiche Bewertung 0–100): Hauptsignal OpenTripMap-Rate × 6; kleiner Bonus für Museen/Kultur/Aussicht; niedrige Schwelle (10) → ca. 50 Orte bleiben.
- **3 · Doubletten weg** (Zwei Runden): Runde 1 exakt gleicher Name; Runde 2 < 150 m Abstand ODER Namens-Ähnlichkeit ≥ 82 %.
- Fußnote: „Ergebnis: eine saubere Liste von ca. 50 Orten — die Auswahl für den LLM-Planner."

**Folie 5 — LLM-Planner (zwei Karten nebeneinander)**
Titel: „Der LLM-Planner — die KI kuratiert den Plan".
- Links **Was bekommt die KI?**: die ~50 gefilterten Orte (Name, Kategorie, Kosten); Reiseziel, Dauer, Wetter, Interessen; klare Regeln (≥ 4 Aktivitäten/Tag, je 1 Mittag- und Abendessen, keine Doubletten); Kontext aus dem Gedächtnis (RAG), falls vorhanden.
- Rechts **Was gibt die KI zurück?**: eine Zuordnung welche Orte an welchem Tag; wird streng geprüft; bei Fehler 1× Reparatur-Versuch; klappt es nicht, greift der alte regelbasierte Weg als Sicherheitsnetz.

**Folie 6 — Zeit-/Routen-Agent → finale Ausgabe (zwei Karten)**
Titel: „Zeit- & Routen-Agent — und die finale Ausgabe".
- Links **Zeit- & Routen-Agent**: realistische Start-/Endzeiten je Aktivität; Mittagessen ab 12:00, Abendessen ab 18:30; geschätzte Laufzeit zwischen Orten; nichts endet nach Mitternacht.
- Rechts **Finale Ausgabe**: Budget-Agent rechnet Gesamtkosten; Checklisten-Agent erstellt Packliste; optional Flugdaten passen Tag 1 an; Plan erscheint in Streamlit + Google Calendar.

**Folie 7 — LangGraph-Orchestrator (Flussdiagramm + Tool-Liste)**
Titel: „LangGraph-Orchestrator — der Chat versteht den Nutzer".
- Einleitung: „Statt hunderter Textmuster (Regex) entscheidet jetzt ein LLM, welche Aktion eine Chat-Nachricht auslöst."
- Fluss (3 Boxen mit Pfeilen): **Nachricht** → **Orchestrator (LLM wählt Tool)** *(Amber)* → **Handler (führt aus)**.
- Karte mit „Die 9 Werkzeuge, aus denen das LLM wählt:" als 3×3-Raster: Zeit ändern · Tag neu planen · Alternative vorschlagen · Aktivität löschen · Plan auffüllen · Aktivität ersetzen · Aktivität hinzufügen · Kalender synchronisieren · Frage beantworten.
- Fußnote: „Das LLM wählt nur die Absicht — die Details (welche Uhrzeit, welcher Tag) liest der Handler selbst aus."

**Folie 8 — RAG & Gedächtnis (zwei Karten)**
Titel: „RAG & Gedächtnis — das System merkt sich den Nutzer".
- Links **Was ist ein Embedding?**: „Ein Embedding ist der mathematische Fingerabdruck eines Textes — eine Liste von Zahlen, die seinen Inhalt beschreibt. Inhaltlich ähnliche Texte bekommen ähnliche Zahlen und liegen nah beieinander." Zusatz: „Berechnet von **sentence-transformers** (Modell all-MiniLM-L6-v2) — läuft lokal, kein extra API-Key nötig." Beispiel: „‚mit den Kindern ins Museum' und ‚Paris Kunstausstellung' liegen nah beieinander."
- Rechts **So funktioniert es (RAG)** als 3 nummerierte Schritte:
  1. **Speichern** — Telegram-/Mail-Nachrichten werden als Embedding in der Datenbank abgelegt.
  2. **Suchen** — Zum Reiseziel werden die ähnlichsten Nachrichten herausgesucht (Cosine-Ähnlichkeit).
  3. **Einspeisen** — Die Treffer kommen als Kontext in den Planungs-Prompt → persönlicherer Plan.

**Folie 9 — Kernbotschaften (dunkler Hintergrund, 2×2 Kästen)**
Titel: „Was unser System ausmacht".
- **Drei Eintrittspunkte** — Manuelle Planung, Chat und proaktiver Scheduler teilen dieselben Agenten.
- **LLM trifft Entscheidungen** — Auswahl, Uhrzeiten und Intent; Berechnungen bleiben im zuverlässigen Code.
- **Gedächtnis (RAG)** — Embeddings personalisieren Pläne anhand echter Nachrichten des Nutzers.
- **Robust by design** — Ohne API-Key fällt alles sauber auf den regelbasierten Weg zurück — kein Absturz.

## Zusatz
Füge passende Sprecher-Notizen (kurze Stichpunkte) zu jeder Folie hinzu. Gib mir die fertige .pptx als Download.
