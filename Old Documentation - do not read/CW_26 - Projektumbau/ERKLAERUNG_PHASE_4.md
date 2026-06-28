# Phase 4 erklärt — Proaktiver Vorschlag und wöchentlicher Scheduler

*Geschrieben für jemanden, der den bisherigen Code nicht kennt.*

---

## Was das System bisher macht (kurzer Überblick)

Unser Reiseplanungs-Agent kann auf Anfrage des Nutzers eine Reise planen. Der Nutzer öffnet die App, gibt Reiseziel, Datum und Interessen ein, und das System erstellt automatisch einen vollständigen Tagesplan. Außerdem gibt es bereits einen Mechanismus, der „freie Tage" erkennt — also Tage, an denen der Nutzer laut seinem Google-Kalender keine Termine hat — und für diese Tage Freizeitvorschläge erstellt (z.B. „Geh an diesem Samstag ins Museum X"). Diese Vorschläge werden in der Datenbank gespeichert, aber die entscheidende Frage ist: **wann und wie oft** passiert das überhaupt?

Aktuell läuft diese Logik nie von alleine. Jemand muss sie manuell anstoßen — entweder über die API oder durch direktes Aufrufen der Funktion. Das bedeutet: der Agent ist reaktiv. Er macht nur etwas, wenn man ihn explizit darum bittet.

---

## Was Phase 4 ändert — die Grundidee

Phase 4 macht den Agenten **proaktiv**. Das bedeutet: Das System läuft einmal pro Woche automatisch im Hintergrund, schaut in den Google-Kalender des Nutzers, entscheidet mit Hilfe eines KI-Modells welche Tage wirklich frei sind, erstellt für diese Tage einen Freizeitvorschlag — und zeigt diesen Vorschlag dann als Karte in der Chat-Oberfläche an. Der Nutzer sieht dann zum Beispiel: „Du hast nächsten Samstag nichts vor — soll ich dir was für Berlin planen? [Ja] / [Nein]". Drückt er Ja, wird automatisch ein vollständiger Plan erstellt. Drückt er Nein, wird der Vorschlag verworfen.

Das ist der Kern-Gedanke: **Der Agent schläft nicht mehr — er denkt einmal pro Woche voraus und fragt dann den Nutzer, ob er handeln soll.** Der Nutzer behält die Kontrolle (er muss immer Ja sagen), aber der erste Schritt passiert automatisch.

---

## Warum das sinnvoll ist — ein konkretes Beispiel

Stell dir vor, der Nutzer hat nächsten Samstag frei. Er weiß das, aber er denkt nicht daran, die App zu öffnen und aktiv eine Reise zu planen. Ohne Phase 4 passiert dann nichts — der Agent wartet.

Mit Phase 4 läuft das System Samstag morgens von selbst durch, sieht „Samstag: kein Termin, Sonntag: kein Termin, Montag: Feiertag" und schlussfolgert: das ist ein langes Wochenende. Es erstellt einen Vorschlag für einen Tagesausflug nach München oder eine Stadtführung in Berlin — angereichert mit dem Nutzerprofil aus Phase 3 (seine gespeicherten Interessen aus Telegram und E-Mails). Am nächsten Mal, wenn der Nutzer die App öffnet, sieht er im Chat direkt: „Hey, du hattest letzten Samstag Lust auf ein Konzert — soll ich das lange Wochenende verplanen?" Er klickt Ja, und fertig.

---

## Was technisch gebaut werden muss

Es gibt fünf Bereiche.

**1. Eine neue Datei: `calendar_agent.py`**

Bisher erkennt das System freie Tage rein mathematisch: Kein Termin im Kalender an diesem Tag = freier Tag. Das funktioniert bei offensichtlichen Fällen, aber es ist zu plump. Was ist mit einem Termin „Gym 7:00–8:00"? Das ist kein freier Tag im Sinne von „kann nichts unternehmen", aber auch nicht blockiert. Oder ein Termin „Urlaub – Mallorca"? Das ist eindeutig kein freier Tag für Berlin-Vorschläge.

Die neue Datei `calendar_agent.py` enthält eine Funktion, die die rohen Kalender-Einträge an ein KI-Modell schickt und es beurteilen lässt, was die Einträge bedeuten. Das KI-Modell gibt für jeden Tag zurück: frei, teilweise frei oder belegt — und begründet das kurz. So erkennt es, dass „Gym 7:00–8:00" den Tag trotzdem fast frei lässt, aber „Arbeit 8:00–18:00" den Tag praktisch blockiert. Sollte das KI-Modell eine fehlerhafte Antwort liefern, gibt es einen einmaligen Korrektur-Versuch (Repair-Prompt), danach fällt das System auf die alte mathematische Methode zurück.

**2. Eine neue Datei: `scheduler.py` (oder ein Thread in `main.py`)**

Diese Datei ist dafür verantwortlich, dass der gesamte Ablauf automatisch einmal pro Woche läuft — und zwar samstags. Die Umsetzung ist bewusst einfach gehalten: ein Hintergrundthread, der beim Start des Servers mitläuft und jedes Mal, wenn er aufwacht, prüft: „Ist heute Samstag, und habe ich heute noch nicht gelaufen?" Falls ja, startet er den Ablauf: Kalender lesen → KI interpretieren → freie Tage speichern → Vorschlag erstellen.

Dieser Wächter-Mechanismus ist wichtig, damit derselbe Vorschlag nicht zweimal am selben Tag erstellt wird, falls der Server z.B. neu gestartet wird.

**3. Änderung: `calendar.py` und `free_time_detector.py`**

Diese Dateien existieren bereits und sind für die Kalender-Anbindung zuständig. Bisher liest `free_time_detector.py` den Kalender aus und entscheidet rein mathematisch, welche Tage frei sind (kein Termin = frei). Das wird jetzt auf den neuen `calendar_agent` umgestellt: der Detektor gibt die rohen Kalender-Einträge an die KI weiter und übernimmt deren intelligentere Einstufung. Nur Tage, die als „frei" oder „teilweise frei" eingestuft werden, landen am Ende als geplante freie Tage in der Datenbank.

**4. Vorschlag per Telegram senden (statt Streamlit)**

Die Vorschläge werden nicht in der Streamlit-Oberfläche angezeigt, sondern direkt per Telegram an den Nutzer geschickt — mit zwei Inline-Buttons: „✅ Annehmen" und „❌ Ablehnen". Der Nutzer bekommt also auf seinem Handy eine Nachricht wie: „Du hast am Samstag, 5. Juli, freie Zeit — Vorschlag: Tagesausflug nach München. Englischer Garten, Deutsches Museum, Augustiner Keller. Soll ich einen Plan erstellen?"

Drückt der Nutzer Annehmen, wird automatisch ein vollständiger Reiseplan erstellt und ihm ebenfalls per Telegram zugeschickt. Drückt er Ablehnen, wird der Vorschlag in der Datenbank als abgelehnt markiert.

Dieser Mechanismus existiert im Code bereits vollständig — für Flugverspätungen. Die Funktionen `send_flight_delay_proposal`, `_create_callback_token`, `get_callback_updates` und `answer_callback_query` sind fertig. Für Phase 4 wird lediglich eine neue Funktion `send_suggestion_proposal(trip, suggestion)` nach demselben Muster gebaut. `telegram.py` selbst wird dabei nicht verändert — der Aufruf kommt aus dem Scheduler heraus.

**5. Eine Kleinigkeit: Profil-Trennung**

Bisher zieht das System beim Erstellen einer neuen Reise automatisch das gespeicherte Nutzerprofil hinzu (gelernte Interessen aus E-Mails und Telegram). Das soll in Phase 4 getrennt werden: Automatische Vorschläge (die durch den Scheduler erzeugt werden) dürfen das Profil nutzen — das macht sie persönlicher. Manuelle Reisen (wenn der Nutzer selbst das Formular ausfüllt) sollen das Profil dagegen **nicht** automatisch hinzufügen. Der Nutzer hat ja selbst eingetragen, was er will — das sollte nicht still durch das Profil überschrieben werden.

Technisch ist das eine kleine Änderung: Der Planungs-Aufruf bekommt ein neues optionales Feld `auto=True`, das der Scheduler setzt. Nur wenn dieses Feld vorhanden ist, werden Profil-Interessen eingemischt.

---

## Drei offene Fragen, die noch entschieden werden müssen

**Frage 1 — Wie läuft der Scheduler technisch?**

Option A: Ein einfacher Hintergrundthread mit Wochentag-Prüfung (Samstag?). Schlank, keine neue Bibliothek, leicht verständlich. Option B: Eine fertige Scheduler-Bibliothek wie APScheduler, die genauere Zeitplanung erlaubt (z.B. „samstags um 08:00 Uhr"). Mehr Komfort, aber eine neue Abhängigkeit.

**Frage 2 — Was passiert mit „teilweise freien" Tagen?**

Ein Tag mit einem Arzttermin um 10:00 Uhr ist nicht komplett frei, aber auch nicht blockiert. Soll das System für solche Tage trotzdem einen (kürzeren) Vorschlag machen — mit einem Hinweis? Oder werden nur vollständig freie Tage vorgeschlagen?

**Frage 3 — Wie wird manuell vs. automatisch technisch markiert?**

Der Planungs-Aufruf `handle_plan_request` wird sowohl vom Nutzer-Formular als auch vom Scheduler aufgerufen. Über welches konkrete Feld im Request unterscheidet das System die beiden Fälle — z.B. `request["auto"] = True`?

---

## Was man beachten muss

Wenn Google Calendar nicht eingerichtet ist (kein Konto verbunden), liefert der Kalender-Provider eine leere Liste. Das System darf dann nicht abstürzen — es tut einfach nichts und wartet bis zur nächsten Woche.

Doppelte Vorschläge müssen verhindert werden: Wenn der Scheduler zweimal hintereinander läuft, sollen nicht zwei identische Vorschläge für denselben Tag entstehen. Das ist durch den bestehenden Status-Mechanismus in der Datenbank (`pending / rejected / replaced`) bereits gelöst — der Scheduler muss das nur konsequent nutzen.

---

## Zusammenfassung in einem Satz

Phase 4 macht den Agenten proaktiv: Er schaut einmal pro Woche selbst in den Kalender, lässt eine KI entscheiden welche Tage wirklich frei sind, erstellt automatisch personalisierte Freizeitvorschläge — und fragt den Nutzer in der Chat-Oberfläche, ob er daraus einen Plan machen soll.
