import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import profile_store
from datetime import date, timedelta

profile_store.init_db()
profile_store.save_interest("musik", "konzert", score=3.0, source="test")
profile_store.save_interest("kunst", "museum", score=2.0, source="test")
profile_store.save_interest("essen", "restaurant", score=2.5, source="test")
profile_store.save_past_event("Rock im Park", "musik", "2024-06-01", "test")
profile_store.save_free_day((date.today() + timedelta(days=3)).isoformat())

print("Interessen:", profile_store.get_top_interests())
print("Events:", profile_store.get_past_events())
print("Freie Tage:", profile_store.get_upcoming_free_days())

from agents.suggestion_agent import create_suggestion_for_day
result = create_suggestion_for_day((date.today() + timedelta(days=3)).isoformat(), home_city="Berlin")
print("Vorschlag:", result)
