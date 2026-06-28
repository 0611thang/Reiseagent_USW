

> Kurz-Spickzettel. 2026-06-23.

---

## 1. Was wir gerade verbessern: Planung & Ortsauswahl

**Einfach erklärt:** Heute wählt der Computer die Orte über eine **starre Punkte-Rechnung** aus.
Wir bauen das so um, dass eine **KI die Orte auswählt** — wie ein menschlicher Reiseführer.

### Vorher (regelbasiert)
```
OpenTripMap liefert Orte
   → Punkte-Rechnung mit festen Regeln
     (+60 für berühmte Namen, −80 für "schlechte" Wörter, +16 Museum …)
   → Orte mit zu wenig Punkten fallen raus
   → die übrigen werden stur der Reihe nach eingeplant
```
**Problem:** Die Rechnung misst „Denkmalwert", nicht „lohnt sich für Touristen".
→ Bei Rotterdam landeten **Postamt und Bankgebäude** im Plan, aber **Markthal und Euromast fehlten**.
Keine Feinjustierung der Regeln kann das beheben.

### Nachher (KI-gestützt / hybrid)
```
OpenTripMap liefert Orte
   → nur grober Müll-Filter (Parkplätze, Adressen raus)
   → ~50 saubere Kandidaten an die KI (LLM)
   → KI wählt die wirklich sehenswerten aus und ordnet sie sinnvoll auf die Tage
   → der Computer rechnet danach Uhrzeiten, Wege, Budget (das kann er besser)
```
**Warum:** Die KI hat **Weltwissen** — sie weiß, dass die Markthal sehenswert ist und ein Postamt nicht.
Der Computer bleibt für das **Rechnen** zuständig. Fällt die KI aus → automatischer Rückfall auf die alte Logik.

**Mehrwert / Innovation:** echte KI-Entscheidung statt starrer Regeln, mit Sicherheitsnetz.

---
