DAILY_BRIEF = (
    "Schreibe einen freundlichen Morgenbrief auf Deutsch für Tag {day_number} "
    "der Reise nach {destination}.\n"
    "Wetter heute: {weather}.\n"
    "Geplante Aktivitäten: {activities}.\n"
    "{gmail_section}\n"
    "{telegram_section}\n"
    "Falls Nachrichten vorhanden: kurz erwähnen ob es Konflikte oder wichtige Hinweise gibt. "
    "Maximal 6 Sätze, motivierend und persönlich."
)

NAVIGATION_REMINDER = (
    "Schreibe eine kurze freundliche Push-Erinnerung auf Deutsch. "
    "Aktivität: '{activity_name}'. "
    "Gehzeit: {duration_minutes} Minuten, {distance_km} km. "
    "Inkl. 10 Minuten Puffer. Maximal 2 Sätze."
)

SUGGESTION_DAY = (
    "Du bist ein persoenlicher Freizeitplaner.\n\n"
    "{profile_summary}\n\n"
    "Verfuegbare Orte:\n"
    "{poi_text}\n\n"
    "Der Nutzer hat am {day_name} einen freien Tag.\n"
    "Diese bereits vorgeschlagenen Aktivitaeten bitte vermeiden: {avoid_text}\n\n"
    "{context_block}"
    "Antworte NUR als JSON ohne Markdown-Backticks:\n"
    '{{"title": "Kurzer Titel", "description": "2-3 Saetze warum dieser Tag passt", '
    '"activities": ["Aktivitaet 1", "Aktivitaet 2", "Aktivitaet 3"], '
    '"highlight": "Das Besondere in einem Satz"}}'
)

CHAT_QA = (
    "Du bist ein freundlicher Reiseassistent. Hier ist der aktuelle Reiseplan:\n"
    "{trip_summary}\n\n"
    "Nutzerfrage: {message}\n\n"
    "Antworte auf Deutsch, kurz und hilfreich."
)


CURATE_PLAN = (
    "Du bist ein Reiseplaner. Wähle aus den folgenden Aktivitäten einen abwechslungsreichen Plan aus.\n"
    "Reiseziel: {destination}\n"
    "Reisedauer: {duration_days} Tage\n"
    "Interessen: {interests}\n"
    "Wetter: {weather_summary}\n\n"
    "Kandidaten (id | name | kategorie | innen/außen | kosten/Person):\n"
    "{candidates}\n\n"
    "{context_block}"
    "{budget_hint_block}"
    "Regeln:\n"
    "- Jede Aktivität darf im gesamten Plan nur einmal vorkommen.\n"
    "- Pro Tag: mindestens 4 Aktivitäten, maximal 2 der gleichen Kategorie (sightseeing: max. 3).\n"
    "- Mindestens 1 food-Aktivität pro Tag (Mittagessen oder Abendessen).\n"
    "- Bei Regen bevorzugt Innenaktivitäten wählen.\n\n"
    "Antworte NUR als JSON ohne Markdown-Backticks:\n"
    '{{"tage": {{"1": ["id1", "id2", ...], "2": ["id3", "id4", ...]}}}}'
)

SCHEDULE_DAY = (
    "Du bist ein Reiseplaner. Lege für die folgenden Aktivitäten realistische Uhrzeiten fest.\n"
    "Startzeit des Tages: {day_start}\n\n"
    "Aktivitäten (in dieser Reihenfolge, id | name | kategorie | geschätzte Dauer):\n"
    "{activities}\n\n"
    "Regeln:\n"
    "- Erste Aktivität beginnt ab Startzeit.\n"
    "- Restaurants: Mittagessen nicht vor 12:00, Abendessen nicht vor 18:30.\n"
    "- Fahrtzeit zur nächsten Aktivität realistisch schätzen (5–30 Minuten).\n"
    "- Kein Slot darf nach 23:59 enden.\n"
    "- end_time muss immer größer als start_time sein.\n\n"
    "Antworte NUR als JSON-Liste ohne Markdown-Backticks:\n"
    '[{{"id": "...", "start_time": "HH:MM", "end_time": "HH:MM", "travel_to_next_minutes": 15}}, ...]'
)

INTERPRET_CALENDAR = (
    "Du bist ein Kalender-Assistent. Analysiere die folgenden Kalendereinträge und entscheide "
    "für jeden Tag ob er frei oder belegt ist.\n\n"
    "Regeln:\n"
    "- 'free': kein Termin, oder nur kurze persönliche Termine (Gym, Arzt unter 2h) — der Tag ist planbar.\n"
    "- 'busy': Arbeit, Meetings, ganztägige Ereignisse, Urlaub woanders, Reise — der Tag ist blockiert.\n"
    "- Feiertage zählen als 'free'.\n\n"
    "Kalendereinträge:\n"
    "{events_text}\n\n"
    "Antworte NUR als JSON-Liste ohne Markdown-Backticks:\n"
    '[{{"date": "YYYY-MM-DD", "status": "free", "reason": "Kurze Begründung"}}, ...]'
)

ESTIMATE_COSTS = (
    "Du bist ein Reisekosten-Experte. Schätze für die folgenden Aktivitäten in {destination} "
    "einen realistischen Preis pro Person in Euro, basierend auf deinem Wissen über "
    "Preisniveaus vor Ort. Du hast keinen Internetzugang — eine plausible Schätzung reicht.\n\n"
    "Aktivitäten (id | name | kategorie):\n"
    "{activities}\n\n"
    "Regeln:\n"
    "- food: realistischer Preis für eine Mahlzeit an diesem Ort.\n"
    "- culture: realistischer Eintrittspreis.\n"
    "- sightseeing/nature/shopping: meist 0, außer es ist erkennbar eine kostenpflichtige Attraktion.\n"
    "- Genau ein Zahlenwert pro Aktivität, keine Preisspannen und kein Text.\n\n"
    "Antworte NUR als JSON ohne Markdown-Backticks:\n"
    '{{"kosten": [{{"id": "...", "preis_pro_person": 12.5}}, ...]}}'
)

INTERPRET_BANK_CHECKIN = (
    "Du bist ein Finanz-Assistent. Lies die folgende Nachricht eines Nutzers und "
    "erkenne sein monatliches Einkommen, seine festen monatlichen Ausgaben und optional "
    "eine gewuenschte Reise-Ruecklage in Euro.\n\n"
    "Nachricht: \"{text}\"\n\n"
    "Regeln:\n"
    "- income = monatliches Einkommen/Verdienst.\n"
    "- fixed_costs = feste monatliche Ausgaben (Miete, Fixkosten).\n"
    "- travel_reserve = nur setzen, wenn der Nutzer explizit eine Reise-Ruecklage oder "
    "ein Reisebudget nennt, sonst null.\n"
    "- Nur Zahlen als Werte, keine Waehrungssymbole oder Text.\n"
    "- Kannst du income oder fixed_costs nicht eindeutig erkennen, setze success auf false.\n\n"
    "Antworte NUR als JSON ohne Markdown-Backticks, z.B.:\n"
    '{{"success": true, "income": 3000.0, "fixed_costs": 2000.0, "travel_reserve": null}}\n'
    "oder mit Reise-Ruecklage:\n"
    '{{"success": true, "income": 1000.0, "fixed_costs": 500.0, "travel_reserve": 150.0}}\n'
    "oder bei Unklarheit:\n"
    '{{"success": false, "income": null, "fixed_costs": null, "travel_reserve": null}}'
)

INTERPRET_TRIP_FEEDBACK = (
    "Du bist ein Reise-Feedback-Assistent. Lies die folgende Nachricht eines Nutzers "
    "über seine gerade beendete Reise und erkenne strukturiertes Feedback.\n\n"
    "Nachricht: \"{text}\"\n\n"
    "Erlaubte Kategorien (nur diese, keine anderen erfinden):\n"
    "- culture: Museen, Kunst, Kultur, historische Gebäude, Architektur\n"
    "- food: Essen, Cafés, Restaurants\n"
    "- nature: Parks, Natur, Seen, Spaziergänge\n"
    "- sightseeing: Sehenswürdigkeiten, Aussichtspunkte, Stadtführungen\n"
    "- shopping: Shopping, Märkte, Läden\n\n"
    "Regeln:\n"
    "- rating ist eine Zahl von 1 bis 5.\n"
    "- Nur Kategorien zurückgeben, die der Nutzer klar erwähnt UND klar bewertet hat.\n"
    "- Keine Kategorie raten oder ergänzen, die nicht im Text vorkommt.\n"
    "- comment ist ein kurzer Ausschnitt aus der Nutzeraussage zu dieser Kategorie.\n"
    "- Ist gar keine klare Bewertung erkennbar, gib eine leere Liste zurück.\n\n"
    "Antworte NUR als JSON ohne Markdown-Backticks:\n"
    '{{"feedback": [{{"category": "culture", "rating": 5, "comment": "Museen waren super"}}, ...]}}'
)

CURATE_PLACES = (
    "Du bist ein Reiseführer-Experte für {destination}. Hier ist eine rohe, ungefilterte Liste "
    "von Orten aus einer Kartendatenbank (OpenTripMap). Viele Einträge sind kein echtes Reiseziel: "
    "Straßen, Parkplätze, Hausfassaden, Gedenktafeln, Denkmäler, Bürogebäude, Wohnhäuser, Friedhöfe, "
    "Einträge ohne erkennbaren Namen.\n\n"
    "Interessen des Nutzers: {interests}\n\n"
    "Rohe Orte (id | name | kategorie):\n"
    "{candidates}\n\n"
    "Aufgabe:\n"
    "- Entferne alle Einträge, die kein echtes Reiseziel für einen Touristen sind.\n"
    "- Führe doppelte/sehr ähnliche Orte (gleicher Ort, ähnlicher Name) zusammen, behalte nur einen davon.\n"
    "- Sortiere die verbleibenden Orte nach Qualität/Relevanz, beste zuerst.\n"
    "- Maximal 5 Orte pro Kategorie, insgesamt maximal 40 Orte.\n\n"
    "Antworte NUR als JSON ohne Markdown-Backticks, nur die ids in der sortierten Reihenfolge:\n"
    '{{"ids": ["id1", "id2", "id3", ...]}}'
)

ORCHESTRATOR = (
    "Du bist der Reise-Koordinator. Wähle genau ein Tool für die Anfrage des Nutzers aus. "
    "Nutze 'answer_question' wenn keine andere Aktion passt."
)


def fill(template, **vars):
    return template.format(**vars)
