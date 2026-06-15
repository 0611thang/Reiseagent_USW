import sys
import os
from datetime import datetime
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import folium
from streamlit_folium import st_folium

import store
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


def add_status(message: str):
    st.session_state.status_messages.append(message)
    st.session_state.status_messages = st.session_state.status_messages[-5:]


def sync_plan_and_notify(plan: dict, reason: str = "Plan aktualisiert") -> dict:
    calendar_result = sync_full_plan_to_calendar(plan)
    calendar_ok = calendar_result.get("updated", False)
    telegram_ok = send_plan_update(plan, calendar_synced=calendar_ok)

    if calendar_ok:
        add_status(f"{reason}: Kalender synchronisiert.")
    else:
        add_status(f"{reason}: Kalender nicht eingerichtet oder nicht erreichbar.")

    if telegram_ok:
        add_status("Telegram gesendet.")

    return calendar_result


def get_current_trip() -> dict | None:
    if not st.session_state.trip_id:
        return None
    return store.get_trip(st.session_state.trip_id)


def load_demo_trip():
    demo_request = {
        "destination": "Berlin",
        "duration_days": 3,
        "budget_total": 600.0,
        "currency": "EUR",
        "number_of_people": 2,
        "travel_type": "couple",
        "interests": ["Museen", "gutes Essen", "Sehenswürdigkeiten", "Spaziergänge"],
    }
    trip = store.create_trip(demo_request)
    result = coordinator.handle_plan_request(demo_request, use_mock_weather=True)
    checklist_data = result["checklist"]
    checklist_data["trip_id"] = trip["id"]
    store.update_trip(trip["id"], {
        "active_plan": result["active_plan"],
        "checklist": checklist_data,
        "agent_insights": result["agent_insights"],
    })
    sync_plan_and_notify(result["active_plan"], "Demo-Reise erstellt")
    st.session_state.trip_id = trip["id"]
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
        '<div style="background:#fff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.08);padding:16px;margin-bottom:12px;">'
        '<div style="font-size:15px;font-weight:700;color:#111;margin-bottom:10px;">Chat</div>'
        f'<div style="max-height:320px;overflow-y:auto;margin-bottom:10px;">{hint}{msgs_html}</div>'
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
            if "Kalender wurde" in result["message"]:
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

    if active_plan:
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


def render_plan_actions(trip: dict):
    plan = trip.get("active_plan", {})
    days = plan.get("days", [])
    if not days:
        return

    with st.expander("Plan schnell bearbeiten"):
        for day in days:
            st.caption(_format_day_label(day))
            for slot in day.get("time_slots", []):
                activity = slot.get("activity", {})
                name = activity.get("name", "Aktivität")
                label = f"{slot.get('start_time')} - {name}"
                cols = st.columns([3, 1, 1])
                with cols[0]:
                    st.write(label)
                with cols[1]:
                    if st.button("Löschen", key=f"delete_{day['day_number']}_{slot['id']}"):
                        prompt = f"lösche {name} an Tag {day['day_number']}"
                        _send_chat_command_from_ui(trip, prompt)
                        add_status("Aktivität gelöscht.")
                        st.rerun()
                with cols[2]:
                    if st.button("Alternative", key=f"alt_{day['day_number']}_{slot['id']}"):
                        prompt = f"gib mir Vorschläge für Tag {day['day_number']} um {slot.get('start_time')}"
                        _send_chat_command_from_ui(trip, prompt)
                        add_status("Alternativen gesucht.")
                        st.rerun()


def _send_chat_command_from_ui(trip: dict, prompt: str):
    st.session_state.chat_messages.append({"role": "user", "content": prompt})
    trip["chat_messages"] = list(st.session_state.chat_messages)
    result = coordinator.handle_chat_message(trip, prompt)
    st.session_state.chat_messages.append({"role": "assistant", "content": result["message"]})
    if "Kalender wurde" in result["message"]:
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
            sync_plan_and_notify(new_plan, "Neuplanung übernommen")
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


# ─────────────────────────── main ────────────────────────────────────────────

def main():
    init_session()

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

    for msg in st.session_state.status_messages:
        st.info(msg)

    # ── Eigene Reise planen ──────────────────────────────────────────────────
    with st.expander("Eigene Reise planen"):
        with st.form("plan_form"):
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                dest = st.text_input("Reiseziel", "München")
                dur = st.slider("Tage", 1, 14, 3)
            with fc2:
                bud = st.number_input("Budget (EUR)", 100.0, 10000.0, 500.0, 50.0)
                ppl = st.number_input("Personen", 1, 20, 2)
            with fc3:
                ttype = st.selectbox("Reiseart", ["solo", "couple", "family", "group"])
                ints = st.multiselect(
                    "Interessen",
                    ["Museen", "gutes Essen", "Sehenswürdigkeiten", "Spaziergänge", "Natur", "Shopping"],
                    default=["Sehenswürdigkeiten", "gutes Essen"],
                )
            if st.form_submit_button("Reise planen", type="primary"):
                req = {
                    "destination": dest,
                    "duration_days": dur,
                    "budget_total": bud,
                    "currency": "EUR",
                    "number_of_people": ppl,
                    "travel_type": ttype,
                    "interests": ints or ["Sehenswürdigkeiten"],
                }
                with st.spinner("Plane Reise..."):
                    trip_obj = store.create_trip(req)
                    result = coordinator.handle_plan_request(req)
                    cl = result["checklist"]
                    cl["trip_id"] = trip_obj["id"]
                    store.update_trip(trip_obj["id"], {
                        "active_plan": result["active_plan"],
                        "checklist": cl,
                        "agent_insights": result["agent_insights"],
                    })
                    sync_plan_and_notify(result["active_plan"], "Plan erstellt")
                    st.session_state.trip_id = trip_obj["id"]
                    st.session_state.chat_messages = []
                st.rerun()

    trip = get_current_trip()

    if not trip:
        st.info("Lade eine Demo-Reise oder plane eine eigene Reise, um zu starten.")
        st.markdown("---")
        show_profile_and_suggestions()
        return

    # ── Proposal Banner ──────────────────────────────────────────────────────
    render_proposal_banner(trip)

    active_plan = trip.get("active_plan")
    if not active_plan:
        st.warning("Kein aktiver Reiseplan gefunden.")
        return

    # ── Three-column layout: 25% · 45% · 30% ────────────────────────────────
    col_chat, col_plan, col_budget = st.columns([1, 1.8, 1.2])

    with col_chat:
        render_left_col(trip)

    with col_plan:
        render_middle_col(active_plan)
        render_plan_actions(trip)

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

    # ── Profile & Suggestions ────────────────────────────────────────────────
    st.markdown("---")
    show_profile_and_suggestions()


if __name__ == "__main__":
    main()
