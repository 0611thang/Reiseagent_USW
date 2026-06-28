"""
Test: Zeigt was aus Google Calendar gelesen wird und was die KI daraus macht.
Ausfuehren: python test_calendar.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()  # WICHTIG: ohne .env kein GROQ_API_KEY -> KI laeuft nicht, nur Fallback

from providers.calendar import get_calendar_events
from agents.calendar_agent import interpret_calendar, get_truly_free_days, _build_day_lines
import prompts

print("=" * 60)
print("SCHRITT 1 — Rohe Kalender-Eintraege (was Google liefert)")
print("=" * 60)

events = get_calendar_events(days_ahead=14)

if not events:
    print("Kalender nicht konfiguriert (credentials.json fehlt).")
    print("Verwende Mock-Daten fuer den Test...\n")
    from datetime import date, timedelta
    today = date.today()
    events = [
        {"summary": "Arbeit",        "start": (today + timedelta(days=1)).isoformat(), "all_day": False, "blocks_reiseagent_day": False},
        {"summary": "Arbeit",        "start": (today + timedelta(days=2)).isoformat(), "all_day": False, "blocks_reiseagent_day": False},
        {"summary": "Gym",           "start": (today + timedelta(days=3)).isoformat(), "all_day": False, "blocks_reiseagent_day": False},
        {"summary": "Arzt",          "start": (today + timedelta(days=4)).isoformat(), "all_day": False, "blocks_reiseagent_day": False},
        {"summary": "Arbeit",        "start": (today + timedelta(days=5)).isoformat(), "all_day": False, "blocks_reiseagent_day": False},
        {"summary": "",              "start": (today + timedelta(days=6)).isoformat(), "all_day": False, "blocks_reiseagent_day": False},
        {"summary": "",              "start": (today + timedelta(days=7)).isoformat(), "all_day": False, "blocks_reiseagent_day": False},
        {"summary": "Familientreffen","start": (today + timedelta(days=8)).isoformat(), "all_day": True,  "blocks_reiseagent_day": False},
        {"summary": "Arbeit",        "start": (today + timedelta(days=9)).isoformat(), "all_day": False, "blocks_reiseagent_day": False},
        {"summary": "Meeting",       "start": (today + timedelta(days=10)).isoformat(),"all_day": False, "blocks_reiseagent_day": False},
    ]
    for e in events:
        label = e["summary"] if e["summary"] else "(kein Termin)"
        ganztaegig = "ganztaegig" if e["all_day"] else "mit Uhrzeit"
        print(f"  {e['start']}  |  {label}  ({ganztaegig})")
else:
    for e in events:
        ganztaegig = "ganztaegig" if e["all_day"] else "mit Uhrzeit"
        blockiert = " [REISEAGENT-MARKER]" if e.get("blocks_reiseagent_day") else ""
        print(f"  {e['start']}  |  {e['summary']}  ({ganztaegig}){blockiert}")

print()
print("=" * 60)
print("SCHRITT 2 — Was die KI als Prompt bekommt")
print("=" * 60)

_, _, lines = _build_day_lines(events, days_ahead=14)
events_text = "\n".join(lines)
filled_prompt = prompts.fill(prompts.INTERPRET_CALENDAR, events_text=events_text)
print(filled_prompt)

print()
print("=" * 60)
print("SCHRITT 3 — KI-Interpretation (free / busy pro Tag)")
print("=" * 60)

if events:
    interpreted = interpret_calendar(events)
    if interpreted:
        for day in interpreted:
            symbol = "✓ frei  " if day["status"] == "free" else "✗ belegt"
            print(f"  {symbol}  {day['date']}  —  {day['reason']}")
    else:
        print("KI hat keine verwertbare Antwort geliefert (Fallback aktiv).")
else:
    print("Keine Eintraege — Interpretation uebersprungen.")

print()
print("=" * 60)
print("SCHRITT 4 — Ergebnis: wirklich freie Tage (gehen als Vorschlag raus)")
print("=" * 60)

free_days = get_truly_free_days(days_ahead=14)
if free_days:
    for d in free_days:
        print(f"  → {d}")
else:
    print("  Keine freien Tage gefunden.")

print()
print("Fertig.")
