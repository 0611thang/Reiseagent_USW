# Phase 3 erklärt — Memory und RAG

*Geschrieben für jemanden, der den bisherigen Code nicht kennt.*

---

## Was das System bisher macht (Kurzüberblick)

Unser System ist ein Reiseplanungs-Agent. Der Nutzer gibt an, wohin er reisen möchte und für wie viele Tage, und das System erstellt automatisch einen detaillierten Tagesplan mit Aktivitäten, Uhrzeiten und Routen. Dafür holt es sich Orte aus der Google Places API, bewertet sie, wählt die besten aus und schickt dann alles an ein KI-Modell (Claude), das daraus einen sinnvollen, abwechslungsreichen Plan zusammenstellt.

Zusätzlich liest das System bereits heute Telegram-Nachrichten und Gmail-E-Mails des Nutzers. Es erkennt dabei Schlüsselwörter — zum Beispiel: wenn der Nutzer eine E-Mail mit „Konzertticket" oder „Restaurantbuchung" bekommt, merkt sich das System, dass der Nutzer Interesse an Musik oder gutem Essen hat. Diese gelernten Interessen werden in einer SQLite-Datenbank (`profile.db`) gespeichert.

Das Problem ist: diese gespeicherten Informationen werden beim Planen **noch nicht benutzt**. Die KI weiß nichts davon. Sie bekommt nur das Reiseziel, die Dauer, das Wetter und eine Liste möglicher Aktivitäten — aber keinen einzigen Satz darüber, wer der Nutzer eigentlich ist und was ihm wichtig ist.

---

## Was Phase 3 ändert — die Grundidee

Phase 3 gibt dem System ein **Gedächtnis**. Konkret bedeutet das: Die Telegram-Nachrichten und E-Mails, die das System bisher schon einliest, werden ab jetzt nicht nur auf Schlüsselwörter untersucht, sondern vollständig gespeichert — zusammen mit einem sogenannten **Embedding**.

Ein Embedding ist eine mathematische Darstellung des Inhalts einer Nachricht. Man kann sich das vorstellen wie einen „Fingerabdruck" des Textes in Form von Zahlen. Der Witz dabei: Wenn zwei Texte inhaltlich ähnlich sind — zum Beispiel „wir möchten mit den Kindern ins Museum" und „Paris Kunstausstellung" — dann liegen ihre Fingerabdrücke auch mathematisch nah beieinander. Das erlaubt es, zu einer beliebigen Frage oder einem beliebigen Reiseziel die **thematisch passendsten** gespeicherten Nachrichten herauszusuchen.

Dieser Ansatz heißt in der Informatik **RAG — Retrieval-Augmented Generation**. Das bedeutet: Bevor die KI etwas generiert (den Reiseplan), holt man sich zuerst relevante Informationen aus einem Speicher (Retrieval) und fügt sie dem Prompt hinzu, damit die KI besser informiert antworten kann (Augmented Generation).

---

## Warum das sinnvoll ist — ein konkretes Beispiel

Stell dir vor, der Nutzer hat letzte Woche eine Nachricht in Telegram geschrieben: „Wir fahren mit den Kindern nach Paris, am liebsten Museen und kein Shopping." Diese Nachricht liegt in der Datenbank. Jetzt plant der Nutzer eine neue Reise nach Paris.

**Ohne Phase 3:** Die KI bekommt nur „Reiseziel: Paris, 3 Tage" und wählt irgendwas Vernünftiges aus — vielleicht den Eiffelturm, einen Shoppingbummel auf den Champs-Élysées und ein gutes Restaurant. Das ist korrekt, aber völlig unpersönlich.

**Mit Phase 3:** Bevor die KI den Prompt bekommt, sucht das System in der Datenbank nach Nachrichten, die inhaltlich zu „Paris" passen. Es findet die alte Telegram-Nachricht. Diese wird am Ende des Prompts eingefügt: „Nutzer-Kontext: Wir fahren mit den Kindern nach Paris, am liebsten Museen und kein Shopping." Die KI sieht das, und plant entsprechend: mehr Museen, keine Shopping-Aktivitäten, kinderfreundliche Optionen.

Das ist der gesamte Sinn von Phase 3. Nicht mehr und nicht weniger.

---

## Was technisch gebaut werden muss

Es gibt vier Bereiche, in denen Code hinzukommt oder geändert wird.

**1. Eine neue Datenbank-Tabelle**

In `profile_store.py` wird eine neue Tabelle `messages` angelegt. Jede Zeile enthält eine gespeicherte Nachricht (Text, Quelle, Datum) und ihr Embedding (eine Liste von Zahlen, die den Inhalt mathematisch beschreibt). Diese Tabelle ist der eigentliche „Langzeitspeicher" des Systems.

**2. Eine neue Datei: `memory.py`**

Diese Datei hat zwei Aufgaben. Erstens: `store_message(source, date, text)` — wenn eine neue Nachricht reinkommt, wird sie mit ihrem Embedding in der Datenbank gespeichert. Zweitens: `retrieve_context(query, k=4)` — wenn das System einen Plan erstellt und ein Reiseziel kennt, ruft es diese Funktion auf. Sie berechnet den Fingerabdruck des Reiseziels und vergleicht ihn mit allen gespeicherten Nachrichten. Die vier ähnlichsten Nachrichten werden zurückgegeben.

Das Embedding-Modell selbst ist eine fertige Bibliothek (`sentence-transformers`), die man einfach installiert. Man gibt ihr einen Text, sie gibt einem eine Liste von Zahlen zurück. Den Vergleich zwischen zwei solchen Zahlenlisten (Cosine-Ähnlichkeit) rechnet das System selbst mit `numpy` aus — das sind ein paar Zeilen Code.

**3. Nachrichten beim Einlesen zusätzlich speichern**

In `profile_learner.py` gibt es bereits Funktionen, die Telegram-Nachrichten und E-Mails verarbeiten — sie suchen nach Schlüsselwörtern und speichern Interessen. Diese Funktionen werden jetzt um einen einzigen zusätzlichen Aufruf erweitert: `memory.store_message(...)`. Das heißt: jede eingelesene Nachricht landet ab jetzt auch im Langzeitspeicher.

Wichtig: Das wird **nur hier** gemacht, nicht in `telegram.py` oder `gmail.py`. Diese Dateien sollen unberührt bleiben.

**4. Den Reiseplan-Prompt mit Kontext anreichern**

In `planning.py` und `suggestion_agent.py` — das sind die Funktionen, die den eigentlichen Reiseplan und Freizeitvorschläge erstellen — wird vor dem Aufrufen der KI `retrieve_context(reiseziel)` aufgerufen. Der zurückgegebene Text wird in den Prompt eingebaut. Der Prompt-Template in `prompts.py` bekommt dafür am Ende einen optionalen Block: `"Nutzer-Kontext (aus Nachrichten): {context}"`. Falls das System noch keine passenden Nachrichten kennt (Datenbank leer oder kein Treffer), wird dieser Block einfach weggelassen — der Prompt bleibt dann exakt so wie bisher.

---

## Was man beachten muss

Das Embedding-Modell muss beim ersten Start geladen werden. Das dauert einmalig 5–10 Sekunden — danach ist es im Speicher und läuft schnell. Im Terminal sieht man eine kurze Meldung dazu.

Die Datenbank wächst mit der Zeit, weil jede Nachricht drin bleibt. Das ist bei normaler Nutzung kein Problem, aber man könnte optional ältere Einträge löschen, wenn mehr als z.B. 500 Nachrichten gespeichert sind.

Wenn der Kontext-Block leer ist — weil noch keine Nachrichten gespeichert sind oder keine zur Anfrage passen — darf er nicht als leerer String in den Prompt. Das würde die KI verwirren. Stattdessen wird er vollständig weggelassen.

---

## Zusammenfassung in einem Satz

Phase 3 gibt dem System ein Gedächtnis, das Nachrichten des Nutzers inhaltlich versteht und bei der Reiseplanung automatisch die passenden Informationen heraussucht und der KI mitgibt — damit der Plan nicht generisch ist, sondern zur konkreten Person passt.
