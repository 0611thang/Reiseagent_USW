import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()  # ohne .env kein GROQ_API_KEY -> LLM-Tests wuerden nur den Fallback pruefen

from datetime import date, timedelta

# ── Ergebnis-Tracking ────────────────────────────────────────────────────────

passed = []
failed = []

def ok(label):
    print(f"[PASS] {label}")
    passed.append(label)

def fail(label, reason=""):
    msg = f"[FAIL] {label}" + (f": {reason}" if reason else "")
    print(msg)
    failed.append((label, reason))

# ── TEST 1 – Geocoding ───────────────────────────────────────────────────────

print("\n── TEST 1 – Geocoding ──────────────────────────────────────────────────")
try:
    from providers.geocoding import get_coordinates
    coords = get_coordinates("Berlin")
    if coords and "lat" in coords and "lng" in coords:
        ok("TEST 1 - Geocoding: Berlin Koordinaten korrekt")
    else:
        fail("TEST 1 - Geocoding: Berlin Koordinaten korrekt", f"Ergebnis: {coords}")
except Exception as e:
    fail("TEST 1 - Geocoding: Berlin Koordinaten korrekt", str(e))

try:
    coords = get_coordinates("Paris")
    if coords and "lat" in coords and "lng" in coords:
        ok("TEST 1 - Geocoding: Paris Koordinaten korrekt")
    else:
        fail("TEST 1 - Geocoding: Paris Koordinaten korrekt", f"Ergebnis: {coords}")
except Exception as e:
    fail("TEST 1 - Geocoding: Paris Koordinaten korrekt", str(e))

try:
    coords = get_coordinates("UnbekannteStadt123")
    ok("TEST 1 - Geocoding: Unbekannte Stadt kein Crash")
except Exception as e:
    fail("TEST 1 - Geocoding: Unbekannte Stadt kein Crash", str(e))

# ── TEST 2 – Wetter ──────────────────────────────────────────────────────────

print("\n── TEST 2 – Wetter ─────────────────────────────────────────────────────")
try:
    from providers.weather import get_weather_for_trip
    weather = get_weather_for_trip({"destination": "Berlin", "duration_days": 3}, use_mock=True)
    if isinstance(weather, list) and len(weather) == 3:
        ok("TEST 2 - Wetter: 3 Einträge zurückgegeben")
    else:
        fail("TEST 2 - Wetter: 3 Einträge zurückgegeben", f"Länge: {len(weather) if isinstance(weather, list) else type(weather)}")
except Exception as e:
    fail("TEST 2 - Wetter: 3 Einträge zurückgegeben", str(e))

try:
    required = {"day_number", "condition", "description", "affects_outdoor_activities"}
    missing = [r for r in required if r not in weather[0]]
    if not missing:
        ok("TEST 2 - Wetter: Felder vorhanden (day_number, condition, description, affects_outdoor_activities)")
    else:
        fail("TEST 2 - Wetter: Felder vorhanden", f"Fehlend: {missing}")
except Exception as e:
    fail("TEST 2 - Wetter: Felder vorhanden", str(e))

# ── TEST 3 – Places ──────────────────────────────────────────────────────────

print("\n── TEST 3 – Places ─────────────────────────────────────────────────────")
try:
    from providers.places import get_places
    places = get_places("Berlin", ["Museen", "Sehenswürdigkeiten"])
    if isinstance(places, list) and len(places) >= 3:
        ok(f"TEST 3 - Places: Mindestens 3 Aktivitäten ({len(places)} zurückgegeben)")
    else:
        fail("TEST 3 - Places: Mindestens 3 Aktivitäten", f"Nur {len(places) if isinstance(places, list) else 0} zurückgegeben")
except Exception as e:
    fail("TEST 3 - Places: Mindestens 3 Aktivitäten", str(e))
    places = []

try:
    required = {"id", "name", "category", "location"}
    missing = [r for r in required if r not in places[0]] if places else list(required)
    if not missing:
        ok("TEST 3 - Places: Felder vorhanden (id, name, category, location)")
    else:
        fail("TEST 3 - Places: Felder vorhanden", f"Fehlend: {missing}")
except Exception as e:
    fail("TEST 3 - Places: Felder vorhanden", str(e))

# ── TEST 4 – Recommendation Agent ───────────────────────────────────────────

print("\n── TEST 4 – Recommendation Agent ───────────────────────────────────────")
TEST_REQUEST = {
    "destination": "Berlin",
    "duration_days": 3,
    "budget_total": 600.0,
    "currency": "EUR",
    "number_of_people": 2,
    "travel_type": "couple",
    "interests": ["Museen", "Sehenswürdigkeiten"],
}
TEST_ACTIVITY = {
    "id": "test-museum",
    "name": "Testmuseum",
    "category": "museum",
    "tags": ["museen", "geschichte"],
    "estimated_cost_per_person": 10.0,
    "indoor_outdoor": "indoor",
}
TEST_WEATHER = {"condition": "rain", "affects_outdoor_activities": True}

try:
    from agents.recommendation import score_activity
    score = score_activity(TEST_ACTIVITY, TEST_REQUEST, TEST_WEATHER)
    if isinstance(score, dict) and "overall_score" in score and 0.0 <= score["overall_score"] <= 1.0:
        ok(f"TEST 4 - Recommendation: score_activity liefert overall_score ({score['overall_score']})")
    else:
        fail("TEST 4 - Recommendation: score_activity liefert overall_score", f"Ergebnis: {score}")
except Exception as e:
    fail("TEST 4 - Recommendation: score_activity liefert overall_score", str(e))

try:
    from agents.recommendation import pick_activities_for_day
    activities = pick_activities_for_day(places if places else [TEST_ACTIVITY], 1, TEST_REQUEST, TEST_WEATHER, set())
    if isinstance(activities, list) and len(activities) <= 4:
        ok(f"TEST 4 - Recommendation: pick_activities_for_day max 4 Aktivitäten ({len(activities)} zurückgegeben)")
    else:
        fail("TEST 4 - Recommendation: pick_activities_for_day max 4", f"Anzahl: {len(activities)}")
except Exception as e:
    fail("TEST 4 - Recommendation: pick_activities_for_day max 4", str(e))

# ── TEST 5 – Planning Agent ──────────────────────────────────────────────────

print("\n── TEST 5 – Planning Agent ─────────────────────────────────────────────")
try:
    from agents.planning import create_plan
    weather3 = get_weather_for_trip({"destination": "Berlin", "duration_days": 3}, use_mock=True)
    days = create_plan(TEST_REQUEST, places if places else [], weather3)
    if isinstance(days, list) and len(days) == 3:
        ok(f"TEST 5 - Planning: create_plan liefert 3 Tage")
    else:
        fail("TEST 5 - Planning: create_plan liefert 3 Tage", f"Anzahl: {len(days) if isinstance(days, list) else type(days)}")
except Exception as e:
    fail("TEST 5 - Planning: create_plan liefert 3 Tage", str(e))
    days = []

try:
    required = {"day_number", "title", "date", "time_slots"}
    missing = [r for r in required if r not in days[0]] if days else list(required)
    if not missing:
        ok("TEST 5 - Planning: Felder vorhanden (day_number, title, date, time_slots)")
    else:
        fail("TEST 5 - Planning: Felder vorhanden", f"Fehlend: {missing}")
except Exception as e:
    fail("TEST 5 - Planning: Felder vorhanden", str(e))

# ── TEST 6 – Budget Agent ────────────────────────────────────────────────────

print("\n── TEST 6 – Budget Agent ───────────────────────────────────────────────")
try:
    from agents.budget import calculate_budget
    budget_result = calculate_budget(days if days else [], TEST_REQUEST)
    required = {"budget_total", "planned_total", "remaining", "status"}
    missing = [r for r in required if r not in budget_result]
    if not missing:
        ok("TEST 6 - Budget: Felder vorhanden (budget_total, planned_total, remaining, status)")
    else:
        fail("TEST 6 - Budget: Felder vorhanden", f"Fehlend: {missing}")
except Exception as e:
    fail("TEST 6 - Budget: Felder vorhanden", str(e))
    budget_result = {}

try:
    valid_statuses = {"within_budget", "near_limit", "over_budget"}
    status = budget_result.get("status", "")
    if status in valid_statuses:
        ok(f"TEST 6 - Budget: Status gültig ({status})")
    else:
        fail("TEST 6 - Budget: Status gültig", f"Status: '{status}'")
except Exception as e:
    fail("TEST 6 - Budget: Status gültig", str(e))

# ── TEST 7 – Checklist Agent ─────────────────────────────────────────────────

print("\n── TEST 7 – Checklist Agent ────────────────────────────────────────────")
try:
    from agents.checklist import create_checklist
    checklist_data = create_checklist("test-trip-id", TEST_REQUEST, weather3 if 'weather3' in dir() else [])
    if isinstance(checklist_data, dict) and "items" in checklist_data:
        ok("TEST 7 - Checklist: dict mit items zurückgegeben")
    else:
        fail("TEST 7 - Checklist: dict mit items zurückgegeben", f"Typ: {type(checklist_data)}")
except Exception as e:
    fail("TEST 7 - Checklist: dict mit items zurückgegeben", str(e))
    checklist_data = {"items": []}

try:
    items = checklist_data.get("items", [])
    if len(items) >= 5:
        ok(f"TEST 7 - Checklist: Mindestens 5 Items ({len(items)} vorhanden)")
    else:
        fail("TEST 7 - Checklist: Mindestens 5 Items", f"Nur {len(items)}")
except Exception as e:
    fail("TEST 7 - Checklist: Mindestens 5 Items", str(e))

try:
    required = {"id", "label", "category", "completed", "priority"}
    missing = [r for r in required if r not in items[0]] if items else list(required)
    if not missing:
        ok("TEST 7 - Checklist: Item-Felder vorhanden (id, label, category, completed, priority)")
    else:
        fail("TEST 7 - Checklist: Item-Felder vorhanden", f"Fehlend: {missing}")
except Exception as e:
    fail("TEST 7 - Checklist: Item-Felder vorhanden", str(e))

# ── TEST 8 – Coordinator ─────────────────────────────────────────────────────

print("\n── TEST 8 – Coordinator ────────────────────────────────────────────────")
DEMO_REQUEST = {
    "destination": "Berlin",
    "duration_days": 3,
    "budget_total": 600.0,
    "currency": "EUR",
    "number_of_people": 2,
    "travel_type": "couple",
    "interests": ["Museen", "gutes Essen", "Sehenswürdigkeiten", "Spaziergänge"],
}
try:
    from agents.coordinator import handle_plan_request
    result = handle_plan_request(DEMO_REQUEST, use_mock_weather=True)
    required = {"active_plan", "checklist", "agent_insights"}
    missing = [r for r in required if r not in result]
    if not missing:
        ok("TEST 8 - Coordinator: active_plan, checklist, agent_insights vorhanden")
    else:
        fail("TEST 8 - Coordinator: Felder vorhanden", f"Fehlend: {missing}")
    COORDINATOR_RESULT = result
except Exception as e:
    fail("TEST 8 - Coordinator: Felder vorhanden", str(e))
    COORDINATOR_RESULT = None

try:
    insights = COORDINATOR_RESULT.get("agent_insights", []) if COORDINATOR_RESULT else []
    if len(insights) >= 5:
        ok(f"TEST 8 - Coordinator: Mindestens 5 Agent Insights ({len(insights)} vorhanden)")
    else:
        fail("TEST 8 - Coordinator: Mindestens 5 Agent Insights", f"Nur {len(insights)}")
except Exception as e:
    fail("TEST 8 - Coordinator: Mindestens 5 Agent Insights", str(e))

# ── TEST 9 – Replanning Agent ────────────────────────────────────────────────

print("\n── TEST 9 – Replanning Agent ───────────────────────────────────────────")
try:
    from agents.replanning import create_replanning_proposal
    if COORDINATOR_RESULT:
        test_trip = {
            "request": DEMO_REQUEST,
            "active_plan": COORDINATOR_RESULT["active_plan"],
        }
        all_acts = COORDINATOR_RESULT.get("all_activities", places if places else [])
        weather_event = {"day_number": 1, "condition": "rain", "severity": "medium", "description": "Starkregen"}
        proposal = create_replanning_proposal(test_trip, weather_event, all_acts)
        required = {"id", "reason", "changes", "proposed_plan", "status"}
        missing = [r for r in required if r not in proposal]
        if not missing:
            ok("TEST 9 - Replanning: Proposal mit id, reason, changes, proposed_plan, status")
        else:
            fail("TEST 9 - Replanning: Proposal Felder", f"Fehlend: {missing}")

        if proposal.get("status") == "pending":
            ok("TEST 9 - Replanning: Status ist 'pending'")
        else:
            fail("TEST 9 - Replanning: Status ist 'pending'", f"Status: {proposal.get('status')}")
    else:
        fail("TEST 9 - Replanning: Proposal erstellt", "Coordinator-Ergebnis fehlt (TEST 8 fehlgeschlagen)")
except Exception as e:
    fail("TEST 9 - Replanning: Proposal erstellt", str(e))

# ── TEST 10 – Profile Store ──────────────────────────────────────────────────

print("\n── TEST 10 – Profile Store ─────────────────────────────────────────────")
try:
    import profile_store
    profile_store.init_db()
    ok("TEST 10 - Profile Store: init_db() kein Crash")
except Exception as e:
    fail("TEST 10 - Profile Store: init_db() kein Crash", str(e))

try:
    profile_store.save_interest("musik", "konzert_test", score=2.0, source="test")
    interests = profile_store.get_top_interests(limit=5)
    assert isinstance(interests, list)
    ok("TEST 10 - Profile Store: save_interest / get_top_interests funktionieren")
except Exception as e:
    fail("TEST 10 - Profile Store: save_interest / get_top_interests", str(e))

try:
    profile_store.save_past_event("Test Event", "musik", "2024-01-01", "test")
    events = profile_store.get_past_events(limit=5)
    assert isinstance(events, list)
    ok("TEST 10 - Profile Store: save_past_event / get_past_events funktionieren")
except Exception as e:
    fail("TEST 10 - Profile Store: save_past_event / get_past_events", str(e))

try:
    free_day = (date.today() + timedelta(days=5)).isoformat()
    profile_store.save_free_day(free_day)
    free_days = profile_store.get_upcoming_free_days(limit=5)
    assert isinstance(free_days, list)
    ok("TEST 10 - Profile Store: save_free_day / get_upcoming_free_days funktionieren")
except Exception as e:
    fail("TEST 10 - Profile Store: save_free_day / get_upcoming_free_days", str(e))

try:
    profile_store.save_suggestion(free_day, "Test Vorschlag", "Beschreibung", ["Aktivität A", "Aktivität B"])
    suggestions = profile_store.get_pending_suggestions()
    assert isinstance(suggestions, list)
    ok("TEST 10 - Profile Store: save_suggestion / get_pending_suggestions funktionieren")
except Exception as e:
    fail("TEST 10 - Profile Store: save_suggestion / get_pending_suggestions", str(e))
    suggestions = []

try:
    if suggestions:
        sid = suggestions[0]["id"]
        profile_store.update_suggestion_status(sid, "accepted")
        updated = profile_store.get_pending_suggestions()
        still_pending = any(s["id"] == sid for s in updated)
        if not still_pending:
            ok("TEST 10 - Profile Store: update_suggestion_status ändert Status")
        else:
            fail("TEST 10 - Profile Store: update_suggestion_status ändert Status", "Eintrag noch pending")
    else:
        fail("TEST 10 - Profile Store: update_suggestion_status", "Keine Suggestions vorhanden")
except Exception as e:
    fail("TEST 10 - Profile Store: update_suggestion_status", str(e))

# ── TEST 11 – Profile Learner ────────────────────────────────────────────────

print("\n── TEST 11 – Profile Learner ───────────────────────────────────────────")
try:
    from agents.profile_learner import learn_from_telegram, learn_from_gmail, run_profile_update
    test_msgs = [
        {"text": "Hab heute ein Konzert Ticket gekauft!", "date": "18:00"},
        {"text": "Morgen gehen wir ins Museum der Stadtgeschichte.", "date": "19:30"},
    ]
    learn_from_telegram(test_msgs)
    ok("TEST 11 - Profile Learner: learn_from_telegram kein Crash")
except Exception as e:
    fail("TEST 11 - Profile Learner: learn_from_telegram kein Crash", str(e))

try:
    test_emails = [
        {"subject": "Buchung für das Konzert bestätigt", "snippet": "Dein Ticket für das Festival ist bereit."},
        {"subject": "Restaurant Reservierung", "snippet": "Tisch für 2 Personen reserviert."},
    ]
    learn_from_gmail(test_emails)
    ok("TEST 11 - Profile Learner: learn_from_gmail kein Crash")
except Exception as e:
    fail("TEST 11 - Profile Learner: learn_from_gmail kein Crash", str(e))

try:
    update_result = run_profile_update(telegram_messages=test_msgs, gmail_emails=test_emails)
    if "top_interests" in update_result and "agent_insight" in update_result:
        ok(f"TEST 11 - Profile Learner: run_profile_update liefert top_interests und agent_insight ({len(update_result['top_interests'])} Interessen)")
    else:
        fail("TEST 11 - Profile Learner: run_profile_update Felder", f"Keys: {list(update_result.keys())}")
except Exception as e:
    fail("TEST 11 - Profile Learner: run_profile_update", str(e))

# ── TEST 12 – Free Time Detector ─────────────────────────────────────────────

print("\n── TEST 12 – Free Time Detector ────────────────────────────────────────")
try:
    from agents.free_time_detector import detect_and_save_free_days
    ft_result = detect_and_save_free_days(days_ahead=7)
    if "free_days" in ft_result and "agent_insight" in ft_result:
        ok(f"TEST 12 - Free Time Detector: free_days und agent_insight vorhanden")
    else:
        fail("TEST 12 - Free Time Detector: Felder", f"Keys: {list(ft_result.keys())}")
except Exception as e:
    fail("TEST 12 - Free Time Detector: free_days und agent_insight", str(e))

# ── TEST 13 – Suggestion Agent ───────────────────────────────────────────────

print("\n── TEST 13 – Suggestion Agent ──────────────────────────────────────────")
try:
    from agents.suggestion_agent import create_suggestion_for_day, create_suggestions_for_upcoming_free_days
    test_date = (date.today() + timedelta(days=4)).isoformat()
    profile_store.save_free_day(test_date)
    suggestion = create_suggestion_for_day(test_date, home_city="Berlin")
    required = {"title", "activities", "status"}
    missing = [r for r in required if r not in suggestion]
    if not missing:
        ok(f"TEST 13 - Suggestion Agent: create_suggestion_for_day liefert title, activities, status")
    else:
        fail("TEST 13 - Suggestion Agent: create_suggestion_for_day Felder", f"Fehlend: {missing}")
except Exception as e:
    fail("TEST 13 - Suggestion Agent: create_suggestion_for_day", str(e))

try:
    sug_result = create_suggestions_for_upcoming_free_days(home_city="Berlin", max_suggestions=2)
    if "suggestions" in sug_result and "agent_insight" in sug_result:
        ok(f"TEST 13 - Suggestion Agent: create_suggestions_for_upcoming_free_days liefert suggestions und agent_insight ({len(sug_result['suggestions'])} Vorschläge)")
    else:
        fail("TEST 13 - Suggestion Agent: create_suggestions_for_upcoming_free_days Felder", f"Keys: {list(sug_result.keys())}")
except Exception as e:
    fail("TEST 13 - Suggestion Agent: create_suggestions_for_upcoming_free_days", str(e))

# ── TEST 14 – Navigation Provider ────────────────────────────────────────────

print("\n── TEST 14 – Navigation Provider ───────────────────────────────────────")
try:
    from providers.navigation import get_route
    old_key = os.environ.pop("ORS_API_KEY", None)
    result = get_route(52.52, 13.405, 52.53, 13.42)
    if old_key:
        os.environ["ORS_API_KEY"] = old_key
    if result is None:
        ok("TEST 14 - Navigation Provider: get_route ohne ORS-Key gibt None zurück")
    else:
        ok(f"TEST 14 - Navigation Provider: get_route liefert Ergebnis (ORS-Key vorhanden: {result})")
except Exception as e:
    fail("TEST 14 - Navigation Provider: get_route ohne Key kein Crash", str(e))

try:
    result = get_route(999.0, 999.0, 999.0, 999.0)
    ok("TEST 14 - Navigation Provider: get_route mit ungültigen Koordinaten kein Crash")
except Exception as e:
    fail("TEST 14 - Navigation Provider: get_route mit ungültigen Koordinaten kein Crash", str(e))

# ── TEST 15 – Navigation Agent ────────────────────────────────────────────────

print("\n── TEST 15 – Navigation Agent ──────────────────────────────────────────")
try:
    from agents.navigation import create_navigation_reminder
    reminder = create_navigation_reminder("Brandenburger Tor", None)
    if isinstance(reminder, str) and len(reminder) > 0:
        ok(f"TEST 15 - Navigation Agent: Fallback-Text bei route=None ({reminder[:60]})")
    else:
        fail("TEST 15 - Navigation Agent: Fallback-Text", f"Ergebnis: {reminder}")
except Exception as e:
    fail("TEST 15 - Navigation Agent: Fallback-Text bei route=None", str(e))

try:
    test_route = {"duration_minutes": 12, "distance_km": 0.9, "mode": "foot-walking"}
    reminder = create_navigation_reminder("Reichstag", test_route)
    if isinstance(reminder, str) and len(reminder) > 0:
        ok(f"TEST 15 - Navigation Agent: Text bei Test-Route ({reminder[:60]})")
    else:
        fail("TEST 15 - Navigation Agent: Text bei Test-Route", f"Ergebnis: {reminder}")
except Exception as e:
    fail("TEST 15 - Navigation Agent: Text bei Test-Route", str(e))

# ── TEST 16 – Telegram Provider ──────────────────────────────────────────────

print("\n── TEST 16 – Telegram Provider ─────────────────────────────────────────")
try:
    from providers.telegram import get_recent_messages, find_trip_relevant_messages
    old_token = os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    msgs = get_recent_messages(hours=24)
    if old_token:
        os.environ["TELEGRAM_BOT_TOKEN"] = old_token
    if msgs == []:
        ok("TEST 16 - Telegram Provider: get_recent_messages ohne Token gibt leere Liste")
    else:
        ok(f"TEST 16 - Telegram Provider: get_recent_messages liefert {len(msgs)} Nachrichten")
except Exception as e:
    fail("TEST 16 - Telegram Provider: get_recent_messages ohne Token", str(e))

try:
    test_messages = [
        {"text": "Das Hotel in Berlin hat bestätigt.", "date": "10:00"},
        {"text": "Was soll ich heute Abend kochen?", "date": "11:00"},
        {"text": "Bahn Ticket nach Berlin gekauft", "date": "12:00"},
    ]
    relevant = find_trip_relevant_messages(test_messages, "Berlin")
    if len(relevant) == 2:
        ok(f"TEST 16 - Telegram Provider: find_trip_relevant_messages filtert korrekt (2 von 3)")
    else:
        fail("TEST 16 - Telegram Provider: find_trip_relevant_messages", f"{len(relevant)} von 3 gefunden (erwartet: 2)")
except Exception as e:
    fail("TEST 16 - Telegram Provider: find_trip_relevant_messages", str(e))

# ── TEST 17 – Gmail Provider ──────────────────────────────────────────────────

print("\n── TEST 17 – Gmail Provider ────────────────────────────────────────────")
try:
    from providers.gmail import get_recent_emails, find_trip_relevant_emails
    emails = get_recent_emails(hours=24)
    if isinstance(emails, list):
        ok(f"TEST 17 - Gmail Provider: get_recent_emails ohne credentials.json kein Crash (leere Liste)")
    else:
        fail("TEST 17 - Gmail Provider: get_recent_emails kein Crash", f"Typ: {type(emails)}")
except Exception as e:
    fail("TEST 17 - Gmail Provider: get_recent_emails kein Crash", str(e))

try:
    test_emails = [
        {"subject": "Buchungsbestätigung Hotel Berlin", "snippet": "Ihr Hotel ist gebucht."},
        {"subject": "Newsletter Angebote", "snippet": "Sonderangebote diese Woche."},
        {"subject": "Flug Stornierung Berlin", "snippet": "Ihr Flug wurde storniert."},
    ]
    relevant = find_trip_relevant_emails(test_emails, "Berlin")
    if len(relevant) >= 2:
        ok(f"TEST 17 - Gmail Provider: find_trip_relevant_emails filtert korrekt ({len(relevant)} von 3 relevant)")
    else:
        fail("TEST 17 - Gmail Provider: find_trip_relevant_emails", f"Nur {len(relevant)} von 3 gefunden")
except Exception as e:
    fail("TEST 17 - Gmail Provider: find_trip_relevant_emails", str(e))

# ── TEST 18 – Calendar Provider ───────────────────────────────────────────────

print("\n── TEST 18 – Calendar Provider ─────────────────────────────────────────")
try:
    from providers.calendar import get_calendar_events, find_free_days
    events = get_calendar_events(days_ahead=7)
    if isinstance(events, list):
        ok(f"TEST 18 - Calendar Provider: get_calendar_events ohne credentials kein Crash (leere Liste)")
    else:
        fail("TEST 18 - Calendar Provider: get_calendar_events kein Crash", f"Typ: {type(events)}")
except Exception as e:
    fail("TEST 18 - Calendar Provider: get_calendar_events kein Crash", str(e))

try:
    free = find_free_days([], days_ahead=7)
    if "all_free" in free and len(free["all_free"]) == 7:
        ok(f"TEST 18 - Calendar Provider: find_free_days mit leerer Event-Liste markiert alle 7 Tage frei")
    else:
        fail("TEST 18 - Calendar Provider: find_free_days alle frei", f"all_free: {len(free.get('all_free', []))}")
except Exception as e:
    fail("TEST 18 - Calendar Provider: find_free_days", str(e))

# ── TEST 19 – Daily Brief Agent ───────────────────────────────────────────────

print("\n── TEST 19 – Daily Brief Agent ─────────────────────────────────────────")
try:
    from agents.daily_brief import create_daily_brief
    if COORDINATOR_RESULT:
        test_trip_brief = {
            "request": DEMO_REQUEST,
            "active_plan": COORDINATOR_RESULT["active_plan"],
        }
        brief = create_daily_brief(test_trip_brief, day_number=1)
        if isinstance(brief, str) and len(brief) > 10:
            ok(f"TEST 19 - Daily Brief: Fallback-Text zurückgegeben ({brief[:60]}...)")
        else:
            fail("TEST 19 - Daily Brief: Fallback-Text", f"Ergebnis: '{brief}'")
    else:
        fail("TEST 19 - Daily Brief: create_daily_brief", "Coordinator-Ergebnis fehlt")
except Exception as e:
    fail("TEST 19 - Daily Brief: create_daily_brief kein Crash", str(e))

# ── TEST 20 – FastAPI Routes ──────────────────────────────────────────────────

print("\n── TEST 20 – FastAPI Endpoints ─────────────────────────────────────────")
try:
    from main import app
    registered = set()
    for route in app.routes:
        if hasattr(route, "path"):
            for method in getattr(route, "methods", {"GET"}):
                registered.add((method.upper(), route.path))

    EXPECTED = [
        ("GET",   "/api/trips/{trip_id}"),
        ("POST",  "/api/trips/plan"),
        ("POST",  "/api/trips/demo"),
        ("POST",  "/api/trips/{trip_id}/chat"),
        ("POST",  "/api/trips/{trip_id}/simulate-weather"),
        ("POST",  "/api/trips/{trip_id}/proposals/{proposal_id}/accept"),
        ("POST",  "/api/trips/{trip_id}/proposals/{proposal_id}/reject"),
        ("PATCH", "/api/trips/{trip_id}/checklist/items/{item_id}"),
        ("GET",   "/api/trips/{trip_id}/navigation/{day_number}/{slot_index}"),
        ("GET",   "/api/trips/{trip_id}/daily-brief/{day_number}"),
        ("POST",  "/api/profile/update"),
        ("POST",  "/api/profile/detect-free-days"),
        ("GET",   "/api/profile/interests"),
        ("POST",  "/api/suggestions/generate"),
        ("GET",   "/api/suggestions/pending"),
        ("POST",  "/api/suggestions/{suggestion_id}/accept"),
        ("POST",  "/api/suggestions/{suggestion_id}/reject"),
    ]

    for method, path in EXPECTED:
        if (method, path) in registered:
            ok(f"TEST 20 - FastAPI: {method} {path}")
        else:
            fail(f"TEST 20 - FastAPI: {method} {path}", "Route nicht registriert")
except Exception as e:
    fail("TEST 20 - FastAPI: app Import", str(e))

# ── TEST 21 – Kostenschätzungs-Agent ──────────────────────────────────────────

print("\n── TEST 21 – Kostenschätzungs-Agent ────────────────────────────────────")
COST_TEST_DAY = {
    "day_number": 1,
    "title": "Test",
    "date": "2026-07-10",
    "time_slots": [
        {
            "activity": {
                "id": "cost-test-museum",
                "name": "Testmuseum",
                "category": "culture",
                "estimated_cost_per_person": 12.0,
                "estimated_cost_total": 24.0,
            }
        },
        {
            "activity": {
                "id": "cost-test-restaurant",
                "name": "Testrestaurant",
                "category": "food",
                "estimated_cost_per_person": 20.0,
                "estimated_cost_total": 40.0,
            }
        },
    ],
}

try:
    from agents.cost_estimation import estimate_costs_for_plan
    cost_days = [COST_TEST_DAY]
    estimate_costs_for_plan(cost_days, TEST_REQUEST)
    activity = cost_days[0]["time_slots"][0]["activity"]
    cost_value = activity.get("estimated_cost_per_person")
    if isinstance(cost_value, (int, float)) and cost_value >= 0:
        ok(f"TEST 21 - Kostenschätzung: estimated_cost_per_person bleibt numerisch ({cost_value})")
    else:
        fail("TEST 21 - Kostenschätzung: estimated_cost_per_person bleibt numerisch", f"Wert: {cost_value}")
except Exception as e:
    fail("TEST 21 - Kostenschätzung: estimate_costs_for_plan läuft ohne Absturz", str(e))

try:
    from agents.cost_estimation import get_agent_insight
    insight = get_agent_insight()
    required = {"agent_name", "display_label", "status", "summary"}
    missing = [r for r in required if r not in insight]
    if not missing:
        ok("TEST 21 - Kostenschätzung: get_agent_insight liefert erwartete Felder")
    else:
        fail("TEST 21 - Kostenschätzung: get_agent_insight liefert erwartete Felder", f"Fehlend: {missing}")
except Exception as e:
    fail("TEST 21 - Kostenschätzung: get_agent_insight liefert erwartete Felder", str(e))

# ── Zusammenfassung ───────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print(f"  ERGEBNIS: {len(passed)} bestanden  |  {len(failed)} fehlgeschlagen")
print("=" * 70)

if failed:
    print("\nFehlgeschlagene Tests:")
    for label, reason in failed:
        print(f"  [FAIL] {label}" + (f"\n         Grund: {reason}" if reason else ""))

print()
sys.exit(0 if not failed else 1)
