# Review-Session mit dem Prof — Kurznotizen (für Abwesende)

> Schnell-Zusammenfassung der wichtigsten Punkte. Datum: 2026-06-23.

---

## Das Hauptproblem, das der Prof sieht
- **Kein klarer Unterschied zu ChatGPT.** In der Demo war nicht erkennbar, dass im Hintergrund echte Agenten
  orchestrieren und mehr leisten als ein normaler ChatGPT-Chat. Das muss sichtbar werden.

## Was er konkret bemängelt hat
- **Qualitätssicherung fehlt.** Im generierten Tagesplan stand z.B. **Notre-Dame doppelt**. Jeder
  (Sub-)Agent muss sicherstellen, dass sein Output stimmt.
- **Prompts nicht gezeigt.** Er will sehen, welcher System-Prompt hinter jedem Agenten steckt — simpler
  Prompt oder Template mit Variablen?
- **Kontext-Nutzung unklar.** Telegram/Mail/Kalender wurden erwähnt, aber nicht klar, *was* genau daraus in
  den Plan einfließt und *wie* es gespeichert/gesucht wird.

## Der Kern: Paradigmenwechsel
- Weg von **Regeln / festem Workflow** (if/else, feste Reihenfolge) → hin zu **Agenten, die selbst
  entscheiden**, wann was passiert und welche Daten an welchen Agenten gehen.
- Man beschreibt nur noch Agenten (Funktionen, **Tools**, **System-Prompts**) — nicht mehr den Ablauf.
- **Wichtig:** Darf anfangs ruhig schlechter funktionieren als die Regel-Variante. Ziel des Kurses ist
  KI-Erfahrung, nicht ein perfektes regelbasiertes System.

## Rechnen vs. KI (wichtige Klarstellung)
- **LLMs rechnen schlecht.** Für Uhrzeiten/Routen/Budget → deterministisch (Regeln/Tools) bleiben.
- Alternative, die er nannte: das **LLM generiert ein kleines Code-Snippet**, das die Rechnung macht.
- Die spannende Aufgabe: diese **Grenze sauber herausarbeiten** — wo Regel, wo LLM, wo LLM-generierter Code.
- Für ein MVP/Demo dürfen einzelne Bausteine bewusst regelbasiert bleiben — er ist nicht dogmatisch.

## Seine Ideen für die Weiterentwicklung
- **Weniger Formular-Tippen, mehr Konversation.** Nutzer sagt nur „Ich hab Lust wegzukommen" → Agent legt
  selbst los: nutzt Telegram/Mail, Präferenzen, familiäre Situation (Kinder/Hund), Kontostand → macht
  proaktiv einen Vorschlag.
- **Proaktive Benachrichtigung im Chatbot:** „Du hattest am Wochenende Lust auf Paris — soll ich planen?"
  → Nutzer klickt nur Ja/Nein.
- **Iterativ verfeinern wie im Reisebüro:** „Das Restaurant kenne ich schon, gib mir ein anderes."
- **Formular bleibt trotzdem** — beide Modi kombinieren (Formular für „schnell mal abchecken").
- **Flug-Logik agentisch:** Statt „wenn Flugnummer eingegeben" soll der Agent **selbst entscheiden**, dass
  er die Flug-API aufruft (z.B. nur Starthafen wählen → Agent sucht den Flug + Daten selbst).

## Offene Fragen, die er gestellt hat (architektonisch zu beantworten)
- Werden Telegram-Nachrichten in einer **Vektordatenbank** gespeichert? Ein Dokument pro Nachricht oder alle
  zusammen? Wie wird eine Anfrage gegen alte Nachrichten **gematcht** (Retrieval/RAG)?

## Auftrag für nächste Präsentation
- **Alle Agenten vorstellen:** wie sie zusammenarbeiten, wann welcher aufgerufen wird, wie er arbeitet.
- **An einem Beispiel-Nutzerprompt** zeigen: Orchestrator entscheidet → Agent X → ruft Tool A, dann Tool B →
  leitet an Agent Y weiter — als **detailliertes Flowchart**.
- **Prompt-Template zeigen** (mindestens für einen komplexen Prompt).
- Er nimmt sich für nächste Woche ~5 Min mehr Zeit, evtl. auch **Blick in den Code**.

---
*Folgedokumente im Projekt:* [UMBAU_ERKLAERUNG_TEAM.md](../CW_27/UMBAU_ERKLAERUNG_TEAM.md) (verständlich) ·
[UMBAU_VORSCHLAG.md](../CW_27/UMBAU_VORSCHLAG.md) (technisch).
