# Der Umbau — verständlich erklärt (für das Team)

> Diese Datei erklärt **in normaler Sprache**, was wir umbauen wollen und warum.
> Die technische Detail-Version mit Datei:Zeile-Verweisen steht in [UMBAU_VORSCHLAG.md](UMBAU_VORSCHLAG.md).
> Ziel hier: dass jeder im Team versteht, worum es geht — auch ohne tief im Code zu stecken.

---

## 1. Worum geht es überhaupt?

Der Professor hat in der Review-Session einen klaren Wunsch geäußert: Unser System soll sich **deutlich von
ChatGPT abheben**. Aktuell merkt man nicht, dass im Hintergrund echte Agenten arbeiten — es wirkt, als würde
man einfach Wünsche eintippen und einen Plan zurückbekommen. Genau das könnte man mit ChatGPT auch.

Sein zweiter, größerer Punkt: **Paradigmenwechsel.** Früher hat man Software gebaut, indem man *Regeln* und
einen *festen Ablauf* definiert hat („wenn X, dann Y"). Die neue Art, KI-Systeme zu bauen, ist anders: Man
beschreibt **Agenten** (kleine Spezialisten mit Aufgaben und Werkzeugen) und lässt sie **selbst entscheiden**,
wann was passiert. Das ist genau die Erfahrung, die wir im Modul sammeln sollen.

**Kurz:** Wir gehen von einem starren Automaten zu einem mitdenkenden Assistenten.

---

## 2. Die Kernidee in einem Bild

**Heute ist unser System wie ein Getränkeautomat:**
Es hat feste Knöpfe in fester Reihenfolge. Du drückst genau die Knöpfe, die es gibt, und bekommst genau das,
was fest verdrahtet ist. Im Code heißt das: `coordinator.py` arbeitet eine feste Liste ab
(Wetter → Orte → Plan → Budget → Checkliste), und der Chat erkennt deine Sätze über hunderte starre
Stichwort-Regeln.

**Nachher soll es wie ein persönlicher Reiseberater sein:**
Du sagst, was du willst — und der Berater entscheidet selbst, wen er anruft: das Wetter-Büro, den
Karten-Dienst, die Fluggesellschaft. Er kennt dich (deine früheren Nachrichten, deinen Kalender, dein
Budget) und macht dir von sich aus einen Vorschlag. Wenn dir etwas nicht passt, verbesserst du es im Gespräch
— wie in einem echten Reisebüro.

---

## 3. Was heute konkret schiefläuft

Vier Dinge, die der Umbau lösen muss:

**a) Der Chat ist gar keine KI.**
Was wie ein KI-Chat aussieht, sind in Wirklichkeit ~1300 Zeilen Stichwort-Regeln. Das LLM (die eigentliche
KI) darf nur antworten, wenn nichts anderes passt — und selbst dann kann es den Plan nicht verändern. Es
plaudert nur. Die Arbeit machen die Regeln.

**b) Niemand entscheidet — alles ist fest verdrahtet.**
Die Reihenfolge der Schritte steht starr im Code. Kein Agent überlegt „was brauche ich jetzt?". Das ist das
Gegenteil von dem, was der Professor will.

**c) Qualitätsfehler wie „Notre-Dame doppelt".**
Der Professor hat in der Demo gesehen, dass ein Ort doppelt im Plan stand. Ursache: Unsere Doppel-Prüfung
vergleicht nur **exakt gleiche Namen**. „Notre-Dame Cathedral" und „Cathédrale Notre-Dame" gelten als zwei
verschiedene Orte — also rutschen beide rein. Es fehlt eine **Endkontrolle**, die den fertigen Plan prüft.

**d) Der Kontext (Telegram, Mail, Kalender) wird kaum genutzt.**
Genau das wäre unser Alleinstellungsmerkmal gegenüber ChatGPT — aber heute werden Nachrichten nur kurz nach
Stichworten durchsucht und dann **weggeworfen**. Nichts wird gespeichert, nichts wird wirklich „erinnert".

---

## 4. Wie es nachher funktioniert — am Beispiel

Stell dir vor, du tippst in den Chat: **„Ich hab Lust, mal wegzukommen."**

So läuft es im neuen System ab:

1. Der **Orchestrator** (der Chef-Agent) liest deinen Satz und überlegt: „Was brauche ich, um das zu
   beantworten?" — und entscheidet **selbst**, welche Werkzeuge er nacheinander benutzt.
2. Er ruft das **Gedächtnis** ab → findet: „In Telegram hattest du Lust auf Paris" und „aus einer Mail: die
   Kinder sind im Urlaub dabei".
3. Er prüft deinen **Kalender** → das Wochenende ist frei.
4. Er prüft das **Budget** → 400 € verfügbar.
5. Er holt **Sehenswürdigkeiten** für Paris und das **Wetter** fürs Wochenende.
6. Der **Planungs-Agent** (KI) wählt daraus die wirklich sehenswerten Orte aus und verteilt sie sinnvoll auf
   die Tage — am Regentag eher Indoor.
7. Eine **Qualitäts-Kontrolle** prüft: Sind alle Orte gültig? Kommt keiner doppelt vor? Erst dann rechnet der
   Computer die genauen Uhrzeiten, Wege und Kosten aus.
8. Du bekommst eine Karte im Chat: *„Paris, Samstag–Sonntag, kinderfreundlich, im Budget — soll ich den Plan
   erstellen? [Ja] / [Nein]"*. Ein Klick genügt.

**Das kann ChatGPT nicht:** Es kennt deinen Kalender nicht, liest deine Telegram-Nachrichten nicht, weiß
nichts von deinem Budget und ruft keine echten Flug-/Karten-Dienste auf. Genau dieser orchestrierte Ablauf
ist unser Mehrwert — und den machen wir im Umbau **sichtbar**.

---

## 5. Die wichtigsten Begriffe — kurz erklärt

**Agent.** Ein kleiner Spezialist mit einer Aufgabe, eigenen Werkzeugen und einer eigenen „Arbeitsanweisung"
(System-Prompt). Beispiel: der Planungs-Agent wählt Orte aus.

**Tool-Calling (Werkzeug-Aufruf).** Der Chef-Agent hat sozusagen eine Kontaktliste (Wetter, Karten, Flüge,
Gedächtnis …) und **entscheidet selbst**, wen er anruft und in welcher Reihenfolge. Das ist der technische
Kern von „Agent entscheidet selbst".

**Qualitäts-Gate (Endkontrolle pro Agent).** Jeder Agent prüft sein eigenes Ergebnis, bevor es weitergeht —
wie ein Korrektor. Beispiel: „Steht ein Ort doppelt drin? Dann verwerfen und neu machen." Das verhindert den
„Notre-Dame doppelt"-Fehler.

**Gedächtnis / RAG.** Das System merkt sich deine Nachrichten (eine pro Eintrag, gespeichert) und holt bei
einer Anfrage die **passenden** wieder hervor — wie ein Berater, der in seinen Notizen blättert. Wir starten
einfach (Stichwort + Aktualität) und können später auf „echtes" semantisches Suchen (Vektor-Datenbank)
ausbauen.

**Deterministisch vs. KI — wer macht was?**
Das ist eine zentrale Aussage des Professors: *LLMs können nicht gut rechnen.* Deshalb teilen wir die Arbeit:
- Die **KI entscheidet und wählt aus** (welche Orte sind schön, in welcher Reihenfolge) — dafür braucht man
  Geschmack und Weltwissen.
- Der **normale Code rechnet** (Uhrzeiten, Fahrtzeiten, Budget) — das muss exakt sein.
- Der Berater hat also **guten Geschmack**, benutzt für die Rechnung aber einen **Taschenrechner**.

---

## 6. Was sich für den Nutzer ändert

- **Das Formular bleibt.** Wer schnell „nur mal checken" will, wie ein Berlin-Trip aussähe, tippt weiter ins
  Formular. (Das war ein ausdrücklicher Wunsch des Professors.)
- **Neu: der Gesprächs-Modus.** Man kann einfach lostippen („Ich will übers Wochenende weg") und das System
  legt los.
- **Neu: proaktive Vorschläge.** Das System erkennt freie Wochenenden und meldet sich von selbst:
  „Du hattest Lust auf Paris — soll ich planen?"
- **Neu: Verfeinern wie im Reisebüro.** „Das Restaurant kenne ich schon, gib mir ein anderes" — und es
  tauscht gezielt aus.

---

## 7. Was bleibt — und was wir schützen müssen

Damit beim Umbau nichts kaputtgeht, bleiben alle **funktionierenden Features** erhalten: gespeicherte Reisen,
Kalender-Synchronisation, Flug-Anpassung, die verschiedenen Tagesplan-Ansichten. Es gibt ein paar zentrale
Funktionen im Code, die viele andere Stellen benutzen — die fassen wir vorsichtig an, damit nichts unbemerkt
bricht (Details in UMBAU_VORSCHLAG.md, Abschnitt 9). Und: **A3 Telegram nicht anfassen.**

---

## 8. Der Fahrplan (was zuerst, was später)

Wir bauen **schrittweise** um, damit das System immer lauffähig bleibt:

| Schritt | Was passiert | Für die nächste Präsentation? |
|---|---|---|
| **0. Fundament** | Eine zentrale Stelle für alle KI-Aufrufe + sichtbare Prompt-Vorlagen + Mitschrift, was die Agenten tun. | **Ja** — liefert genau die Prompt-Vorlagen und das Flowchart, das der Prof sehen will |
| **1. Chat wird agentisch** | Die Stichwort-Regeln werden durch echtes Tool-Calling ersetzt. | **Ja** — der sichtbare „Wow, es entscheidet selbst"-Moment |
| **2. Bessere Orte + Endkontrolle** | KI wählt Orte aus, Doppel-Einträge werden verhindert. | Wenn Zeit reicht |
| **3. Gedächtnis** | Telegram/Mail werden gespeichert und in die Planung einbezogen. | optional |
| **4. Proaktiv** | System schlägt von selbst Reisen vor, automatisch zeitgesteuert. | optional |
| **5. Später** | Flugsuche per Agenten-Entscheidung, Finanzmodell, Lernen aus Feedback. | nein |

**Für nächste Woche reichen Schritt 0 + 1** — das bringt den größten sichtbaren Sprung („agentisch") und
genau die Artefakte (Prompt-Vorlagen, Flowchart), die der Professor verlangt hat, bei überschaubarem Risiko.

---

## 9. Was wir als Team entscheiden müssen

Bevor es losgeht, sollten wir ein paar Fragen gemeinsam klären (ausführlich in UMBAU_VORSCHLAG.md,
Abschnitt 10). Die zwei wichtigsten:

1. **Wie „groß" für nächste Woche?** Reicht Schritt 0 + 1 für die Präsentation, oder wollen wir auch den
   „Notre-Dame"-Fix (Schritt 2) unbedingt zeigen?
2. **Gedächtnis: einfach oder mit Vektor-Datenbank?** Der Professor hat nach Vektor-Datenbank/RAG gefragt.
   Wollen wir das schlicht halten (Stichwort + Aktualität) oder bewusst die „große" Variante bauen und zeigen,
   um Punkte zu sammeln?

Weitere offene Punkte: Bauen wir mit der schlanken Plain-Python-Variante oder mit einem Framework
(LangGraph)? Vereinheitlichen wir Streamlit und die API? — Diese können wir im Team-Meeting durchgehen.

---

## 10. Das Wichtigste in drei Sätzen

Wir bauen unser Reise-System von **festen Regeln** zu **selbst entscheidenden Agenten** um, die unseren
Kontext (Telegram, Mail, Kalender, Budget) kennen und proaktiv Vorschläge machen — klar unterscheidbar von
ChatGPT. Jeder Agent **prüft seine eigene Qualität** (kein doppeltes Notre-Dame mehr), und das **Rechnen
bleibt beim normalen Code**, während die **KI auswählt und entscheidet**. Für die nächste Präsentation
zeigen wir den agentischen Chat, die sichtbaren Prompt-Vorlagen und ein Flowchart, das nachvollziehbar macht,
was „unter der Motorhaube" passiert.
