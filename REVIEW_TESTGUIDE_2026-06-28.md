# Review- und Test-Leitfaden — Umbau vom 28. Juni 2026

*Diese Datei richtet sich an meine Teammitglieder, die den heutigen Umbau reviewen und testen. Sie ist bewusst als Fließtext geschrieben, damit genug Kontext da ist und nichts missverstanden werden kann. Jeder Abschnitt erklärt **was** gemacht wurde, **warum** es gemacht wurde, **welche Funktionalitäten betroffen** sind und **wie ihr es testen bzw. merken** könnt. Die zugehörigen technischen Details stehen im `CHANGELOG.md` unter dem Datum 28.06.2026.*

---

## Worum es bei dem ganzen Umbau geht

Bis heute war unser Reiseplanungs-Agent ein größtenteils regelbasiertes System: Aktivitäten wurden nach festen Regeln ausgewählt, Uhrzeiten mechanisch berechnet, Chat-Nachrichten über hunderte Zeilen Regex-Muster geroutet, und freie Tage im Kalender nur anhand eines selbstgesetzten Markers erkannt. Das funktionierte, war aber starr und wenig „intelligent". Der heutige Umbau führt an mehreren Stellen ein Large Language Model (LLM, über Groq) ein und ergänzt das System um ein Gedächtnis und um proaktives Verhalten. Wichtig zu verstehen: Es wurde bewusst darauf geachtet, **keine bestehenden Funktionssignaturen zu brechen** und alle alten Pfade als Fallback zu erhalten. Wenn also kein API-Key vorhanden ist oder das LLM ausfällt, läuft das System weiter wie vorher — nur eben weniger schlau. Das ist beim Testen wichtig: Viele neue Funktionen zeigen ihren vollen Effekt nur, wenn ein `GROQ_API_KEY` in der `.env` gesetzt ist.

Der Umbau ist in Phasen gegliedert (Phase 0 bis Phase 4). Jede Phase baut auf der vorherigen auf. Im Folgenden gehe ich sie der Reihe nach durch.

---

## Phase 0 — Zentrales `llm.py`, `prompts.py` und Trace-Logging

**Was wurde gemacht.** Vorher waren die Groq-Aufrufe an vier verschiedenen Stellen im Code verstreut, jeder mit eigenem Inline-Code. Das wurde zu einer einzigen zentralen Schnittstelle zusammengezogen: Die neue Datei `llm.py` enthält die Funktion `call(...)`, durch die ab jetzt **jeder** LLM-Aufruf läuft. Alle Prompt-Texte wurden in die neue Datei `prompts.py` als benannte Vorlagen ausgelagert. Zusätzlich gibt es jetzt einen „Trace" — eine Protokollierung, die bei jedem Planungs- oder Chat-Vorgang mitschreibt, welcher Agent was getan hat, und das sowohl im Terminal live ausgibt als auch im Ergebnis-Objekt mitliefert.

**Warum.** Einheitliches Logging, ein sichtbarer Ablauf pro Auftrag, und alle Prompts an einem Ort, wo man sie ohne Suchen findet und anpassen kann. Ohne diese Grundlage wären die späteren Phasen nicht sauber umsetzbar gewesen.

**Betroffene Funktionalität.** Tagesbrief, Navigations-Erinnerung, Freizeitvorschläge und die Chat-Antworten nutzen jetzt alle `llm.call`. Das Verhalten selbst sollte sich in Phase 0 **nicht** geändert haben — es ist ein reiner Umbau der „Verkabelung".

**Wie testen / merken.** Startet die App und löst irgendeinen Vorgang aus (z.B. eine Reise planen). Im Terminal sollten jetzt Trace-Zeilen erscheinen, etwa `[suggestion_agent] LLM → 312 Zeichen`. Wenn ihr den `GROQ_API_KEY` in der `.env` leert, dürfen die Aufrufe **nicht abstürzen**, sondern müssen sauber auf ihren alten Textbaustein zurückfallen.

---

## Phase 1 — LangGraph-Orchestrator für den Chat

**Was wurde gemacht.** Die Chat-Steuerung (`handle_chat_message`) wurde von einer riesigen Regex-Kette auf einen LangGraph-Graphen umgestellt. Statt mit Mustern zu raten, was der Nutzer will, entscheidet jetzt ein LLM per „Tool-Calling", welcher der bestehenden Handler ausgeführt wird (Zeit ändern, Tag neu planen, Aktivität löschen, Alternative vorschlagen, Kalender synchronisieren, Frage beantworten usw.). Die eigentlichen Handler-Funktionen wurden **nicht** verändert — sie werden nur anders aufgerufen.

**Warum.** Die Regex-Erkennung war fehleranfällig und schwer zu warten. Ein LLM versteht natürliche Formulierungen deutlich robuster.

**Betroffene Funktionalität.** Alles, was über den Chat läuft. Die Rückgabe-Struktur ist absichtlich identisch geblieben, damit Streamlit und die API unverändert weiterfunktionieren.

**Wie testen / merken.** Schickt im Chat verschiedene Formulierungen, z.B. „verschiebe das Abendessen auf 20 Uhr", „lösche an Tag 2 das Museum", „wie ist das Wetter?". Jede sollte beim richtigen Handler landen. Im Terminal seht ihr im Trace, welches Tool gewählt wurde, z.B. `[Orchestrator] → delete_activity`. Ohne API-Key muss der Chat trotzdem antworten (regelbasierter Fallback). Den kompletten Graphen könnt ihr euch übrigens als ASCII-Diagramm ausgeben lassen:

```bash
cd reiseagent
python -c "import sys; sys.path.insert(0,'.'); import graph; print(graph._compiled_graph.get_graph().draw_ascii())"
```

---

## Phase 2 — LLM-kuratierter Plan, Zeit-/Routen-Agent und semantische Dublettenerkennung

**Was wurde gemacht.** Drei Dinge. Erstens: Die Auswahl der Aktivitäten pro Tag wird jetzt vom LLM kuratiert, statt rein deterministisch zusammengestellt zu werden. Zweitens: Ein neuer Zeit-/Routen-Agent (`time_route_agent.py`) lässt das LLM realistische Uhrzeiten und Fahrtzeiten festlegen. Drittens: Die Orte-Quelle (`places.py`) erkennt jetzt Dubletten quellenübergreifend — wenn z.B. „Notre-Dame" aus zwei Quellen mit leicht unterschiedlichen Namen kommt, wird das als ein Ort erkannt (über Koordinaten-Nähe und Namens-Ähnlichkeit). Im selben Zug wurde der Kandidaten-Pool vergrößert und von zu strengen Filtern befreit (das ist der „Places-Fix" bzw. PHASE_B Teil 1 im Changelog).

**Warum.** Vorher tauchten Sehenswürdigkeiten doppelt auf, alle Aktivitäten waren 90 Minuten lang, und der Filter war so streng, dass dem LLM zu wenige gute Orte zur Auswahl blieben. Mit größerem Pool und LLM-Kuration werden die Pläne abwechslungsreicher und realistischer.

**Betroffene Funktionalität.** Die komplette Reiseplan-Erstellung — Auswahl, Reihenfolge, Uhrzeiten. Wichtig: Bei ungültiger LLM-Antwort gibt es einen einmaligen Reparatur-Versuch und danach den alten deterministischen Weg als Sicherheitsnetz.

**Wie testen / merken.** Plant eine Reise für eine bekannte Stadt (z.B. Paris, 3 Tage). Prüft, dass Sehenswürdigkeiten wie Notre-Dame oder der Louvre **nur einmal** im gesamten Plan vorkommen, dass jeder Tag etwa 4–5 Aktivitäten hat und dass Mittag- und Abendessen zu plausiblen Zeiten eingeplant sind (nicht um 9:15 Uhr). Die Dauer sollte je nach Kategorie variieren (Museum länger als Park).

---

## Phase 3 — Gedächtnis / RAG (semantisches Nutzergedächtnis)

**Was wurde gemacht.** Das System bekam ein Gedächtnis. Telegram-Nachrichten und E-Mails, die ohnehin schon eingelesen wurden, werden jetzt zusätzlich vollständig gespeichert — zusammen mit einem sogenannten Embedding, also einer mathematischen Darstellung ihres Inhalts. Die neue Datei `memory.py` kann zu einer beliebigen Anfrage (z.B. einem Reiseziel) die inhaltlich passendsten gespeicherten Nachrichten heraussuchen und dem Planungs-Prompt mitgeben. Dieses Prinzip heißt RAG (Retrieval-Augmented Generation): Bevor die KI plant, holt sie sich relevante Informationen aus dem Gedächtnis.

**Warum.** Vorher waren die Pläne völlig generisch — die KI wusste nichts über die Person. Mit dem Gedächtnis kann sie z.B. erkennen, dass jemand „mit den Kindern eher Museen" möchte, und den Plan entsprechend anpassen.

**Betroffene Funktionalität.** Die Reiseplan-Kuration (`planning.py`) und die Freizeitvorschläge (`suggestion_agent.py`) bekommen jetzt einen optionalen Kontextblock aus dem Gedächtnis. Ist das Gedächtnis leer oder passt nichts, wird der Block weggelassen und der Prompt bleibt wie vorher.

**Wie testen / merken.** Es ist eine neue Abhängigkeit dazugekommen (`sentence-transformers`), die beim ersten Aufruf einmalig ein Modell lädt — das dauert 5 bis 10 Sekunden, das ist normal und wird im Terminal angekündigt. Zum Testen kann man manuell eine Nachricht ins Gedächtnis legen und prüfen, ob sie zur passenden Anfrage als Top-Treffer zurückkommt:

```bash
cd reiseagent
python -c "import sys; sys.path.insert(0,'.'); import memory; memory.store_message('telegram','2026-06-28','Wir wollen mit den Kindern nach Paris, eher Museen'); print(memory.retrieve_context('Paris'))"
```

**Achtung beim Testen:** In der Datenbank liegen eventuell noch zwei Testnachrichten von der Entwicklung (Paris/Kinder und ein Jazz-Konzertticket). Wenn ein Vorschlag plötzlich von Kindern oder Paris spricht, kommt das daher — nicht aus hartkodiertem Code. Die Testdaten lassen sich löschen mit:

```bash
cd reiseagent
python -c "import sys; sys.path.insert(0,'.'); import sqlite3, profile_store; c=sqlite3.connect(profile_store.DB_PATH); c.execute('DELETE FROM messages'); c.commit(); print('Testdaten geloescht')"
```

---

## Phase 4 — Proaktiver Scheduler mit Telegram-Vorschlägen

**Was wurde gemacht.** Bis hierher war der Agent rein reaktiv — er handelte nur auf Anfrage. Phase 4 macht ihn proaktiv. Ein Hintergrund-Thread läuft einmal pro Woche (samstags), liest den Google-Kalender, lässt ein LLM (neuer `calendar_agent.py`) entscheiden, welche Tage wirklich frei sind, erstellt für diese Tage personalisierte Freizeitvorschläge und schickt sie per **Telegram** mit zwei Buttons — „✅ Ja, planen!" und „❌ Nein, danke" — an den Nutzer. Drückt der Nutzer Ja, wird automatisch ein vollständiger Tagesplan erstellt und ihm per Telegram zugeschickt. Drückt er Nein, wird der Vorschlag verworfen. Der Nutzer behält also die Kontrolle (Human-in-the-Loop), aber der erste Anstoß kommt vom System.

Wichtig für das Verständnis: Die Erkennung freier Tage ist jetzt deutlich klüger als vorher. Früher galt ein Tag nur dann als belegt, wenn das System selbst einen Marker hineingeschrieben hatte — ein echter Termin wie „Arbeit 8–17 Uhr" wurde komplett ignoriert. Jetzt liest das System alle Termine und lässt das LLM beurteilen, ob ein Tag frei, teilweise belegt oder belegt ist (kurze Termine wie Gym oder Arzt zählen weiterhin als planbar, Arbeit und ganztägige Ereignisse als belegt, Feiertage als frei).

Zusätzlich wurde in diesem Zug die Profil-Trennung umgesetzt: Automatisch erzeugte Vorschläge mischen die gelernten Profil-Interessen ein, **manuell** vom Nutzer erstellte Reisen jedoch nicht mehr — denn dort hat der Nutzer ja selbst angegeben, was er will. Technisch wird das über ein Feld `auto=True` im Request gesteuert.

**Warum.** Der Mehrwert eines Assistenten entsteht erst, wenn er mitdenkt, statt nur abzuarbeiten. Ein langes Wochenende soll erkannt und vorgeschlagen werden, ohne dass der Nutzer selbst daran denken muss.

**Betroffene Funktionalität.** Kalender-Anbindung (`calendar.py`, `free_time_detector.py`, neuer `calendar_agent.py`), der neue `scheduler.py`, der Telegram-Provider (neue Sende- und Empfangs-Logik) und `coordinator.handle_plan_request` (Profil-Trennung). Der bestehende Telegram-Flow für Flugverspätungen bleibt davon unberührt.

**Wie testen / merken.** Ihr müsst nicht bis Samstag warten. Es gibt einen manuellen Auslöser: Ruft im Swagger-UI (`http://localhost:8000/docs`) den Endpunkt **`POST /api/scheduler/run`** auf — damit läuft der komplette Ablauf sofort durch (Kalender lesen → LLM interpretieren → Vorschläge erstellen → per Telegram senden). Ist ein Telegram-Bot konfiguriert, erscheinen die Vorschläge mit Buttons in der Gruppe; drückt „Ja, planen!", und es sollte ein Plan erstellt und zurückgeschickt werden.

Zum reinen Prüfen der Kalender-Erkennung gibt es das Hilfsskript `test_calendar.py`. Es zeigt in vier Stufen: (1) die rohen Kalender-Einträge, (2) den exakten Text, den die KI bekommt, (3) das KI-Urteil pro Tag (frei/belegt mit Begründung) und (4) die am Ende übrig bleibenden freien Tage. So seht ihr transparent, was passiert:

```bash
cd reiseagent
python test_calendar.py
```

---

## Phase-4-Nachbesserungen (wichtig fürs Testen)

Beim ersten Testen von Phase 4 sind vier Fehler aufgefallen und wurden noch am selben Tag behoben. Ich beschreibe sie hier, weil ihr beim Review sonst über dieselben Stolperstellen fallen würdet.

**Erstens: Mehrtägige Kalender-Events.** Ein als Serie eingetragener Urlaub (z.B. 3.–5. Juli) wurde von Google als ein einziges Event geliefert und vom Code nur am Starttag erkannt — der 4. und 5. fehlten. Das ist jetzt gefixt: Solche Events werden in einen Eintrag pro Tag aufgespalten. **Ihr müsst Urlaubstage also nicht einzeln markieren.**

**Zweitens: Leere Tage waren für die KI unsichtbar.** Früher bekam das LLM nur Tage mit Terminen zu sehen, wodurch echte freie Tage (z.B. ein leeres Wochenende) gar nicht bewertet wurden. Jetzt wird jeder Tag im Zeitraum an die KI geschickt, auch die ohne Termin.

**Drittens: Das Testskript lud die `.env` nicht.** Dadurch war beim Testen kein `GROQ_API_KEY` gesetzt, der KI-Aufruf scheiterte still, und der Fallback markierte **alle** Tage als frei — auch Arbeitstage. Das war kein Logikfehler, sondern eine fehlende Konfiguration im Test. Wenn ihr im Test seht, dass jeder Tag mit der Begründung „Kein Termin" als frei gilt, dann läuft die KI nicht (Key fehlt). Das Skript lädt die `.env` jetzt selbst.

**Viertens: Der „Ja, planen!"-Button funktionierte nicht.** Ursprünglich war nur die Sende-Seite gebaut, nicht die Empfangs-Seite. Ein Klick lief in den alten Flug-Verspätungs-Handler, der Freizeitvorschläge nicht kennt, und meldete „Button nicht mehr gültig". Jetzt unterscheidet das System anhand eines Typ-Felds (`kind`) zwischen Flug-Vorschlägen und Freizeitvorschlägen und hat einen eigenen Handler, der bei „Ja" einen echten Plan erstellt und bei „Nein" den Vorschlag ablehnt.

**Zwei Einschränkungen, die ihr kennen solltet:** (a) Telegram-Buttons, die **vor** diesem Fix erzeugt wurden, bleiben ungültig — testet also nur mit Vorschlägen, die nach einem Server-Neustart neu erzeugt wurden. (b) Beim Drücken von „Ja" kann der Lade-Kreisel in Telegram kurz hängen, weil die KI erst den Plan baut; der Plan kommt aber zuverlässig an.

---

## Voraussetzungen und Stolperfallen beim Aufsetzen

Damit ihr nicht an Kleinigkeiten hängen bleibt, hier die wichtigsten Punkte gebündelt.

**Abhängigkeiten installieren.** Es sind neue Pakete dazugekommen (`langgraph`, `sentence-transformers`, `numpy`). Falls etwas fehlt:

```bash
cd reiseagent
pip install -r requirements.txt
```

**Aus dem richtigen Ordner starten.** Mehrere Module suchen ihre Dateien (Datenbanken, Google-Zugangsdaten) **relativ zum aktuellen Verzeichnis**. Startet die App daher immer aus dem Ordner `reiseagent/`, sonst werden Dateien am falschen Ort gesucht:

```bash
cd reiseagent
uvicorn main:app --reload        # Backend (Terminal 1)
streamlit run streamlit_app.py   # Oberfläche (Terminal 2)
```

**API-Key setzen.** Für den vollen Effekt der LLM-Funktionen muss ein `GROQ_API_KEY` in der `.env` (im Ordner `reiseagent/`) stehen. Ohne Key läuft alles weiter, aber auf den alten, regelbasierten Fallbacks — das ist beim Beurteilen der „Intelligenz" wichtig zu wissen.

**Google-Kalender (optional).** Die Kalender-Funktionen brauchen die Dateien `credentials.json` und `calendar_token.json` **im Ordner `reiseagent/`**. Liegen sie woanders (z.B. im Projekt-Hauptordner), werden sie nicht gefunden und der Kalender bleibt leer. Beim ersten Zugriff öffnet sich einmalig ein Browser-Fenster zur Google-Anmeldung. Ohne Kalender-Zugang stürzt nichts ab — es werden dann einfach keine Termine gelesen.

**Telegram (optional).** Für die Vorschlags-Buttons muss ein `TELEGRAM_BOT_TOKEN` gesetzt sein. Ohne Token werden die Vorschläge nur in der Datenbank gespeichert, aber nicht verschickt.

---

## Kurz-Checkliste für den Review

- App startet aus `reiseagent/` ohne Fehler, vier Hintergrund-Threads melden sich im Terminal (Monitoring, Navigation, Telegram-Callbacks, Scheduler).
- Eine Reise planen → Plan ist abwechslungsreich, keine doppelten Sehenswürdigkeiten, plausible Uhrzeiten, Essen mittags und abends.
- Chat mit verschiedenen Formulierungen → richtiger Handler, Trace im Terminal sichtbar.
- `python test_calendar.py` → KI stuft Arbeitstage als belegt und freie Tage als frei ein (nicht alles „frei"; falls doch, fehlt der API-Key).
- `POST /api/scheduler/run` → Vorschlag erscheint in Telegram, „Ja, planen!" erzeugt einen Plan.
- `GROQ_API_KEY` leeren → nichts stürzt ab, alles fällt sauber auf die alten Pfade zurück.
