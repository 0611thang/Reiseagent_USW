# Systemarchitektur — Erklärung für Teammitglieder

*Dieses Dokument beschreibt in Prosa, wie unser Reiseplanungs-Agent funktioniert, warum er so aufgebaut ist und in welche Richtung er sich entwickeln soll. Es richtet sich an alle Teammitglieder, die ein vollständiges Verständnis des Systems brauchen, bevor sie an ihm weiterarbeiten. Die technische Übersicht mit allen Details findet sich in `ZIELARCHITEKTUR.md`; dieses Dokument legt den Fokus auf Kontext und Verständnis.*

---

## Die Grundidee: Von reaktiv zu proaktiv

Klassische Reiseplaner warten auf eine Eingabe. Der Nutzer tippt „Ich möchte nach Barcelona reisen" und bekommt einen Plan. Unser Agent soll das nicht sein. Er soll sich mehr wie ein persönlicher Assistent verhalten, der mitdenkt, beobachtet und von sich aus aktiv wird — ähnlich wie ein guter Freund, der weiß: Du hast nächstes Wochenende frei, du magst Museen und Essen gehen, und dein Budget erlaubt gerade einen Kurztrip. Also schreibt er dir: „Hey, wie wäre es mit einem Wochenende in Hamburg?"

Dieses Prinzip — proaktiv statt reaktiv — ist der Kern des gesamten Systems. Es bedeutet, dass der Agent nicht wartet, bis der Nutzer etwas fragt. Er beobachtet ständig: Was steht im Kalender? Wie ist das Wetter am Reiseziel? Hat der Flug Verspätung? Was interessiert den Nutzer, basierend auf seinen Nachrichten und vergangenen Erfahrungen? Und er verbindet diese Informationen zu konkreten Vorschlägen, die der Nutzer dann nur noch bestätigen oder ablehnen muss.

---

## Wie das System gestartet wird

Es gibt drei Wege, wie das System aktiv werden kann.

Der erste ist der klassische Weg: Der Nutzer stellt aktiv eine Anfrage. Er möchte eine Reise planen und gibt Ziel, Daten, Budget und seine Interessen an. Das System verarbeitet diese Anfrage und erstellt einen personalisierten Reiseplan.

Der zweite Weg ist automatisch. Das System schaut regelmäßig in den Kalender des Nutzers und sucht nach freien Zeitfenstern. Findet es beispielsweise, dass Freitag und Samstag frei sind, aber Sonntag wieder ein Termin ansteht, denkt es aktiv mit: Es schlägt keinen Wochenendtrip mit Rückreise am Sonntagabend vor, sondern berücksichtigt den Termin und empfiehlt einen Kurztrip bis Samstag 18 Uhr, damit der Nutzer rechtzeitig zu Hause ist.

Der dritte Weg ist zeitgesteuert. Im Hintergrund läuft ein Scheduler, der bestimmte Aufgaben regelmäßig — stündlich oder täglich — ausführt. Morgens wird ein Tagesbrief für den Reisetag generiert, stündlich werden Wetter und Flugstatus geprüft, täglich werden neue Nachrichten ausgewertet, um das Nutzerprofil aktuell zu halten.

---

## Wie die Agenten zusammenarbeiten

Das System besteht aus mehreren spezialisierten Agenten, die über einen gemeinsamen Workflow miteinander kommunizieren. Dieser Workflow wird mit LangGraph organisiert — einem Framework, das den Ablauf als einen expliziten Graphen beschreibt, durch den ein gemeinsamer Zustand fließt. Jeder Agent ist ein Knoten in diesem Graphen. Er empfängt den aktuellen Zustand, bereichert ihn mit seinen Ergebnissen und gibt ihn weiter. Welcher Agent als nächstes aktiv wird, hängt von Bedingungen ab — so kann beispielsweise der Monitoring-Agent den Replanning-Agent auslösen, aber nur dann, wenn er tatsächlich ein kritisches Ereignis erkannt hat.

Dieses Modell macht das System wartbar und erweiterbar: Ein neuer Agent ist ein neuer Knoten. Eine neue Bedingung ist eine neue Kante. Der gesamte Ablauf ist jederzeit nachvollziehbar.

---

## Die einzelnen Agenten und ihre Rollen

**Der Planning-Agent** ist der Kern der Reiseerstellung. Er nimmt die Anfrage des Nutzers entgegen — Ziel, Daten, Budget, Interessen — und erzeugt daraus einen vollständigen Tagesplan. Dabei fragt er aktiv externe Quellen ab: Er holt Wetterdaten für den Reisezeitraum, sucht passende Aktivitäten und Restaurants über eine POI-API und berücksichtigt das Profil des Nutzers, um die Empfehlungen zu personalisieren. Die eigentliche Entscheidung, welche Aktivitäten an welchem Tag und zu welcher Zeit passen, übernimmt ein Sprachmodell. Es versteht den Kontext — „Outdoor-Aktivitäten am Nachmittag, aber es ist bewölkt" oder „der Nutzer mag Museen und hat schon drei besucht, heute etwas anderes vorschlagen" — und trifft inhaltlich sinnvolle Entscheidungen.

Das war früher anders. In der alten Version war der Planning-Agent rein regelbasiert: feste Zeitslots, feste Tagestitel, mathematisches Scoring. Er konnte keinen Kontext einbeziehen. Der neue Planning-Agent ist ein echter KI-Agent, der denkt, statt nur Regeln abzuarbeiten.

**Der Checklist-Agent** erstellt die Packliste für eine Reise. Klingt simpel, aber eine gute Checkliste hängt von vielen Faktoren ab: Reiseziel, Wetter, Reiseart, Dauer, persönliche Präferenzen. Der neue Agent nutzt ein Sprachmodell, um wirklich kontextbezogene Listen zu generieren — statt der alten starren If-Else-Logik, die immer die gleichen Standardpunkte produziert hat.

**Der Budget-Agent** ist bewusst ohne Sprachmodell gebaut — er rechnet deterministisch. Er summiert die Kosten aller geplanten Aktivitäten, vergleicht sie mit dem verfügbaren Budget und gibt einen klaren Status zurück: im Budget, nahe am Limit oder darüber. Für Rechenoperationen braucht man kein Sprachmodell. Was sich ändert: Der Budget-Agent ist jetzt mit dem Finanzmodell des Nutzers verbunden und weiß daher, wie viel Geld tatsächlich für diese Reise zur Verfügung steht.

**Der Finanz-Agent** ist neu. Er verwaltet ein virtuelles Finanzmodell des Nutzers. Einmal im Monat gibt der Nutzer an: sein Gehalt, seine Fixkosten (Miete, Lebensmittel, Versicherungen) und wie viel er diesen Monat für Freizeit und Reisen zur Seite legen möchte. Aus diesen Daten berechnet der Agent das verfügbare Reisebudget. Er kann darüber hinaus in die Zukunft schauen: Wenn das aktuelle Budget für eine bestimmte Reise nicht reicht, kann er berechnen, in wie vielen Monaten es reichen würde — und einen Sparvorschlag formulieren. Der Kern dieser Berechnung ist deterministisch; die Formulierung des Sparvorschlags in natürlicher Sprache übernimmt ein Sprachmodell.

**Der Monitoring-Agent** ist der Wächter. Er läuft im Hintergrund und prüft regelmäßig, ob sich etwas für aktive oder bevorstehende Reisen verändert hat. Zwei Dinge überwacht er besonders: Wetter und Flüge. Wenn für einen Reisetag starker Regen vorhergesagt wird und Outdoor-Aktivitäten geplant sind, schlägt er vor, den Plan anzupassen. Wenn ein Flug ausfällt oder sich stark verspätet, denkt er die Konsequenzen weiter — eine Restaurantreservierung am Abend ist vielleicht nicht mehr erreichbar, ein geplantes Ausflugsziel wird sich nicht mehr ausgehen. Der Agent informiert den Nutzer und löst den Replanning-Agent aus.

**Der Replanning-Agent** erstellt bei Störungen einen neuen Planvorschlag. Er identifiziert, welche Aktivitäten betroffen sind, und sucht geeignete Alternativen. Früher war diese Auswahl rein mathematisch — höchster Score gewinnt. Jetzt übernimmt ein Sprachmodell die Auswahl und kann dabei echten Kontext einbeziehen: Was mag der Nutzer? Was ist bei dem konkreten Wetterereignis sinnvoll? Der Vorschlag wird dem Nutzer präsentiert, der ihn akzeptieren oder ablehnen kann. Das System verändert den Plan nie ohne Zustimmung.

**Der Profil-Lern-Agent** lernt, was dem Nutzer gefällt. Er liest eingehende Telegram-Nachrichten und E-Mails und erkennt darin Hinweise auf Interessen: Wenn jemand ein Konzert vorschlägt und der Nutzer begeistert antwortet, steigt der Musikinteresse-Score. Wenn nach einer Reise gefragt wird „Wie hat dir das Restaurant gefallen?" und der Nutzer antwortet, wird diese Bewertung gespeichert. Über die Zeit entsteht so ein detailliertes Bild: Was isst er gerne? Was hat ihm auf Reisen besonders gefallen? Was eher nicht? Dieses Wissen fließt direkt in den Planning- und Vorschlags-Agenten ein.

**Der Freizeit-Erkenner** ist einfach, aber wichtig. Er liest den Kalender aus und identifiziert Tage ohne oder mit nur wenigen Terminen. Er entscheidet regelbasiert — ein Ganztagstermin oder zwei oder mehr Termine an einem Tag bedeuten: dieser Tag ist besetzt. Alles andere gilt als frei. Diese freien Tage werden in der Datenbank gespeichert und sind die Grundlage für proaktive Vorschläge.

**Der Vorschlags-Agent** verbindet alles. Er nimmt die freien Tage aus dem Kalender, das verfügbare Budget aus dem Finanzmodell und die Interessen aus dem Profil — und generiert daraus konkrete, personalisierte Vorschläge. „Du hast dieses Wochenende frei und 200 Euro übrig — wie wäre es mit einem Tagesausflug nach Potsdam?" Diese Vorschläge werden dem Nutzer präsentiert und warten auf seine Bestätigung.

**Der Tagesbrief-Agent** generiert jeden Morgen eines Reisetages eine persönliche Zusammenfassung. Er schaut auf den Tagesplan, das Wetter, und prüft, ob es relevante Mails oder Nachrichten gibt (Buchungsbestätigungen, Hinweise, etwaige Absagen). Ein Sprachmodell formuliert daraus einen freundlichen, motivierenden Morgenbrief.

**Der Navigations-Agent** berechnet Routen zwischen den Aktivitäten eines Tages und erinnert den Nutzer rechtzeitig, wann er losgehen muss — inklusive zehn Minuten Puffer.

---

## Wie Daten gespeichert und genutzt werden

Das System verwendet eine persistente SQLite-Datenbank (`profile.db`), die alle langfristigen Informationen speichert: das Nutzerprofil, Interessen und ihre Bewertungen, vergangene Events, erkannte freie Tage, generierte Vorschläge und ihre Status, das Finanzmodell sowie alle Reisepläne.

Dieser letzte Punkt ist wichtig: Reisepläne werden nicht mehr flüchtig im Arbeitsspeicher gehalten. Das wäre für ein proaktives System fatal — wenn der Server einmal neustartet, während eine Reise überwacht wird, würde der Monitoring-Agent nichts mehr zum Überwachen finden. Alle aktiven und geplanten Reisen liegen daher in der Datenbank.

Das Profil des Nutzers wächst mit der Zeit. Jede gespeicherte Interaktion — eine Nachricht, eine Reisebewertung, ein angenommener Vorschlag — erhöht den Score der relevanten Interessen-Kategorien. Der Agent weiß also nicht nur, was der Nutzer mögen könnte, sondern wie stark und wie konsistent dieses Interesse ist.

---

## Was sich im Vergleich zur alten Version ändert

Der bisherige Code enthält mehrere Agenten, die vollständig regelbasiert arbeiten: Der Planning-Agent folgte festen Zeitslots, der Recommendation-Agent nutzte ein mathematisches Scoring-System mit hartcodierten Gewichten, und der Checklist-Agent produzierte immer dieselbe Liste basierend auf einfachen If-Else-Abfragen. Diese Agenten werden durch LLM-gestützte Varianten ersetzt, weil sie ein grundlegendes Problem haben: Sie können keinen echten Kontext verstehen. Sie können nicht erkennen, dass ein Nutzer der fünfte Museumsbesuch an Tag drei schon zu viel wäre, oder dass „gutes Essen" für diesen Nutzer bedeutet, dass er lokale Spezialitäten bevorzugt und keine internationalen Ketten.

Was bleibt, sind die Teile des Systems, die bereits gut funktionieren und keinen LLM-Einsatz benötigen: der Budget-Agent für Berechnungen, der Freizeit-Erkenner für die Kalenderlogik, sowie alle Agenten aus dem proaktiven Subsystem, das zuletzt eingeführt wurde — Profil-Lerner, Vorschlags-Agent, Tagesbrief und Navigation. Diese wurden bereits mit Sprachmodell-Unterstützung gebaut und sind ein guter Ausgangspunkt.

---

## Der Weg dorthin: Unsere Entwicklungsphasen

Wir bauen das System schrittweise um, damit zu jeder Zeit ein lauffähiger Zustand vorhanden ist.

Zuerst schaffen wir das Fundament: Einen zentralen LLM-Zugriffspunkt, persistente Datenbankstattung für Reisepläne und die nötigen Erweiterungen des Datenbankschemas. Das verändert das Verhalten des Systems noch nicht — es macht nur die Basis sauber.

Danach führen wir LangGraph ein und bauen den bestehenden Ablauf als expliziten Graphen nach. Wieder ohne Verhaltensänderung — aber jetzt ist die Grundlage für alle weiteren Agenten-Verbindungen gelegt.

Im nächsten Schritt ersetzen wir die regelbasierten Agenten durch ihre LLM-gestützten Nachfolger. Das ist der größte inhaltliche Sprung und macht aus dem regelbasierten Reiseplaner einen echten KI-Agenten.

Dann kommt das Finanzmodell dazu: Der Nutzer kann sein monatliches Budget angeben, und das System macht daraus budgetbewusste Vorschläge und Prognosen.

Schließlich aktivieren wir die proaktive Automatisierung: den Monitoring-Agenten für Wetter und Flüge sowie den Scheduler für zeitgesteuerte Hintergrundläufe. Erst in dieser Phase ist das System wirklich proaktiv im vollen Sinne.

Den Abschluss bildet die Feedback-Schleife: Der Nutzer kann nach Aktivitäten und Reisen Bewertungen abgeben, die das System für zukünftige Empfehlungen nutzt. Damit wird aus einem Agenten, der gute Vorschläge macht, einer, der mit der Zeit immer bessere Vorschläge macht.

---

*Für die technische Detailansicht aller Agenten, das vollständige Datenbankschema und die genaue Auflistung aller Komponenten: siehe `ZIELARCHITEKTUR.md`.*
