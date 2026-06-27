# Zukunfts-Notizen — Was wir noch vorhaben (nicht vergessen!)

> Dieses Dokument hält Ideen und geplante Features fest, die wir **jetzt nicht implementieren**,
> aber **später unbedingt einbauen wollen**. Ergänzt nach Session 2026-06-23.

---

## 1. Automatische Reiseerstellung via Kalender-Erkennung

**Idee:** Das System soll selbst erkennen, wann der User Freizeit hat (z.B. 3 freie Tage im Kalender), und ihm dann automatisch einen Reisevorschlag anbieten.

**Wie es funktionieren soll:**
- Kalender-Integration liest freie Zeitblöcke (z.B. 3+ Tage ohne Termine)
- System triggert automatisch eine Reisegenerierung
- Vorschlag wird dem User präsentiert (nicht einfach aktiviert) — er kann annehmen oder ablehnen
- Idee aus Leitprinzip: **„Proaktiv statt reaktiv"** (siehe ZIELARCHITEKTUR.md)

**Was dafür noch fehlt:**
- Kalender-Leselogik die Freizeitfenster erkennt
- Trigger-Mechanismus der die Reisegenerierung anstößt
- UI um Vorschläge anzuzeigen und anzunehmen/abzulehnen

---

## 2. Profil-Interessen-Trennung: Manuell vs. Auto-Trip (Code-Änderung)

**Was:** `coordinator.py` (Zeile 37–47) merged aktuell Profil-Interessen automatisch in **jede** Reise,
auch manuell erstellte. Laut Design soll das nur bei automatisch generierten Reisevorschlägen (Kalender-Trigger) passieren.

**Wo im Code:** `coordinator.py`, Funktion `handle_plan_request`, Block `profile_labels` / `merged_interests`.

**Was zu ändern:** Profil-Interessen nur einmergen wenn der `request` ein Flag wie `"auto_generated": True` trägt.
Manuelle Reisen (User gibt Interessen selbst ein) sollen das Profil **nicht** automatisch übernehmen.

**Wann:** Im späteren Profil-Feature implementieren — **nicht** in Phase B.

---

## 4. Nutzerprofil-Fragebogen (Onboarding)

**Idee:** Beim ersten Start (oder auf Wunsch) füllt der User einen Fragebogen aus. Die Antworten bilden sein Profil und fließen in automatische Reisevorschläge ein.

**Mögliche Fragen:**
- Welche Art von Urlaub bevorzugst du? (Kultur / Abenteuer / Entspannung / Städtetrip / Natur)
- Welche Küche bevorzugst du? (Lokale Landesküche / Asiatisch / Mediterran / Fast Food / Vegetarisch / Gemischt)
- Wie aktiv bist du im Urlaub? (Viel laufen & erkunden / Gemütlich / Lieber gemischt)
- Reisst du lieber allein, als Paar, mit Familie oder Gruppe?
- Was ist dir besonders wichtig? (Günstig / Komfort / Exklusiv / Spontan)

**Wichtig — Abgrenzung zur manuellen Reiseerstellung:**
> Bei **manuell erstellten Reisen** gibt der User seine Interessen **selbst ein** (Museen, Sehenswürdigkeiten, Essen, Natur, Shopping). Das Profil wird dabei **NICHT automatisch übernommen**.
>
> Das Profil-System greift **NUR** bei automatisch generierten Reisevorschlägen (Kalender-Trigger, siehe Punkt 1).

---

## 5. Budget-Integration via Kontomodell / Finanzmodell

**Idee:** Das System soll das tatsächliche Budget des Users kennen — nicht nur das manuell eingegebene Reisebudget, sondern das verfügbare Geld aus einem verknüpften Konto oder Finanzmodell.

**Wie es funktionieren soll (Vision aus Zielarchitektur):**
- Verknüpfung mit Konto-/Finanzdaten (z.B. monatlich verfügbares Budget)
- Automatische Reisevorschläge passen das Budget realistisch an
- Möglichkeit: „Bis Ende Monat hast du noch X € übrig — hier ein Wochenendtrip dafür"

**Was dafür noch fehlt:**
- Kontomodell/Finanzmodell muss erst entwickelt werden
- Datenschutz-Überlegungen
- Ist im Zielarchitektur-Dokument (ZIELARCHITEKTUR.md) bereits angedacht

---

## 4. Was in dieser Session entschieden wurde (Erinnerung)

- **City Highlights löschen**: Die hardcodierte `CITY_HIGHLIGHTS`-Liste in `places.py` soll komplett entfernt werden. Nur OpenTripMap als Datenquelle.
- **Essen immer dabei**: `_category_allowed_by_interests` in `places.py` soll für `food` immer `True` zurückgeben — Restaurants werden nie mehr blockiert, egal welche Interessen angegeben sind.
- **Pool-Erschöpfung bei langen Trips**: Bei sehr langen Reisen (z.B. 11 Tage Rotterdam) werden alle Kandidaten verbraucht. Lösung: `used_ids` bei Erschöpfung lockern, damit beliebte Orte mit Mindestabstand wiederholt werden dürfen.
- **Quality Score degradieren statt tunen**: Echte Daten-Analyse (Rotterdam) hat gezeigt: OpenTripMaps `rate`-Feld misst *denkmalgeschützte/architektonische Bedeutung*, NICHT *touristische Sehenswürdigkeit*. Bei `rate=7` standen Postamt, Bankgebäude, Kaufhaus — während Markthal, Euromast, Kubushäuser fehlten. Kein Tuning der Magic Numbers kann das beheben, weil das Eingangssignal „sehenswert" gar nicht ausdrücken kann.
  - **Entscheidung:** `quality_score` wird vom „Haupt-Richter" zum dünnen **Müll-Vorfilter** degradiert (nur offensichtlichen Müll raus: kein Name, Adresse-als-Name, keine Koordinaten, kinds in Blockliste wie parking/hotels/offices). Kein Magic-Number-Ranking mehr. Die eigentliche Qualitätsbewertung („was ist wirklich sehenswert") übernimmt das **LLM** (Phase B).
  - **Tote Signale belegt:** `wikipedia` ist in der Radius-Antwort bei 0/50 vorhanden (der +10-Bonus feuert nie). `wikidata` bei 50/50 (der +6-Bonus ist eine Konstante, unterscheidet nichts).
  - **Geocoding ist OK:** Code nutzt Nominatim (nicht OpenTripMap-Geoname) → korrektes Rotterdam-Zentrum. Kein Fix nötig.
  - **Nachschub ist OK:** Mit korrektem Zentrum + allen kinds liefert die API ~104 eindeutige Orte. Die Knappheit entsteht erst durch unsere Filter.

---

## 5. Phase B — LLM-Prompt Design (für Implementierung)

- **Modell:** `llama-3.3-70b-versatile` via Groq (Meta LLaMA 3.3, 70 Mrd. Parameter, 128k Kontext). Groq = nur schnelle Inferenz-Hardware, nicht das Modell selbst. Reicht für die Müll-Kuratierung, weil das LLM nur Weltwissen über Ortskategorien braucht, kein aktuelles Wissen — die Orte kommen ja als Input.
- **Prompt-Sprache: ENGLISCH.** Das Modell ist primär auf Englisch trainiert → bestere Ergebnisse. **Ortsnamen werden so übergeben wie sie von OpenTripMap kommen** (nicht übersetzen, nicht normalisieren — z.B. „Lijnbaan", „Het Schielandshuis" bleiben original).
- **Trip-Dauer geht in den Prompt.** Das LLM bekommt die Anzahl Tage und entscheidet **selbst**:
  - wie viele der ~50 Kandidaten es insgesamt braucht (über die Dauer verteilt),
  - wie viele Aktivitäten pro Tag sinnvoll sind (kein „4 Museen am Stück"),
  - den Tagesrhythmus: Vormittag Sightseeing → Mittag Essen → Nachmittag → Abend Essen.
- **Ein Aufruf für den ganzen Trip** (nicht pro Tag): Input = ~50 Kandidaten (Name + kinds) + Dauer + Interessen + Wetter pro Tag. Output = pro Tag eine Liste von Orts-IDs in Reihenfolge. Vorteil: löst Pool-Erschöpfung elegant, kohärenter über alle Tage, billiger.
- **Arbeitsteilung bleibt strikt:** LLM = WELCHE Orte, WIE VIELE, REIHENFOLGE/Gruppierung pro Tag. **Python = genaue Uhrzeiten, Fahrtzeiten, Budget.** Das LLM rechnet nie.
- **Validierung in Python:** alle zurückgegebenen IDs müssen aus dem Input-Set stammen; bei Halluzination / fehlendem Key → **Fallback auf Phase A** (deterministisch).

---

## 6. Nachschub-Decke bei langen Trips (späteres Feature)

Auch das beste LLM kann keine 11 Tage Programm aus einer 2–3-Tage-Stadt machen. Rotterdam hat schlicht nicht genug echte Sehenswürdigkeiten in 8 km Umkreis.
- **Kurzfristig (Phase B):** LLM soll lange Trips elegant handhaben — entspannte Tage, „Tag frei für Spontanes", Wiederbesuche von Highlights mit Mindestabstand. Keine erfundenen Orte halluzinieren.
- **Später:** **Tagesausflüge in Nachbarstädte** (z.B. Rotterdam → Delft, Den Haag, Kinderdijk). Erfordert, dass das Kandidaten-Set geografisch über die Zielstadt hinaus erweitert wird. Heute auf die Zielstadt begrenzt.

---

*Erstellt: 2026-06-23*
