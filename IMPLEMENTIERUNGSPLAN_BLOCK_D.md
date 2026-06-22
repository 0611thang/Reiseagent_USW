# Implementierungsplan — Block D (Profil & Interessen-Intelligenz)

**Datum:** 21.06.2026
**Grundlage:** [TODO_2026-06-21.md](TODO_2026-06-21.md)
**Umfang:** D1 (E-Mail-Monitoring-Agent), D2 (Interessen-basierte Reiseerstellung)
**Abhängigkeit:** D1 braucht **B3** (IMAP-Provider). D2 braucht D1.

---

## D1 — E-Mail-Monitoring-Agent

### Ziel
Das web.de-Postfach (via B3) regelmäßig auslesen, Interessen extrahieren und im Profil (`profile_store`) speichern. Für die Demo werden Fake-Mails (Gym-Abo, Architektur-Magazin) gesendet, die der Agent erkennt.

### Betroffene Dateien
- `reiseagent/agents/profile_learner.py` → neue `learn_from_imap()`, Einbindung in `run_profile_update`
- `reiseagent/main.py` → Profil-Update-Loop/Endpoint, der den IMAP-Provider speist
- `reiseagent/providers/imap_mail.py` (aus B3)

### Ausgangslage (viel ist schon da)
- `profile_learner.py` hat Keyword-Extraktion (`INTEREST_CATEGORIES:6`, `_extract_interests_from_text:26`) und `learn_from_gmail(emails)` (`:56`), das `{subject, snippet}` erwartet.
- `run_profile_update(telegram_messages, gmail_emails)` (`:62`) ist der Einstieg; speichert via `profile_store.save_interest` (`profile_store.py:49`) und liefert `get_top_interests` (`:106`).
- Der IMAP-Provider (B3) liefert exakt `{subject, from, snippet}` → kompatibel.

### Schritte
1. **Brücke in `profile_learner.py`:**
   ```python
   def learn_from_imap(emails):
       # gleiches Format wie Gmail -> Logik wiederverwenden
       return learn_from_gmail(emails)
   ```
   (Oder `run_profile_update` um Parameter `imap_emails=None` erweitern und intern `learn_from_gmail` aufrufen.)
2. **`run_profile_update` erweitern** (`:62`):
   ```python
   def run_profile_update(telegram_messages=None, gmail_emails=None, imap_emails=None):
       profile_store.init_db()
       if telegram_messages: learn_from_telegram(telegram_messages)
       if gmail_emails:       learn_from_gmail(gmail_emails)
       if imap_emails:        learn_from_imap(imap_emails)
       ...
   ```
3. **Speisung in `main.py`:** Im bestehenden Profil-Endpoint (`main.py:345-349`) zusätzlich `from providers.imap_mail import get_recent_emails as get_imap_emails` und `imap_emails=get_imap_emails(20)` übergeben.
4. **Periodisch (optional):** kleiner Background-Thread analog `_monitoring_loop` (`main.py:50`), der z. B. alle 30 Min `run_profile_update(imap_emails=get_imap_emails())` aufruft. Für die Demo reicht ggf. ein manueller Trigger/Button.

### Verbesserung (optional, empfohlen)
Die aktuelle Extraktion ist rein keyword-basiert (`INTEREST_CATEGORIES`). Für robustere Demo-Ergebnisse: LLM-Extraktion via `llm.py` (aus C2) — „Welche Interessen-Tags stecken in dieser Mail?" → strukturiertes JSON. Keyword-Variante als Fallback behalten.

### Edge Cases
- IMAP nicht konfiguriert → `get_recent_emails` liefert `[]` → `run_profile_update` läuft leer durch, kein Crash.
- Doppelte Interessen: `save_interest` (`profile_store.py:49`) sollte idempotent sein/Score erhöhen statt duplizieren — prüfen, ggf. UPSERT.
- Spam/irrelevante Mails: Keyword-Filter greift nur bei Treffern; LLM-Variante kann „kein Interesse" zurückgeben.

### Verifikation
1. Fake-Mail „Willkommen im FitnessFirst Gym" senden.
2. Profil-Update triggern → `profile_store.get_top_interests()` enthält `sport`.
3. Zweite Mail „ARCHITECTURE TODAY Magazin" → `kunst`/`architektur` erscheint.

### Aufwand
~2–3 h (mehr, wenn LLM-Extraktion).

---

## D2 — Interessen-basierte automatische Reiseerstellung

### Ziel
Beim Erstellen einer Reise das gespeicherte Interessenprofil automatisch als Kontext an den Planner (C2) übergeben, damit Vorschläge zum Nutzer passen.

### Betroffene Dateien
- `reiseagent/agents/coordinator.py` → `handle_plan_request` (`:15`)
- `reiseagent/profile_store.py` → `get_top_interests` (`:106`)
- `reiseagent/agents/planning.py` / `recommendation.py` (Scoring nutzt `request["interests"]`)

### Ausgangslage
- Reise nutzt aktuell nur die im Formular gewählten `interests` (`streamlit_app.py:1002`).
- `recommendation.score_activity` (`:30`) gewichtet nach `request["interests"]`.

### Schritte
1. In `handle_plan_request` (`coordinator.py:15`) vor dem Planen das Profil laden:
   ```python
   profile_interests = [i["category"] for i in profile_store.get_top_interests(limit=5)]
   ```
2. **Merge-Strategie:** Profil-Interessen mit den Formular-Interessen zusammenführen (Formular gewinnt bei Konflikt, Profil ergänzt). In `request["interests"]` schreiben **oder** als separates `request["profile_interests"]` für gewichtetes Scoring.
3. **Transparenz:** Im Agent-Insight vermerken, dass Profil-Interessen einbezogen wurden („Plan berücksichtigt deine Interessen: Architektur, Sport").
4. **Auto-Reise (optional, Demo-Highlight):** Endpoint/Button „Reise basierend auf meinem Profil vorschlagen" → erzeugt Request rein aus Profil + Zielstadt.

### Edge Cases
- Leeres Profil → Verhalten exakt wie heute (nur Formular-Interessen). Kein Bruch.
- Profil-Kategorien (`musik`, `kunst`, …) vs. Formular-Labels (`Museen`, `gutes Essen`) → Mapping-Tabelle nötig, damit Scoring greift.

### Verifikation
- Profil mit „kunst" füllen (über D1) → neue Reise zeigt mehr Kunst/Museen.
- Leeres Profil → identisches Ergebnis wie vor D2.

### Aufwand
~2–3 h.

---

## Definition of Done (Block D)
- [ ] D1: web.de-Mails werden gelesen, Interessen landen in `profile_store`
- [ ] D1: Fake-Mail (Gym/Architektur) erzeugt korrektes Interessen-Tag
- [ ] D2: Reiseerstellung bezieht Profil-Interessen ein, transparent im Insight
- [ ] D2: Leeres Profil bricht nichts (Verhalten wie vorher)

## Offene Entscheidungen
1. **D1:** Keyword-Extraktion behalten oder auf LLM umstellen? (Empfehlung: LLM mit Keyword-Fallback, sobald `llm.py` aus C2 existiert.)
2. **D1:** Automatischer Poll-Thread oder manueller Trigger für die Demo? (Empfehlung: manueller Button reicht für Vorführung.)
3. **D2:** Mapping Profil-Kategorien ↔ Formular-Labels — wer pflegt die Tabelle?
