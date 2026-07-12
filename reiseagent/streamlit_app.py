import sys
import os
from datetime import datetime, date, time, timedelta, time as datetime_time
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import folium
from streamlit_folium import st_folium

import store
import profile_store
import ui_service
store.init_db()
from agents import coordinator, replanning
from providers.places import get_places
from providers.calendar import sync_full_plan_to_calendar
from providers.telegram import send_plan_update

st.set_page_config(
    page_title="Reiseplanungs-Agent",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
* { font-family: system-ui, -apple-system, sans-serif; }
.stApp { background: #f5f6fa; }
div[data-testid="stVerticalBlock"] { gap: 0; }
.stButton button { border-radius: 8px; font-weight: 500; }
.card {
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    padding: 16px;
    margin-bottom: 12px;
}
.card-title {
    font-size: 15px;
    font-weight: 700;
    color: #111;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.pill {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 99px;
    font-size: 12px;
    font-weight: 600;
}
.pill-green  { background: #dcfce7; color: #166534; }
.pill-blue   { background: #dbeafe; color: #1d4ed8; }
.pill-orange { background: #ffedd5; color: #c2410c; }
.pill-gray   { background: #f3f4f6; color: #4b5563; }
.pill-purple { background: #ede9fe; color: #6d28d9; }
.activity-card {
    border: 1px solid #f0f0f0;
    border-radius: 10px;
    padding: 10px 12px;
    margin-bottom: 8px;
    display: flex;
    gap: 12px;
    background: #fff;
}
.time-stripe { min-width: 48px; }
.time-start  { font-size: 13px; font-weight: 700; color: #111; }
.time-end    { font-size: 11px; color: #9ca3af; margin-top: 2px; }
.act-body    { flex: 1; }
.act-header  { display: flex; justify-content: space-between; align-items: flex-start; }
.act-name    { font-size: 14px; font-weight: 700; color: #111; }
.act-desc    { font-size: 12px; color: #6b7280; margin-top: 3px; }
.act-meta    { font-size: 11px; color: #9ca3af; margin-top: 6px; }
.day-header  {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid #f0f0f0;
    margin-bottom: 10px;
    margin-top: 6px;
}
.day-title   { font-size: 14px; font-weight: 700; color: #111; }
.day-weather { font-size: 12px; color: #6b7280; }
.budget-hero {
    background: #2563eb;
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 12px;
    color: #fff;
}
.budget-label  { font-size: 11px; opacity: 0.8; margin-bottom: 2px; }
.budget-amount { font-size: 28px; font-weight: 800; line-height: 1.1; }
.budget-sub    { font-size: 12px; opacity: 0.7; margin-top: 4px; }
.budget-row {
    display: flex;
    justify-content: space-between;
    font-size: 13px;
    padding: 5px 0;
    border-bottom: 1px solid #f3f4f6;
}
.cat-bar-label { display: flex; justify-content: space-between; font-size: 12px; color: #374151; margin-top: 8px; }
.cat-bar-bg    { background: #f3f4f6; border-radius: 99px; height: 6px; margin: 3px 0 2px; }
.cat-bar-fill  { background: #2563eb; border-radius: 99px; height: 6px; }
.route-item { display: flex; gap: 10px; align-items: flex-start; margin-bottom: 10px; }
.route-num  {
    min-width: 24px; height: 24px; border-radius: 50%;
    background: #2563eb; color: #fff;
    font-size: 12px; font-weight: 700;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
}
.route-name { font-size: 13px; font-weight: 700; color: #111; }
.route-sub  { font-size: 11px; color: #9ca3af; }
.chat-msgs  { max-height: 320px; overflow-y: auto; margin-bottom: 10px; }
.assistant-card {
    background: #fff;
    border: 1px solid #bfdbfe;
    border-radius: 12px;
    box-shadow: 0 4px 14px rgba(37, 99, 235, 0.10);
    padding: 18px;
    margin-bottom: 12px;
}
.assistant-title { font-size: 20px; font-weight: 750; color: #111827; margin-bottom: 4px; }
.assistant-subtitle { font-size: 12px; color: #4b5563; margin-bottom: 12px; }
.chat-user  {
    background: #2563eb; color: #fff;
    border-radius: 10px 10px 2px 10px;
    padding: 7px 11px; margin: 4px 0;
    font-size: 13px; text-align: right;
}
.chat-asst  {
    background: #f3f4f6; color: #111;
    border-radius: 10px 10px 10px 2px;
    padding: 7px 11px; margin: 4px 0;
    font-size: 13px;
}
.chat-hint  { font-size: 12px; color: #9ca3af; margin-bottom: 8px; }
.insight-row {
    display: flex; align-items: flex-start;
    gap: 8px; padding: 6px 0;
    border-bottom: 1px solid #f3f4f6;
}
.insight-num {
    min-width: 22px; height: 22px; border-radius: 50%;
    background: #2563eb; color: #fff;
    font-size: 11px; font-weight: 700;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0; margin-top: 1px;
}
.insight-body { flex: 1; font-size: 13px; }
.insight-name { font-weight: 600; color: #111; }
.insight-sum  { font-size: 11px; color: #6b7280; }
.proposal-banner-div {
    background: #fffbeb;
    border: 1px solid #fcd34d;
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 12px;
}
.header-h1  { font-size: 24px; font-weight: 800; color: #111; margin: 0 0 2px; }
.header-sub { font-size: 13px; color: #6b7280; margin: 0; }
.sugg-card  {
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 14px; margin-bottom: 10px;
}
.sugg-date  { font-size: 12px; color: #6b7280; margin-bottom: 4px; }
.sugg-title { font-size: 15px; font-weight: 700; color: #111; margin-bottom: 6px; }
.sugg-desc  { font-size: 13px; color: #374151; margin-bottom: 6px; }
.sugg-act   { font-size: 13px; color: #374151; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────── helpers ────────────────────────────────────────

def _esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _weather_icon(condition: str) -> str:
    return {"sunny": "☀️", "cloudy": "☁️", "rain": "🌧️", "storm": "⛈️", "snow": "❄️"}.get(condition, "🌤️")


def _cat_badge(cat: str) -> str:
    m = {
        "sightseeing": ("Sightseeing", "pill-blue"),
        "museum":      ("Museum",      "pill-purple"),
        "restaurant":  ("Restaurant",  "pill-orange"),
        "transport":   ("Transport",   "pill-gray"),
        "break":       ("Pause",       "pill-green"),
        "walk":        ("Spaziergang", "pill-green"),
        "activity":    ("Aktivität",   "pill-blue"),
    }
    label, cls = m.get(cat, (cat.capitalize(), "pill-gray"))
    return f'<span class="pill {cls}">{label}</span>'


def _status_pill(status: str) -> str:
    m = {
        "completed": ("completed", "pill-green"),
        "running":   ("running",   "pill-orange"),
        "pending":   ("pending",   "pill-gray"),
        "failed":    ("failed",    "pill-gray"),
    }
    label, cls = m.get(status, (status, "pill-gray"))
    return f'<span class="pill {cls}">{label}</span>'


# ─────────────────────────── session / data ──────────────────────────────────

def _format_day_label(day: dict) -> str:
    date_text = day.get("date", "")
    if date_text:
        try:
            date_text = datetime.fromisoformat(date_text).strftime("%d.%m.%Y")
        except ValueError:
            pass
    if date_text:
        return f"Tag {day.get('day_number')} – {date_text}"
    return f"Tag {day.get('day_number')}"


def init_session():
    if "trip_id" not in st.session_state:
        st.session_state.trip_id = None
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "status_messages" not in st.session_state:
        st.session_state.status_messages = []
    if "last_suggestions" not in st.session_state:
        st.session_state.last_suggestions = []
    if "last_suggestion_context" not in st.session_state:
        st.session_state.last_suggestion_context = {}
    if "pretrip_chat_messages" not in st.session_state:
        st.session_state.pretrip_chat_messages = []
    if "background_refresh_at" not in st.session_state:
        st.session_state.background_refresh_at = None
    if "confirm_delete_trip_id" not in st.session_state:
        st.session_state.confirm_delete_trip_id = None
    if "plan_view_mode" not in st.session_state:
        st.session_state.plan_view_mode = "Detail"
    if "trip_form_travel_type" not in st.session_state:
        st.session_state.trip_form_travel_type = "solo"
    if "trip_form_previous_travel_type" not in st.session_state:
        st.session_state.trip_form_previous_travel_type = "solo"
    if "trip_form_people" not in st.session_state:
        st.session_state.trip_form_people = 1
    if "confirm_reset_bank" not in st.session_state:
        st.session_state.confirm_reset_bank = False


def add_status(message: str):
    if not message:
        return
    if st.session_state.status_messages and st.session_state.status_messages[-1] == message:
        return
    st.session_state.status_messages.append(message)
    st.session_state.status_messages = st.session_state.status_messages[-20:]


def render_status_messages():
    messages = []
    for message in st.session_state.status_messages:
        if not messages or messages[-1] != message:
            messages.append(message)
    st.session_state.status_messages = messages[-20:]
    messages = st.session_state.status_messages
    if not messages:
        return

    st.info(messages[-1])
    older_messages = messages[:-1]
    if older_messages:
        with st.expander("Ältere Benachrichtigungen anzeigen"):
            for message in reversed(older_messages):
                st.caption(message)


def sync_plan_and_notify(plan: dict, reason: str = "Plan aktualisiert", trip_id=None) -> dict:
    calendar_result = sync_full_plan_to_calendar(plan, trip_id)
    calendar_ok = calendar_result.get("updated", False)
    telegram_ok = send_plan_update(plan, calendar_synced=calendar_ok)

    parts = []
    if calendar_ok:
        parts.append("Kalender synchronisiert.")
    else:
        parts.append("Kalender nicht eingerichtet oder nicht erreichbar.")
    if telegram_ok:
        parts.append("Telegram gesendet.")
    add_status(f"{reason}: {' '.join(parts)}")

    return calendar_result


def refresh_profile_in_background():
    """Aktualisiert Profil und freie Tage höchstens alle 30 Minuten."""
    last_refresh = st.session_state.background_refresh_at
    if last_refresh and (datetime.now() - last_refresh).total_seconds() < 1800:
        return

    st.session_state.background_refresh_at = datetime.now()

    if os.getenv("IMAP_USER") and os.getenv("IMAP_PASSWORD"):
        try:
            from providers.imap_mail import get_recent_emails
            from agents.profile_learner import run_profile_update
            run_profile_update(imap_emails=get_recent_emails(limit=20))
        except Exception as exc:
            print(f"[profile] Hintergrundaktualisierung übersprungen: {type(exc).__name__}")

    token_path = os.path.join(os.path.dirname(__file__), "calendar_token.json")
    if os.path.exists(token_path):
        try:
            from agents.free_time_detector import detect_and_save_free_days
            detect_and_save_free_days(days_ahead=14)
        except Exception as exc:
            print(f"[calendar] Freie Tage konnten nicht aktualisiert werden: {type(exc).__name__}")


def get_current_trip() -> dict | None:
    if not st.session_state.trip_id:
        return None
    trip = store.get_trip(st.session_state.trip_id)
    if not trip:
        return None

    flight = trip.get("flight_updates") or {}
    invalid_sources = ["mock_after_api_error", "api_unavailable", "api_error"]
    if flight.get("source") in invalid_sources and not trip.get("invalid_flight_slots_removed"):
        plan = trip.get("active_plan") or {}
        removed = 0
        for day in plan.get("days", []):
            slots = day.get("time_slots", [])
            valid_slots = [
                slot for slot in slots
                if slot.get("activity", {}).get("source") != "flight"
            ]
            removed += len(slots) - len(valid_slots)
            day["time_slots"] = valid_slots
            if day.get("day_number") == 1 and removed:
                day["arrival_note"] = "Flugdaten konnten nicht bestätigt werden. Bitte Flugdatum prüfen und später neu laden."
                day["title"] = "Ankunftstag – Flugdaten ausstehend"

        insights = trip.get("agent_insights", [])
        for insight in insights:
            if insight.get("agent_name") == "flight_agent":
                insight["status"] = "failed"
                insight["summary"] = "Flugdaten konnten nicht bestätigt werden; simulierte Ankunftszeiten wurden entfernt."

        trip["invalid_flight_slots_removed"] = True
        if removed:
            trip = store.update_trip(trip["id"], {
                "active_plan": plan,
                "agent_insights": insights,
                "invalid_flight_slots_removed": True,
            })
    return trip


def load_demo_trip():
    trip_id, active_plan = ui_service.create_demo_trip()
    sync_plan_and_notify(active_plan, "Demo-Reise erstellt", trip_id)
    st.session_state.trip_id = trip_id
    st.session_state.chat_messages = []


def simulate_rain_day2():
    trip_id = st.session_state.trip_id
    if not trip_id:
        return
    trip = store.get_trip(trip_id)
    if not trip or not trip.get("active_plan"):
        return
    weather_event = {
        "day_number": 2,
        "condition": "rain",
        "severity": "medium",
        "description": "Starkregen erwartet",
    }
    all_activities = get_places(
        trip["request"]["destination"],
        trip["request"].get("interests", []),
    )
    proposal = replanning.create_replanning_proposal(trip, weather_event, all_activities)
    trip["proposals"].append(proposal)
    insight = replanning.get_agent_insight(len(proposal["changes"]))
    trip["agent_insights"].append(insight)
    store.update_trip(trip_id, {
        "proposals": trip["proposals"],
        "agent_insights": trip["agent_insights"],
    })
    send_plan_update(trip["active_plan"], warning_text="Wetterwarnung erkannt: Regen an Tag 2.")
    add_status("Wetterwarnung erkannt und Telegram optional benachrichtigt.")


# ─────────────────────────── column renderers ────────────────────────────────

def render_left_col(trip: dict):
    active_plan = trip.get("active_plan")

    # Chat messages HTML
    msgs_html = ""
    for msg in st.session_state.chat_messages:
        if msg["role"] == "user":
            msg_style = "background:#2563eb;color:#fff;border-radius:10px 10px 2px 10px;padding:7px 11px;margin:4px 0;font-size:13px;text-align:right;"
        else:
            msg_style = "background:#f3f4f6;color:#111;border-radius:10px 10px 10px 2px;padding:7px 11px;margin:4px 0;font-size:13px;"
        msgs_html += f'<div style="{msg_style}">{_esc(msg["content"])}</div>'

    hint = "" if msgs_html else '<div style="font-size:12px;color:#9ca3af;margin-bottom:8px;">Stell eine Frage zu deiner Reise, z.B. nach Budget, Wetter oder Aktivitäten.</div>'

    html = (
        '<div class="assistant-card">'
        '<div class="assistant-title">Reiseassistent</div>'
        '<div class="assistant-subtitle">Fragen stellen oder den aktuellen Reiseplan direkt anpassen.</div>'
        f'<div style="min-height:180px;max-height:420px;overflow-y:auto;margin-bottom:10px;">{hint}{msgs_html}</div>'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)

    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_input("", placeholder="Nachricht eingeben...", label_visibility="collapsed")
        sent = st.form_submit_button("Senden", use_container_width=True, type="primary")
        if sent and user_input.strip() and active_plan:
            user_message = {"role": "user", "content": user_input.strip()}
            st.session_state.chat_messages.append(user_message)
            trip["chat_messages"] = list(st.session_state.chat_messages)
            result = coordinator.handle_chat_message(trip, user_input.strip())
            assistant_message = {"role": "assistant", "content": result["message"]}
            st.session_state.chat_messages.append(assistant_message)
            if "Kalender wurde" in result["message"] or "Kalender wurden" in result["message"]:
                add_status("Kalender synchronisiert.")
            elif "Kalender konnte nicht aktualisiert werden" in result["message"]:
                add_status("Kalender nicht eingerichtet oder nicht erreichbar.")
            st.session_state.last_suggestions = trip.get("last_suggestions", [])
            st.session_state.last_suggestion_context = trip.get("last_suggestion_context", {})
            trip["chat_messages"] = list(st.session_state.chat_messages)
            store.update_trip(trip["id"], {
                "chat_messages": trip["chat_messages"],
                "active_plan": trip.get("active_plan"),
                "agent_insights": trip.get("agent_insights", []),
                "last_suggestions": trip.get("last_suggestions", []),
                "last_suggestion_context": trip.get("last_suggestion_context", {}),
            })
            st.rerun()

    # Vorschläge werden im Chat und direkt an den Aktivitätskarten angeboten.
    if False and active_plan:
        days = active_plan.get("days", [])
        if days:
            st.caption("Neue Alternativen suchen, ohne den Plan direkt zu ändern.")
            day_labels = [f"Tag {day.get('day_number')}" for day in days]
            selected_day_label = st.selectbox(
                "Tag für neue Vorschläge",
                day_labels,
                key="alternative_day_select",
            )
            section = st.selectbox(
                "Tagesabschnitt",
                ["Vormittag", "Mittag", "Nachmittag", "Abend"],
                key="alternative_section_select",
            )
            custom_time = st.selectbox(
                "Uhrzeit",
                ["09 Uhr", "12 Uhr", "14 Uhr", "19 Uhr"],
                key="alternative_time_select",
            )
            section_times = {
                "Vormittag": "9 Uhr",
                "Mittag": "12 Uhr",
                "Nachmittag": "14 Uhr",
                "Abend": "19 Uhr",
            }
            if st.button("Neue Vorschläge generieren", use_container_width=True):
                day_number = selected_day_label.replace("Tag ", "")
                time_text = custom_time or section_times.get(section, "12 Uhr")
                prompt = f"gib mir Vorschläge für Tag {day_number} um {time_text}"
                st.session_state.chat_messages.append({"role": "user", "content": prompt})
                trip["chat_messages"] = list(st.session_state.chat_messages)
                result = coordinator.handle_chat_message(trip, prompt)
                st.session_state.chat_messages.append({"role": "assistant", "content": result["message"]})
                st.session_state.last_suggestions = trip.get("last_suggestions", [])
                st.session_state.last_suggestion_context = trip.get("last_suggestion_context", {})
                trip["chat_messages"] = list(st.session_state.chat_messages)
                add_status("Vorschläge generiert.")
                store.update_trip(trip["id"], {
                    "chat_messages": trip["chat_messages"],
                    "active_plan": trip.get("active_plan"),
                    "agent_insights": trip.get("agent_insights", []),
                    "last_suggestions": trip.get("last_suggestions", []),
                    "last_suggestion_context": trip.get("last_suggestion_context", {}),
                })
                st.rerun()

            suggestions = (trip.get("last_suggestions") or st.session_state.last_suggestions)[:5]
            if suggestions:
                st.markdown("**Letzte Vorschläge**")
                for index, activity in enumerate(suggestions, start=1):
                    name = activity.get("name", "Vorschlag")
                    category = activity.get("category", "activity")
                    cols = st.columns([3, 2])
                    with cols[0]:
                        st.caption(f"{index}. {name} ({category})")
                    with cols[1]:
                        if st.button("Vorschlag übernehmen", key=f"accept_chat_suggestion_{index}", use_container_width=True):
                            prompt = f"nimm Vorschlag {index}"
                            st.session_state.chat_messages.append({"role": "user", "content": prompt})
                            trip["chat_messages"] = list(st.session_state.chat_messages)
                            result = coordinator.handle_chat_message(trip, prompt)
                            st.session_state.chat_messages.append({"role": "assistant", "content": result["message"]})
                            st.session_state.last_suggestions = trip.get("last_suggestions", [])
                            st.session_state.last_suggestion_context = trip.get("last_suggestion_context", {})
                            trip["chat_messages"] = list(st.session_state.chat_messages)
                            add_status("Vorschlag übernommen.")
                            store.update_trip(trip["id"], {
                                "chat_messages": trip["chat_messages"],
                                "active_plan": trip.get("active_plan"),
                                "agent_insights": trip.get("agent_insights", []),
                                "last_suggestions": trip.get("last_suggestions", []),
                                "last_suggestion_context": trip.get("last_suggestion_context", {}),
                            })
                            st.rerun()

    render_trip_overview(compact=True)

    # Agent Insights
    insights = trip.get("agent_insights", [])
    if insights:
        rows_html = ""
        for i, ins in enumerate(insights, 1):
            label = _esc(ins.get("display_label", ins.get("agent_name", "Agent")))
            summary = _esc(ins.get("summary", ""))
            pill = _status_pill(ins.get("status", ""))
            rows_html += f"""
            <div style="display:flex;align-items:flex-start;gap:8px;padding:6px 0;border-bottom:1px solid #f3f4f6;">
                <div style="min-width:22px;height:22px;border-radius:50%;background:#2563eb;color:#fff;font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:1px;">{i}</div>
                <div style="flex:1;font-size:13px;">
                    <div style="font-weight:600;color:#111;">{label}</div>
                    <div style="font-size:11px;color:#6b7280;">{summary}</div>
                </div>
                {pill}
            </div>"""
        html = (
            '<div style="background:#fff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.08);padding:16px;margin-bottom:12px;">'
            '<div style="font-size:15px;font-weight:700;color:#111;margin-bottom:10px;">Agent Insights</div>'
            f'{rows_html}'
            '</div>'
        )
        st.markdown(html, unsafe_allow_html=True)


def _activity_action_context(trip: dict):
    plan = trip.get("active_plan", {})
    cache_key = f"all_activities_{trip['id']}"
    if cache_key not in st.session_state:
        request = plan.get("request") or trip.get("request", {})
        destination = request.get("destination", "")
        st.session_state[cache_key] = get_places(destination, request) if destination else []

    used_ids = set()
    for day in plan.get("days", []):
        for slot in day.get("time_slots", []):
            used_ids.add(slot.get("activity", {}).get("id"))
    return st.session_state[cache_key], used_ids


def _render_inline_activity_actions(trip: dict, day: dict, slot: dict, all_activities: list, used_ids: set):
    activity = slot.get("activity", {})
    name = activity.get("name", "Aktivität")
    category = activity.get("category", "activity")
    slot_id = slot.get("id")
    day_number = day.get("day_number")

    time_col, save_col = st.columns([2, 1])
    with time_col:
        new_start = st.time_input(
            "Startzeit",
            value=_time_input_value(slot.get("start_time", "09:00")),
            step=900,
            key=f"inline_time_{slot_id}",
        )
    with save_col:
        st.caption("Zeitplan")
        if st.button("Zeit übernehmen", key=f"inline_save_{slot_id}", use_container_width=True):
            old_start = slot.get("start_time", "09:00")
            new_time = new_start.strftime("%H:%M")
            prompt = (
                f"verschiebe {name} von {old_start} Uhr auf {new_time} Uhr an Tag {day_number} "
                "und schiebe alles danach nach hinten"
            )
            result = _send_chat_command_from_ui(trip, prompt)
            add_status(result.get("message", "Zeitplan aktualisiert."))
            st.rerun()

    delete_col, alt_col, ai_col = st.columns(3)
    with delete_col:
        if st.button("Löschen", key=f"inline_delete_{slot_id}", use_container_width=True):
            result = _send_chat_command_from_ui(trip, f"lösche {name} an Tag {day_number}")
            add_status(result.get("message", "Aktivität gelöscht."))
            st.rerun()
    with alt_col:
        if st.button("Alternative", key=f"inline_alt_{slot_id}", use_container_width=True):
            st.session_state[f"show_alt_{slot_id}"] = not st.session_state.get(f"show_alt_{slot_id}", False)
            st.session_state[f"show_ai_{slot_id}"] = False
    with ai_col:
        if st.button("KI-Alternative", key=f"inline_ai_{slot_id}", use_container_width=True):
            st.session_state[f"show_ai_{slot_id}"] = not st.session_state.get(f"show_ai_{slot_id}", False)
            st.session_state[f"show_alt_{slot_id}"] = False

    if st.session_state.get(f"show_alt_{slot_id}", False):
        candidates = [
            item for item in all_activities
            if item.get("category") == category and item.get("id") not in used_ids
        ][:3]
        if not candidates:
            st.info("Keine weitere Alternative in dieser Kategorie gefunden.")
        for candidate in candidates:
            info_col, button_col = st.columns([3, 1])
            info_col.caption(f"{candidate.get('name')} · {str(candidate.get('description', ''))[:80]}")
            if button_col.button("Wählen", key=f"inline_pick_{slot_id}_{candidate.get('id')}"):
                result = _send_chat_command_from_ui(
                    trip,
                    f"ersetze {name} durch {candidate.get('name')} an Tag {day_number}",
                )
                add_status(result.get("message", "Alternative übernommen."))
                st.session_state[f"show_alt_{slot_id}"] = False
                st.rerun()

    if st.session_state.get(f"show_ai_{slot_id}", False):
        interests = profile_store.get_top_interests(limit=5)
        keywords = [item.get("keyword", "").lower() for item in interests]
        ranked = []
        for candidate in all_activities:
            if candidate.get("id") in used_ids:
                continue
            searchable = " ".join(candidate.get("tags", []) + [candidate.get("category", "")]).lower()
            hits = sum(1 for keyword in keywords if keyword and keyword in searchable)
            if hits:
                ranked.append((hits, candidate))
        ranked.sort(key=lambda item: item[0], reverse=True)
        candidates = [candidate for _, candidate in ranked[:3]]
        if not interests:
            st.info("Noch keine Profilinteressen bekannt. Nutze zunächst normale Alternativen.")
        elif not candidates:
            st.info("Für dein Profil wurde gerade keine weitere Alternative gefunden.")
        for candidate in candidates:
            info_col, button_col = st.columns([3, 1])
            info_col.caption(f"{candidate.get('name')} · passend zu deinem Profil")
            if button_col.button("Wählen", key=f"inline_ai_pick_{slot_id}_{candidate.get('id')}"):
                result = _send_chat_command_from_ui(
                    trip,
                    f"ersetze {name} durch {candidate.get('name')} an Tag {day_number}",
                )
                add_status(result.get("message", "KI-Alternative übernommen."))
                st.session_state[f"show_ai_{slot_id}"] = False
                st.rerun()


def _render_plan_day_header(day: dict):
    weather = day.get("weather") or {}
    st.markdown(f"**{_format_day_label(day)} – {day.get('title', '')}**")
    if weather.get("description"):
        st.caption(f"{_weather_icon(weather.get('condition', ''))} {weather.get('description')}")
    if day.get("arrival_note"):
        st.info(day["arrival_note"])


def _render_edit_expander(trip: dict, day: dict, slot: dict, all_activities: list, used_ids: set):
    with st.expander("Bearbeiten"):
        _render_inline_activity_actions(trip, day, slot, all_activities, used_ids)


def _render_detail_plan(trip: dict, days: list, all_activities: list, used_ids: set):
    for day in days:
        _render_plan_day_header(day)
        slots = day.get("time_slots", [])
        if not slots:
            st.info("Für diesen Tag ist noch kein Programmpunkt geplant.")

        for slot in slots:
            activity = slot.get("activity", {})
            with st.container(border=True):
                time_col, content_col = st.columns([1, 4])
                with time_col:
                    st.markdown(f"**{slot.get('start_time', '')}**")
                    st.caption(slot.get("end_time", ""))
                with content_col:
                    st.markdown(f"**{activity.get('name', 'Aktivität')}**")
                    st.caption(activity.get("description", ""))
                    category = activity.get("category", "Aktivität")
                    cost = float(activity.get("estimated_cost_total") or 0)
                    travel = slot.get("travel_to_next_minutes")
                    meta = [category, f"{cost:.0f} EUR" if cost else "kostenlos"]
                    if travel:
                        meta.append(f"{travel} Min. bis zum nächsten Ziel")
                    st.caption(" · ".join(meta))
                _render_edit_expander(trip, day, slot, all_activities, used_ids)


def _render_compact_plan(trip: dict, days: list, all_activities: list, used_ids: set):
    for day in days:
        _render_plan_day_header(day)
        for slot in day.get("time_slots", []):
            activity = slot.get("activity", {})
            with st.container(border=True):
                time_col, name_col, category_col = st.columns([1.3, 3.5, 1.5])
                time_col.markdown(f"**{slot.get('start_time')}–{slot.get('end_time')}**")
                name_col.markdown(activity.get("name", "Aktivität"))
                category_col.caption(activity.get("category", "Aktivität"))
                _render_edit_expander(trip, day, slot, all_activities, used_ids)


def _render_calendar_plan(trip: dict, days: list, all_activities: list, used_ids: set):
    for day in days:
        with st.expander(f"{_format_day_label(day)} – {day.get('title', '')}", expanded=True):
            if day.get("arrival_note"):
                st.info(day["arrival_note"])
            for slot in day.get("time_slots", []):
                activity = slot.get("activity", {})
                time_col, block_col = st.columns([1, 5])
                with time_col:
                    st.markdown(f"**{slot.get('start_time')}**")
                    st.caption(slot.get("end_time", ""))
                with block_col:
                    with st.container(border=True):
                        st.markdown(f"**{activity.get('name', 'Aktivität')}**")
                        st.caption(activity.get("category", "Aktivität"))
                        _render_edit_expander(trip, day, slot, all_activities, used_ids)


def render_interactive_plan(trip: dict):
    plan = trip.get("active_plan", {})
    days = plan.get("days", [])
    request = plan.get("request") or trip.get("request", {})
    destination = request.get("destination", "")
    all_activities, used_ids = _activity_action_context(trip)

    title_col, status_col = st.columns([4, 1])
    title_col.markdown("### Tagesplan")
    status_col.caption("Aktiver Plan")
    st.caption(f"{len(days)} Tage für {destination}")
    st.radio(
        "Ansicht",
        ["Detail", "Kompakt", "Kalender"],
        horizontal=True,
        key="plan_view_mode",
    )

    if st.session_state.plan_view_mode == "Kompakt":
        _render_compact_plan(trip, days, all_activities, used_ids)
    elif st.session_state.plan_view_mode == "Kalender":
        _render_calendar_plan(trip, days, all_activities, used_ids)
    else:
        _render_detail_plan(trip, days, all_activities, used_ids)


def render_middle_col(plan: dict):
    days = plan.get("days", [])
    req = plan.get("request", {})
    dest = _esc(req.get("destination", ""))
    n_days = len(days)

    content_html = ""
    for day in days:
        weather = day.get("weather", {})
        w_str = ""
        if weather:
            icon = _weather_icon(weather.get("condition", ""))
            w_str = f"{icon} {_esc(weather.get('description', ''))}"
            if weather.get("affects_outdoor_activities"):
                w_str += " ⚠️"

        content_html += f"""
        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #f0f0f0;margin-bottom:10px;margin-top:6px;">
            <div style="font-size:14px;font-weight:700;color:#111;">{_esc(_format_day_label(day))} – {_esc(day.get('title', ''))}</div>
            <div style="font-size:12px;color:#6b7280;">{w_str}</div>
        </div>"""

        for slot in day.get("time_slots", []):
            act = slot["activity"]
            badge = _cat_badge(act.get("category", ""))
            desc = _esc(act.get("description", ""))
            loc = act.get("location", {})
            area = _esc(loc.get("area", ""))
            score = act.get("score")
            score_str = f"{score['overall_score']:.0%}" if score else "–"
            cost = act.get("estimated_cost_total", 0.0)
            cost_str = f"{cost:.0f} €" if cost > 0 else "Kostenlos"
            indoor = _esc(act.get("indoor_outdoor", ""))
            duration = act.get("duration_minutes", "")
            meta_parts = [cost_str]
            if indoor:
                meta_parts.append(indoor)
            if duration:
                meta_parts.append(f"{duration} min")
            meta_parts.append(f"Score {score_str}")

            content_html += f"""
            <div style="border:1px solid #f0f0f0;border-radius:10px;padding:10px 12px;margin-bottom:8px;background:#fff;display:flex;gap:12px;">
                <div style="min-width:48px;flex-shrink:0;">
                    <div style="font-size:13px;font-weight:700;color:#111;">{_esc(slot.get('start_time', ''))}</div>
                    <div style="font-size:11px;color:#9ca3af;margin-top:2px;">{_esc(slot.get('end_time', ''))}</div>
                </div>
                <div style="flex:1;min-width:0;">
                    <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                        <div style="font-size:14px;font-weight:700;color:#111;">{_esc(act['name'])}</div>
                        {badge}
                    </div>
                    <div style="font-size:12px;color:#6b7280;margin-top:3px;">{desc}{(' · ' + area) if area else ''}</div>
                    <div style="font-size:11px;color:#9ca3af;margin-top:6px;">{' · '.join(meta_parts)}</div>
                </div>
            </div>"""

    header = (
        '<div style="font-size:15px;font-weight:700;color:#111;margin-bottom:10px;'
        'display:flex;align-items:center;justify-content:space-between;">'
        'Tagesplan'
        '<span style="background:#dcfce7;color:#166534;padding:2px 10px;border-radius:99px;font-size:12px;font-weight:600;">active</span>'
        '</div>'
    )
    subtitle = f'<div style="font-size:13px;color:#6b7280;margin-bottom:10px;">{n_days} Tage f&#252;r {dest}</div>'
    html = (
        '<div style="background:#fff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.08);'
        'padding:16px;margin-bottom:12px;max-height:76vh;overflow-y:auto;">'
        + header + subtitle + content_html +
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def _flight_airport_label(value) -> str:
    if isinstance(value, dict):
        name = value.get("name") or ""
        code = value.get("iata") or value.get("icao") or ""
        if name and code:
            return f"{name} ({code})"
        return name or code or ""
    return str(value or "")


def _flight_time_label(value) -> str:
    if not value:
        return "Nicht verfügbar"
    text = str(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%H:%M")
    except ValueError:
        return text


def render_flight_panel(trip: dict):
    request = trip.get("request", {})
    flight_number = request.get("flight_number")
    if not flight_number:
        return

    details = trip.get("flight_updates") or {}
    number = details.get("flight_number") or flight_number
    source = str(details.get("source", ""))
    api_unavailable = source in ["mock_after_api_error", "api_unavailable", "api_error"]

    if api_unavailable:
        st.error(
            "Echte Flugroute und Uhrzeiten konnten nicht geladen werden."
        )

    with st.expander("Technische Flug-API-Details"):
        st.json({
            "source": details.get("source"),
            "error_reason": details.get("error_reason"),
            "message": details.get("message"),
            "error": details.get("error"),
            "flight_number": details.get("flight_number"),
        })

    return

    origin = _flight_airport_label(details.get("origin_airport"))
    destination = _flight_airport_label(details.get("destination_airport"))
    dep_scheduled = _flight_time_label(details.get("scheduled_departure"))
    dep_current = _flight_time_label(details.get("actual_departure") or details.get("estimated_departure"))
    scheduled = _flight_time_label(details.get("scheduled_arrival"))
    current = _flight_time_label(details.get("actual_arrival") or details.get("estimated_arrival"))
    raw_status = str(details.get("status") or "unknown").lower()
    status_labels = {
        "scheduled": "Planmäßig",
        "active": "Unterwegs",
        "landed": "Gelandet",
        "delayed": "Verspätet",
        "cancelled": "Gestrichen",
        "canceled": "Gestrichen",
        "diverted": "Umgeleitet",
        "unknown": "Unbekannt",
    }
    status = status_labels.get(raw_status, raw_status.capitalize())
    try:
        delay = int(float(details.get("arrival_delay_minutes") or details.get("delay_minutes") or 0))
    except (TypeError, ValueError):
        delay = 0
    if delay > 0 and raw_status in ["scheduled", "delayed"]:
        status = f"Verspätet ({delay} Min.)"

    simulation = ""
    if source.startswith("mock"):
        simulation = '<div style="margin-top:8px;color:#92400e;font-size:12px;">Flugmonitoring simuliert</div>'

    if origin and destination:
        route_html = f"<strong>Route:</strong> {_esc(origin)} &rarr; {_esc(destination)}<br>"
    else:
        route_html = "<strong>Route:</strong> Noch nicht verfügbar<br>"

    st.markdown(
        f"""
        <div class="card">
            <div class="card-title">Flug { _esc(number) }</div>
            <div style="font-size:13px;color:#374151;line-height:1.7;">
                {route_html}
                <strong>Geplanter Abflug:</strong> {_esc(dep_scheduled)} &nbsp;|&nbsp;
                <strong>Aktueller Abflug:</strong> {_esc(dep_current)}<br>
                <strong>Geplante Ankunft:</strong> {_esc(scheduled)} &nbsp;|&nbsp;
                <strong>Aktuelle Ankunft:</strong> {_esc(current)}<br>
                <strong>Status:</strong> {_esc(status)}
            </div>
            {simulation}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _time_input_value(value: str) -> datetime_time:
    try:
        hour, minute = value.split(":")
        return datetime_time(int(hour), int(minute))
    except (AttributeError, TypeError, ValueError):
        return datetime_time(9, 0)


def render_plan_actions(trip: dict):
    plan = trip.get("active_plan", {})
    days = plan.get("days", [])
    if not days:
        return

    st.markdown("---")
    st.markdown("### Plan bearbeiten")

    # Aktivitäten für Alternativen einmalig laden und cachen
    cache_key = f"all_activities_{trip['id']}"
    if cache_key not in st.session_state:
        req = plan.get("request", {})
        dest = req.get("destination", "")
        st.session_state[cache_key] = get_places(dest, req) if dest else []

    all_activities = st.session_state[cache_key]

    # Alle bereits im Plan genutzten IDs sammeln (für Alternativen-Filter)
    used_ids = set()
    for day in days:
        for slot in day.get("time_slots", []):
            used_ids.add(slot["activity"].get("id"))

    for day in days:
        st.markdown(f"**{_format_day_label(day)} – {day.get('title', '')}**")

        for slot in day.get("time_slots", []):
            activity = slot.get("activity", {})
            name = activity.get("name", "Aktivität")
            slot_id = slot.get("id")
            day_num = day.get("day_number")
            category = activity.get("category", "")

            col_time, col_name, col_del, col_alt, col_ai = st.columns([1.3, 3, 0.6, 0.8, 1.0])

            with col_time:
                new_start = st.time_input(
                    "Zeit",
                    value=_time_input_value(slot.get("start_time", "09:00")),
                    step=900,
                    key=f"c3_time_{slot_id}",
                    label_visibility="collapsed",
                )
                if st.button("✓ Zeit", key=f"c3_save_{slot_id}", use_container_width=True):
                    prompt = f"plane {name} auf {new_start.strftime('%H:%M')} Uhr an Tag {day_num}"
                    _send_chat_command_from_ui(trip, prompt)
                    st.rerun()

            with col_name:
                st.markdown(f"**{name}**")
                travel = slot.get("travel_to_next_minutes")
                caption = category
                if travel:
                    caption += f" · 🚶 {travel} Min"
                st.caption(caption)

            with col_del:
                if st.button("🗑️", key=f"c3_del_{slot_id}", use_container_width=True):
                    prompt = f"lösche {name} an Tag {day_num}"
                    _send_chat_command_from_ui(trip, prompt)
                    st.rerun()

            with col_alt:
                if st.button("Alt.", key=f"c3_alt_{slot_id}", use_container_width=True):
                    st.session_state[f"show_alt_{slot_id}"] = not st.session_state.get(f"show_alt_{slot_id}", False)
                    st.session_state[f"show_ai_{slot_id}"] = False

            with col_ai:
                if st.button("KI-Alt.", key=f"c3_ai_{slot_id}", use_container_width=True):
                    st.session_state[f"show_ai_{slot_id}"] = not st.session_state.get(f"show_ai_{slot_id}", False)
                    st.session_state[f"show_alt_{slot_id}"] = False

            # Alternativen: gleiche Kategorie, nicht bereits im Plan
            if st.session_state.get(f"show_alt_{slot_id}", False):
                candidates = [
                    a for a in all_activities
                    if a.get("category") == category and a.get("id") not in used_ids
                ]
                if not candidates:
                    st.info("Keine Alternativen in dieser Kategorie gefunden.")
                else:
                    for alt in candidates[:3]:
                        a_col, b_col = st.columns([4, 1])
                        with a_col:
                            st.markdown(f"• **{alt['name']}** — {str(alt.get('description', ''))[:80]}")
                        with b_col:
                            if st.button("Wählen", key=f"pick_alt_{slot_id}_{alt['id']}"):
                                prompt = f"ersetze {name} durch {alt['name']} an Tag {day_num}"
                                _send_chat_command_from_ui(trip, prompt)
                                st.session_state[f"show_alt_{slot_id}"] = False
                                st.rerun()

            # KI-Alternative: profilbasiert
            if st.session_state.get(f"show_ai_{slot_id}", False):
                interests = profile_store.get_top_interests(limit=5)
                if not interests:
                    st.info("Noch keine Interessen bekannt — verbinde deine E-Mails unter 'Profil & Empfehlungen'.")
                else:
                    interest_keywords = [i["keyword"] for i in interests]
                    ranked = []
                    for a in all_activities:
                        if a.get("id") in used_ids:
                            continue
                        tags = [t.lower() for t in a.get("tags", [])]
                        hits = sum(1 for kw in interest_keywords if kw.lower() in tags)
                        if hits > 0:
                            ranked.append((hits, a))
                    ranked.sort(key=lambda x: x[0], reverse=True)
                    top = [a for _, a in ranked[:3]]

                    if not top:
                        st.info("Keine passenden Aktivitäten für dein Profil gefunden.")
                    else:
                        top_kw = ", ".join(interest_keywords[:3])
                        st.markdown(f"**Basierend auf deinen Interessen** ({top_kw}):")
                        for alt in top:
                            a_col, b_col = st.columns([4, 1])
                            with a_col:
                                st.markdown(f"• **{alt['name']}** — {str(alt.get('description', ''))[:80]}")
                            with b_col:
                                if st.button("Wählen", key=f"pick_ai_{slot_id}_{alt['id']}"):
                                    prompt = f"ersetze {name} durch {alt['name']} an Tag {day_num}"
                                    _send_chat_command_from_ui(trip, prompt)
                                    st.session_state[f"show_ai_{slot_id}"] = False
                                    st.rerun()


def _send_chat_command_from_ui(trip: dict, prompt: str):
    result = ui_service.send_chat_command(trip, prompt, st.session_state.chat_messages)
    if "Kalender wurde" in result["message"] or "Kalender wurden" in result["message"]:
        add_status("Kalender synchronisiert.")
    elif "Kalender konnte nicht aktualisiert werden" in result["message"]:
        add_status("Kalender nicht eingerichtet oder nicht erreichbar.")
    st.session_state.last_suggestions = trip.get("last_suggestions", [])
    st.session_state.last_suggestion_context = trip.get("last_suggestion_context", {})
    return result


def _pretrip_reply(message: str) -> str:
    text = message.lower()
    known_details = []
    for city in ["Berlin", "Köln", "München", "Paris", "Rom", "Barcelona", "Istanbul"]:
        if city.lower() in text:
            known_details.append(f"Ziel {city}")
            break

    import re
    days = re.search(r"(\d+)\s*(?:tage|tag)", text)
    budget = re.search(r"(\d+)\s*(?:euro|eur|€)", text)
    if days:
        known_details.append(f"{days.group(1)} Tage")
    if budget:
        known_details.append(f"Budget {budget.group(1)} EUR")

    prefix = ""
    if known_details:
        prefix = "Ich habe schon erkannt: " + ", ".join(known_details) + ". "
    return (
        prefix
        + "Ich kann dir helfen, die Reise zu planen. "
        "Nenne mir bitte Ziel, Datum, Dauer, Budget und Interessen oder trage die Angaben oben im Formular ein."
    )


def render_pretrip_chat():
    with st.container(border=True):
        st.markdown("## Reiseassistent")
        st.caption("Beschreibe dein Reiseziel oder stelle direkt eine Frage zur Planung.")
        messages = st.session_state.pretrip_chat_messages
        with st.container(height=240):
            if not messages:
                st.info("Ich helfe dir bei Ziel, Reisedauer, Budget und Interessen.")
            for message in messages:
                role = "Du" if message["role"] == "user" else "Reiseassistent"
                st.markdown(f"**{role}:** {message['content']}")

        with st.form("pretrip_chat_form", clear_on_submit=True):
            prompt = st.text_input(
                "Nachricht an den Reiseassistenten",
                placeholder="z. B. Plane mir 3 Tage Köln mit gutem Essen",
                label_visibility="collapsed",
            )
            submitted = st.form_submit_button("Nachricht senden", type="primary", use_container_width=True)
            if submitted and prompt.strip():
                st.session_state.pretrip_chat_messages.append({"role": "user", "content": prompt.strip()})
                st.session_state.pretrip_chat_messages.append({"role": "assistant", "content": _pretrip_reply(prompt)})
                st.rerun()


def render_right_col(plan: dict):
    budget = plan.get("budget_summary", {})
    currency = budget.get("currency", "EUR")
    planned = budget.get("planned_total", 0)
    total = budget.get("budget_total", 0)
    remaining = budget.get("remaining", 0)
    per_person = budget.get("per_person_total", 0)

    status_map = {
        "within_budget": ("Im Budget",   "pill-green"),
        "near_limit":    ("Nahe Limit",  "pill-orange"),
        "over_budget":   ("Über Budget", "pill-gray"),
    }
    status_label, status_cls = status_map.get(budget.get("status", "within_budget"), ("–", "pill-gray"))

    pill_colors = {"pill-green": "#166534;background:#dcfce7", "pill-orange": "#92400e;background:#fef3c7", "pill-gray": "#374151;background:#f3f4f6"}
    pill_style = pill_colors.get(status_cls, pill_colors["pill-gray"])

    cats_html = ""
    for cat in budget.get("categories", []):
        pct = min(cat.get("percentage", 0), 100)
        cats_html += (
            '<div style="display:flex;justify-content:space-between;font-size:12px;color:#374151;margin-top:8px;">'
            f'<span>{_esc(cat["category"].capitalize())}</span>'
            f'<span>{cat["amount"]:.0f} {currency}</span>'
            '</div>'
            '<div style="background:#f3f4f6;border-radius:99px;height:6px;margin:3px 0 2px;">'
            f'<div style="background:#2563eb;border-radius:99px;height:6px;width:{pct}%;"></div>'
            '</div>'
        )

    html = (
        '<div style="background:#fff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.08);padding:16px;margin-bottom:12px;">'
        '<div style="font-size:15px;font-weight:700;color:#111;margin-bottom:10px;display:flex;align-items:center;justify-content:space-between;">'
        'Budget'
        f'<span style="padding:2px 10px;border-radius:99px;font-size:12px;font-weight:600;color:{pill_style};">{status_label}</span>'
        '</div>'
        '<div style="text-align:center;padding:12px 0 8px;">'
        '<div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;">Geplant</div>'
        f'<div style="font-size:28px;font-weight:800;color:#111;">{planned:.0f} {currency}</div>'
        f'<div style="font-size:12px;color:#6b7280;">von {total:.0f} {currency}</div>'
        '</div>'
        '<div style="display:flex;justify-content:space-between;font-size:13px;padding:4px 0;">'
        f'<span>Restbudget</span><span><strong>{remaining:.0f} {currency}</strong></span>'
        '</div>'
        '<div style="display:flex;justify-content:space-between;font-size:13px;padding:4px 0;margin-bottom:10px;">'
        f'<span>Pro Person</span><span><strong>{per_person:.0f} {currency}</strong></span>'
        '</div>'
        + cats_html +
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)

    # Route card
    locations = []
    for day in plan.get("days", []):
        for slot in day.get("time_slots", []):
            loc = slot["activity"].get("location", {})
            locations.append({
                "name": slot["activity"]["name"],
                "day": day["day_number"],
                "start": slot.get("start_time", ""),
                "area": loc.get("area", ""),
            })

    if locations:
        route_html = ""
        for i, loc in enumerate(locations, 1):
            sub = f"Tag {loc['day']} &middot; {loc['start']}"
            if loc["area"]:
                sub += f" &middot; {_esc(loc['area'])}"
            route_html += (
                '<div style="display:flex;align-items:flex-start;gap:10px;padding:6px 0;border-bottom:1px solid #f3f4f6;">'
                f'<div style="min-width:22px;height:22px;border-radius:50%;background:#2563eb;color:#fff;font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;">{i}</div>'
                '<div>'
                f'<div style="font-size:13px;font-weight:600;color:#111;">{_esc(loc["name"])}</div>'
                f'<div style="font-size:11px;color:#6b7280;">{sub}</div>'
                '</div>'
                '</div>'
            )

        html = (
            '<div style="background:#fff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.08);'
            'padding:16px;margin-bottom:12px;max-height:36vh;overflow-y:auto;">'
            '<div style="font-size:15px;font-weight:700;color:#111;margin-bottom:10px;">Karte / Route</div>'
            + route_html +
            '</div>'
        )
        st.markdown(html, unsafe_allow_html=True)


def render_proposal_banner(trip: dict):
    pending = [p for p in trip.get("proposals", []) if p["status"] == "pending"]
    if not pending:
        return
    proposal = pending[0]

    st.markdown(f"""
    <div class="proposal-banner-div">
        <strong>⚠️ Neuplanungsvorschlag</strong> –
        <em>{_esc(proposal.get('reason', ''))}</em>
    </div>
    """, unsafe_allow_html=True)

    changes = proposal.get("changes", [])
    if changes:
        with st.expander(f"Details: {len(changes)} Änderung(en)"):
            for change in changes:
                st.markdown(f"- {change['explanation']} (Kostendelta: {change['cost_delta']:+.0f} €)")

    budget_before = proposal.get("budget_before", {})
    budget_after = proposal.get("budget_after", {})
    m1, m2 = st.columns(2)
    with m1:
        st.metric("Budget vorher", f"{budget_before.get('planned_total', 0):.0f} €")
    with m2:
        delta = budget_after.get("planned_total", 0) - budget_before.get("planned_total", 0)
        st.metric("Budget nachher", f"{budget_after.get('planned_total', 0):.0f} €", delta=f"{delta:+.0f} €")

    ca, cr = st.columns(2)
    with ca:
        if st.button("✅ Annehmen", type="primary", key=f"prop_accept_{proposal['id']}"):
            proposal["status"] = "accepted"
            new_plan = proposal["proposed_plan"]
            new_plan["status"] = "active"
            store.update_trip(trip["id"], {"active_plan": new_plan, "proposals": trip["proposals"]})
            sync_plan_and_notify(new_plan, "Neuplanung übernommen", trip["id"])
            st.success("Neuplanung übernommen!")
            st.rerun()
    with cr:
        if st.button("❌ Ablehnen", key=f"prop_reject_{proposal['id']}"):
            proposal["status"] = "rejected"
            store.update_trip(trip["id"], {"proposals": trip["proposals"]})
            st.info("Vorschlag abgelehnt. Ursprünglicher Plan bleibt erhalten.")
            st.rerun()


def show_profile_and_suggestions():
    import requests as http

    st.markdown("""
    <div class="card">
        <div class="card-title">Persönliches Profil &amp; Vorschläge</div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Profil aktualisieren", use_container_width=True):
            try:
                r = http.post("http://localhost:8000/api/profile/update", timeout=10)
                data = r.json()
                st.success(data["agent_insight"]["summary"])
                for item in data.get("top_interests", []):
                    st.write(f"- {item['keyword']} ({item['category']})")
            except Exception as e:
                st.error(f"Backend nicht erreichbar: {e}")
    with c2:
        if st.button("Freie Tage erkennen", use_container_width=True):
            try:
                r = http.post("http://localhost:8000/api/profile/detect-free-days", timeout=10)
                data = r.json()
                st.success(data["agent_insight"]["summary"])
            except Exception as e:
                st.error(f"Backend nicht erreichbar: {e}")
    with c3:
        home_city = st.text_input("Heimatstadt", value="Berlin", key="home_city_input")
        if st.button("Vorschläge generieren", use_container_width=True):
            try:
                r = http.post("http://localhost:8000/api/suggestions/generate", params={"home_city": home_city}, timeout=15)
                data = r.json()
                st.success(data["agent_insight"]["summary"])
            except Exception as e:
                st.error(f"Backend nicht erreichbar: {e}")

    try:
        r = http.get("http://localhost:8000/api/suggestions/pending", timeout=2)
        suggestions = r.json().get("suggestions", [])
    except Exception:
        suggestions = []

    if suggestions:
        st.markdown("**Deine Vorschläge**")
        for s in suggestions:
            acts_html = "".join(f'<div class="sugg-act">• {_esc(a)}</div>' for a in s.get("activities", []))
            highlight_html = ""
            if s.get("highlight"):
                highlight_html = f'<div style="background:#eff6ff;border-radius:6px;padding:6px 10px;font-size:12px;color:#1d4ed8;margin-top:6px">{_esc(s["highlight"])}</div>'
            st.markdown(f"""
            <div class="sugg-card">
                <div class="sugg-date">{_esc(s['date'])}</div>
                <div class="sugg-title">{_esc(s['title'])}</div>
                <div class="sugg-desc">{_esc(s.get('description', ''))}</div>
                {acts_html}
                {highlight_html}
            </div>
            """, unsafe_allow_html=True)
            sa, sb = st.columns(2)
            with sa:
                if st.button("Annehmen", key=f"sugg_accept_{s['id']}", use_container_width=True):
                    try:
                        response = http.post(f"http://localhost:8000/api/suggestions/{s['id']}/accept", timeout=20)
                        data = response.json()
                        calendar = data.get("calendar", {})
                        if calendar.get("created"):
                            st.success("Vorschlag angenommen und im Google Kalender eingetragen.")
                        else:
                            reason = calendar.get("reason", "unbekannt")
                            st.warning(f"Vorschlag angenommen, aber Kalender konnte nicht aktualisiert werden: {reason}")
                    except Exception as e:
                        st.error(f"Annehmen fehlgeschlagen: {e}")
                    st.rerun()
            with sb:
                if st.button("Ablehnen", key=f"sugg_reject_{s['id']}", use_container_width=True):
                    try:
                        http.post(
                            f"http://localhost:8000/api/suggestions/{s['id']}/reject",
                            params={"home_city": home_city},
                            timeout=5,
                        )
                    except Exception:
                        pass
                    st.rerun()
    else:
        st.info("Noch keine Vorschläge. Profil aktualisieren und freie Tage erkennen.")


# ─────────────────────────── trip overview ───────────────────────────────────

def render_trip_overview(compact: bool = False):
    trips = store.list_trips()
    if not trips:
        return

    st.markdown("### Deine Reisen")

    for trip in trips:
        req = trip.get("request", {})
        plan = trip.get("active_plan") or {}

        destination = req.get("destination", "Unbekannt")
        duration = req.get("duration_days", "?")
        start_date = req.get("start_date", "")
        status = plan.get("status", "kein Plan")
        flight_updates = trip.get("flight_updates") or {}
        flight_number = (
            req.get("flight_number")
            or trip.get("flight_number")
            or flight_updates.get("flight_number")
        )
        if flight_number:
            flight_number = str(flight_number).strip().upper()

        is_active = trip["id"] == st.session_state.trip_id

        with st.container(border=True):
            marker = " · Aktive Reise" if is_active else ""
            st.markdown(f"**{destination}**{marker}")
            date_label = start_date or "kein Datum"
            trip_details = f"{date_label} · {duration} Tage · {status}"
            if flight_number:
                trip_details += f" · Flug {flight_number}"
            st.caption(trip_details)

            with st.expander("Aktionen"):
                open_col, delete_col = st.columns(2)
                if open_col.button(
                    "Aktiv" if is_active else "Öffnen",
                    key=f"open_trip_{trip['id']}_{'compact' if compact else 'full'}",
                    disabled=is_active,
                    use_container_width=True,
                ):
                    st.session_state.trip_id = trip["id"]
                    st.session_state.chat_messages = trip.get("chat_messages", [])
                    st.session_state.confirm_delete_trip_id = None
                    st.rerun()

                if delete_col.button(
                    "Löschen",
                    key=f"delete_trip_{trip['id']}_{'compact' if compact else 'full'}",
                    use_container_width=True,
                ):
                    st.session_state.confirm_delete_trip_id = trip["id"]

                if st.session_state.confirm_delete_trip_id == trip["id"]:
                    st.warning(f"Reise nach {destination} wirklich löschen?")
                    confirm_col, cancel_col = st.columns(2)
                    if confirm_col.button(
                        "Ja, löschen",
                        key=f"confirm_delete_{trip['id']}",
                        type="primary",
                        use_container_width=True,
                    ):
                        delete_result = ui_service.delete_trip(trip)
                        calendar_result = delete_result["calendar"]
                        deleted = delete_result["trip_deleted"]
                        if deleted:
                            if is_active:
                                st.session_state.trip_id = None
                                st.session_state.chat_messages = []
                                st.session_state.last_suggestions = []
                                st.session_state.last_suggestion_context = {}
                            st.session_state.pop(f"all_activities_{trip['id']}", None)
                            st.session_state.confirm_delete_trip_id = None
                            calendar_count = calendar_result.get("deleted_count", 0)
                            if calendar_count:
                                add_status(
                                    f"Reise und {calendar_count} Kalendereinträge gelöscht."
                                )
                            elif calendar_result.get("success"):
                                add_status(
                                    "Reise gelöscht. Keine passenden Kalendereinträge gefunden."
                                )
                            else:
                                add_status(
                                    "Reise gelöscht. Kalender konnte nicht aktualisiert werden."
                                )
                        else:
                            calendar_count = calendar_result.get("deleted_count", 0)
                            if calendar_count:
                                add_status(
                                    f"{calendar_count} Kalendereinträge gelöscht, "
                                    "Reise konnte nicht gelöscht werden."
                                )
                            else:
                                add_status("Reise konnte nicht gelöscht werden.")
                        st.rerun()

                    if cancel_col.button(
                        "Abbrechen",
                        key=f"cancel_delete_{trip['id']}",
                        use_container_width=True,
                    ):
                        st.session_state.confirm_delete_trip_id = None
                        st.rerun()


def render_bank_account_section():
    """Einfache Verwaltung für das Reisebudget (Modul D). Rein lesend/
    schreibend über profile_store — keine Telegram-, Kalender- oder Trip-Aktionen."""
    with st.expander("Reisebudget"):
        account = profile_store.get_current_bank_account()

        st.markdown("#### Aktueller Stand")
        if not account:
            st.info("Noch kein Reisebudget gespeichert.")
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("Monat", account["month"])
            c1.metric("Einnahmen", f"{account['income']:.0f} €")
            c2.metric("Fixkosten", f"{account['fixed_costs']:.0f} €")
            c2.metric("Frei verfügbar", f"{account['free_amount']:.0f} €")
            c3.metric("Für Reisen eingeplant", f"{account['travel_reserve']:.0f} €")
            # Direkt nach dem Speichern sind travel_reserve und current_balance
            # identisch - dann nicht redundant zweimal denselben Betrag zeigen.
            if round(account["current_balance"], 2) == round(account["travel_reserve"], 2):
                c3.caption("Noch keine Reisekosten verbucht")
            else:
                c3.metric("Noch verfügbar", f"{account['current_balance']:.0f} €")

        st.markdown("#### Reisebudget bearbeiten")
        with st.form("bank_checkin_form"):
            bc1, bc2 = st.columns(2)
            with bc1:
                month_input = st.text_input(
                    "Monat (YYYY-MM)",
                    value=account["month"] if account else date.today().strftime("%Y-%m"),
                )
                income_input = st.number_input(
                    "Einnahmen (EUR)",
                    min_value=0.0,
                    value=float(account["income"]) if account else 0.0,
                    step=50.0,
                )
            with bc2:
                fixed_costs_input = st.number_input(
                    "Fixkosten (EUR)",
                    min_value=0.0,
                    value=float(account["fixed_costs"]) if account else 0.0,
                    step=50.0,
                )
                travel_reserve_input = st.number_input(
                    "Für Reisen eingeplant (EUR)",
                    min_value=0.0,
                    value=0.0,
                    step=10.0,
                    help="Leer/0 lassen, um automatisch 20 % vom frei verfügbaren Betrag zu verwenden.",
                )
            if st.form_submit_button("Reisebudget speichern", type="primary"):
                if not month_input.strip():
                    st.error("Bitte einen Monat angeben (z. B. 2026-07).")
                    st.stop()
                # 0 EUR = Nutzer hat nichts eingegeben -> weiter die 20%-Regel nutzen
                travel_reserve_arg = travel_reserve_input if travel_reserve_input > 0 else None
                saved = profile_store.save_bank_checkin(
                    month_input.strip(),
                    income_input,
                    fixed_costs_input,
                    travel_reserve=travel_reserve_arg,
                )
                add_status(
                    f"Reisebudget für {saved['month']} gespeichert. "
                    f"Frei verfügbar: {saved['free_amount']:.0f} €, "
                    f"für Reisen eingeplant: {saved['travel_reserve']:.0f} €."
                )
                st.rerun()

        st.markdown("#### Zurücksetzen")
        if st.session_state.confirm_reset_bank:
            st.warning(
                "Reisebudget und alle Buchungen wirklich zurücksetzen? "
                "Andere Profildaten (Interessen, Nachrichten etc.) bleiben erhalten."
            )
            rc1, rc2 = st.columns(2)
            if rc1.button(
                "Ja, zurücksetzen", key="confirm_reset_bank_yes", type="primary", use_container_width=True
            ):
                profile_store.reset_bank_account_for_demo()
                st.session_state.confirm_reset_bank = False
                add_status("Reisebudget wurde zurückgesetzt.")
                st.rerun()
            if rc2.button("Abbrechen", key="confirm_reset_bank_cancel", use_container_width=True):
                st.session_state.confirm_reset_bank = False
                st.rerun()
        else:
            if st.button("Reisebudget zurücksetzen"):
                st.session_state.confirm_reset_bank = True
                st.rerun()

        st.markdown("#### Letzte Transaktionen")
        transactions = profile_store.get_recent_bank_transactions(limit=10)
        if not transactions:
            st.info("Noch keine Banktransaktionen vorhanden.")
        else:
            for tx in transactions:
                st.caption(
                    f"{tx.get('created_at', '')} · {tx.get('amount', 0):.2f} € · "
                    f"{tx.get('reason') or '-'} · Trip: {tx.get('trip_id') or '-'}"
                )


# ─────────────────────────── main ────────────────────────────────────────────

def main():
    init_session()
    refresh_profile_in_background()

    # ── Header ───────────────────────────────────────────────────────────────
    h_left, h_right = st.columns([3, 2])
    with h_left:
        st.markdown("""
        <div style="padding:4px 0 12px">
            <p class="header-h1">Reiseplanungs-Agent</p>
            <p class="header-sub">GenAI-gesteuerte Reiseplanung mit Chat, Tagesplan, Budget und Proposal Flow.</p>
        </div>
        """, unsafe_allow_html=True)
    with h_right:
        pill_col, demo_col, rain_col = st.columns([1, 2, 2])
        with pill_col:
            st.markdown('<div style="padding-top:8px"><span class="pill pill-green">API: online</span></div>', unsafe_allow_html=True)
        with demo_col:
            if st.button("Demo-Reise laden", type="primary", use_container_width=True):
                with st.spinner("Plane Berlin-Reise..."):
                    load_demo_trip()
                st.rerun()
        with rain_col:
            trip_check = get_current_trip()
            rain_disabled = not (trip_check and trip_check.get("active_plan"))
            if st.button("Regen an Tag 2 simulieren", use_container_width=True, disabled=rain_disabled):
                simulate_rain_day2()
                st.rerun()

    render_status_messages()

    # ── Eigene Reise planen ──────────────────────────────────────────────────
    with st.expander("Eigene Reise planen"):
        travel_type_labels = {
            "solo": "Solo",
            "couple": "Paar",
            "family": "Familie",
            "group": "Freunde / Gruppe",
        }
        ttype = st.selectbox(
            "Reiseart",
            list(travel_type_labels.keys()),
            format_func=lambda value: travel_type_labels[value],
            key="trip_form_travel_type",
        )
        is_solo = ttype == "solo"

        previous_travel_type = st.session_state.trip_form_previous_travel_type
        if ttype != previous_travel_type:
            if is_solo:
                st.session_state.trip_form_people = 1
            elif previous_travel_type == "solo":
                st.session_state.trip_form_people = 2
            elif st.session_state.trip_form_people < 2:
                st.session_state.trip_form_people = 2
            st.session_state.trip_form_previous_travel_type = ttype
        elif is_solo:
            st.session_state.trip_form_people = 1
        elif st.session_state.trip_form_people < 2:
            st.session_state.trip_form_people = 2

        minimum_people = 1 if is_solo else 2

        with st.form("plan_form"):
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                dest = st.text_input("Reiseziel", "München")
                start_date = st.date_input("Startdatum (Anreise)", value=date.today() + timedelta(days=1))
                end_date = st.date_input("Enddatum (Abreise)", value=date.today() + timedelta(days=4))
                day_start = st.time_input("Tagesstart (alle Tage)", value=time(9, 0))
            with fc2:
                bud = st.number_input("Budget (EUR)", 100.0, 10000.0, 500.0, 50.0)
                ppl = st.number_input(
                    "Personen",
                    min_value=minimum_people,
                    max_value=20,
                    step=1,
                    key="trip_form_people",
                    disabled=is_solo,
                    help=(
                        "Bei einer Solo-Reise ist die Personenanzahl fest auf 1 gesetzt."
                        if is_solo
                        else "Für Paar-, Familien- und Gruppenreisen sind mindestens 2 Personen nötig."
                    ),
                )
            with fc3:
                ints = st.multiselect(
                    "Interessen",
                    ["Museen", "gutes Essen", "Sehenswürdigkeiten", "Spaziergänge", "Natur", "Shopping"],
                    default=["Sehenswürdigkeiten", "gutes Essen"],
                )
                flight_number = st.text_input(
                    "Flugnummer optional",
                    value="",
                    placeholder="Optional, z. B. BA8493",
                    help="Leer lassen, wenn keine Flugdaten berücksichtigt werden sollen.",
                )
            if st.form_submit_button("Reise planen", type="primary"):
                if end_date < start_date:
                    st.error("Enddatum muss nach dem Startdatum liegen.")
                    st.stop()
                dur = (end_date - start_date).days + 1
                people_count = 1 if is_solo else max(2, int(ppl))
                req = {
                    "destination": dest,
                    "duration_days": dur,
                    "start_date": start_date.isoformat(),
                    "departure_date": start_date.isoformat(),
                    "day_start_time": day_start.strftime("%H:%M"),
                    "budget_total": bud,
                    "currency": "EUR",
                    "number_of_people": people_count,
                    "travel_type": ttype,
                    "interests": ints or ["Sehenswürdigkeiten"],
                    "flight_number": flight_number.strip() or None,
                }
                with st.spinner("Plane Reise..."):
                    trip_id, active_plan = ui_service.create_trip(req)
                    sync_plan_and_notify(active_plan, "Plan erstellt", trip_id)
                    st.session_state.trip_id = trip_id
                    st.session_state.chat_messages = []
                st.rerun()

    render_bank_account_section()

    trip = get_current_trip()

    if not trip:
        left, right = st.columns([1, 2.2])
        with left:
            render_pretrip_chat()
            render_trip_overview(compact=True)
        with right:
            st.info("Plane über das Formular eine neue Reise oder öffne eine gespeicherte Reise.")
        return

    # ── Proposal Banner ──────────────────────────────────────────────────────
    render_proposal_banner(trip)

    active_plan = trip.get("active_plan")
    if not active_plan:
        st.warning("Kein aktiver Reiseplan gefunden.")
        return

    render_flight_panel(trip)

    # ── Three-column layout: 25% · 45% · 30% ────────────────────────────────
    col_chat, col_plan, col_budget = st.columns([1, 1.8, 1.2])

    with col_chat:
        render_left_col(trip)

    with col_plan:
        render_interactive_plan(trip)

    with col_budget:
        render_right_col(active_plan)

    # ── Navigation & Telegram ────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🗺️ Navigation & Telegram-Erinnerungen")
    st.caption("Routen zwischen Aktivitäten berechnen und Erinnerungen an die Gruppe schicken.")

    for day in active_plan.get("days", []):
        slots = day.get("time_slots", [])
        if not slots:
            continue
        with st.expander(f"{_format_day_label(day)} – {day['title']}"):
            for i, slot in enumerate(slots):
                activity = slot["activity"]
                loc = activity.get("location", {})
                lat = loc.get("lat")
                lng = loc.get("lng")

                routes = {"foot": None, "car": None}
                if i > 0 and lat and lng:
                    prev_loc = slots[i - 1]["activity"].get("location", {})
                    prev_lat = prev_loc.get("lat")
                    prev_lng = prev_loc.get("lng")
                    if prev_lat and prev_lng:
                        from providers.navigation import get_both_routes
                        routes = get_both_routes(prev_lat, prev_lng, lat, lng)

                foot = routes.get("foot")
                col_info, col_btn = st.columns([3, 1])
                with col_info:
                    if foot:
                        st.markdown(
                            f"**{slot['start_time']} – {activity['name']}**  \n"
                            f"👟 {foot['duration_minutes']} Min zu Fuß · {foot['distance_km']} km"
                        )
                    else:
                        st.markdown(f"**{slot['start_time']} – {activity['name']}**")

                with col_btn:
                    btn_key = f"notify_{day['day_number']}_{i}"
                    if st.button("📬 Senden", key=btn_key):
                        from providers.telegram import send_navigation_reminder
                        ok = send_navigation_reminder(activity["name"], slot["start_time"], routes)
                        if ok:
                            st.success("Gesendet!")
                        else:
                            st.error("Fehler beim Senden.")

if __name__ == "__main__":
    main()
