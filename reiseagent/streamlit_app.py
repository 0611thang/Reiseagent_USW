import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import folium
from streamlit_folium import st_folium

import store
from agents import coordinator, replanning
from providers.places import get_places

st.set_page_config(
    page_title="Reiseplanungs-Agent",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
.agent-card { background:#f0f2f6; border-radius:8px; padding:10px; margin:4px 0; }
.proposal-banner { background:#fff3cd; border:1px solid #ffc107; border-radius:8px; padding:15px; margin:10px 0; }
.budget-box { background:#e8f5e9; border-radius:8px; padding:10px; }
.status-within { color: #2e7d32; font-weight:bold; }
.status-near { color: #f57c00; font-weight:bold; }
.status-over { color: #c62828; font-weight:bold; }
</style>
""", unsafe_allow_html=True)


def init_session():
    if "trip_id" not in st.session_state:
        st.session_state.trip_id = None
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []


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


def render_weather_icon(condition: str) -> str:
    icons = {
        "sunny": "☀️",
        "cloudy": "☁️",
        "rain": "🌧️",
        "storm": "⛈️",
        "snow": "❄️",
    }
    return icons.get(condition, "🌤️")


def render_category_icon(category: str) -> str:
    icons = {
        "museum": "🏛️",
        "restaurant": "🍽️",
        "sightseeing": "📍",
        "walk": "🚶",
        "activity": "🎯",
        "transport": "🚌",
        "break": "☕",
    }
    return icons.get(category, "📌")


def render_tagesplan(plan: dict):
    days = plan.get("days", [])
    if not days:
        st.info("Kein Tagesplan verfügbar.")
        return

    tab_labels = []
    for day in days:
        weather = day.get("weather")
        icon = render_weather_icon(weather["condition"]) if weather else "📅"
        tab_labels.append(f"{icon} Tag {day['day_number']}")

    tabs = st.tabs(tab_labels)

    for tab, day in zip(tabs, days):
        with tab:
            weather = day.get("weather")
            col_title, col_weather = st.columns([3, 1])
            with col_title:
                st.markdown(f"### {day['title']}")
                if day.get("date"):
                    st.caption(f"Datum: {day['date']}")
            with col_weather:
                if weather:
                    icon = render_weather_icon(weather["condition"])
                    st.markdown(f"**{icon} {weather['description']}**")
                    if weather.get("affects_outdoor_activities"):
                        st.warning("Outdoor-Aktivitäten eingeschränkt")

            st.divider()
            slots = day.get("time_slots", [])
            if not slots:
                st.info("Keine Aktivitäten geplant.")
                continue

            for slot in slots:
                act = slot["activity"]
                icon = render_category_icon(act.get("category", ""))
                with st.container():
                    c1, c2, c3 = st.columns([1, 4, 1])
                    with c1:
                        st.markdown(f"**{slot['start_time']}**")
                        st.caption(slot["end_time"])
                    with c2:
                        st.markdown(f"**{icon} {act['name']}**")
                        st.caption(act.get("description", ""))
                        loc = act.get("location", {})
                        if loc.get("area"):
                            st.caption(f"📍 {loc.get('name', '')} · {loc['area']}")
                        score = act.get("score")
                        if score:
                            st.caption(
                                f"Score: {score['overall_score']:.0%} · "
                                f"Interessen: {score['interest_match']:.0%} · "
                                f"Wetter: {score['weather_match']:.0%}"
                            )
                    with c3:
                        cost = act.get("estimated_cost_total", 0.0)
                        if cost > 0:
                            st.metric("Kosten", f"{cost:.0f} €")
                        else:
                            st.markdown("**Kostenlos**")
                    st.divider()


def render_budget(budget_summary: dict):
    status = budget_summary.get("status", "within_budget")
    status_labels = {
        "within_budget": ("Im Budget", "status-within"),
        "near_limit": ("Nahe am Limit", "status-near"),
        "over_budget": ("Über Budget!", "status-over"),
    }
    label, css_class = status_labels.get(status, ("Unbekannt", ""))

    currency = budget_summary.get("currency", "EUR")

    st.markdown(f"""
    <div class="budget-box">
        <p><strong>Gesamt-Budget:</strong> {budget_summary.get('budget_total', 0):.0f} {currency}</p>
        <p><strong>Geplant:</strong> {budget_summary.get('planned_total', 0):.0f} {currency}</p>
        <p><strong>Verbleibend:</strong> {budget_summary.get('remaining', 0):.0f} {currency}</p>
        <p><strong>Pro Person:</strong> {budget_summary.get('per_person_total', 0):.0f} {currency}</p>
        <p>Status: <span class="{css_class}">{label}</span></p>
    </div>
    """, unsafe_allow_html=True)

    categories = budget_summary.get("categories", [])
    if categories:
        st.markdown("**Ausgaben nach Kategorie:**")
        for cat in categories:
            icon = render_category_icon(cat["category"])
            st.progress(
                cat["percentage"] / 100,
                text=f"{icon} {cat['category'].capitalize()}: {cat['amount']:.0f} {currency} ({cat['percentage']:.0f}%)",
            )


def render_checklist(checklist: dict):
    items = checklist.get("items", [])
    if not items:
        st.info("Keine Checkliste vorhanden.")
        return

    categories = {}
    for item in items:
        cat = item.get("category", "other")
        categories.setdefault(cat, []).append(item)

    cat_icons = {
        "documents": "📄 Dokumente",
        "booking": "🎫 Buchungen",
        "packing": "🧳 Gepäck",
        "preparation": "🔧 Vorbereitung",
    }

    for cat_key, cat_items in categories.items():
        st.markdown(f"**{cat_icons.get(cat_key, cat_key.capitalize())}**")
        for item in cat_items:
            priority_badge = "🔴" if item["priority"] == "high" else ("🟡" if item["priority"] == "medium" else "🟢")
            new_val = st.checkbox(
                f"{priority_badge} {item['label']}",
                value=item["completed"],
                key=f"checklist_{item['id']}",
            )
            if new_val != item["completed"]:
                item["completed"] = new_val
                trip_id = st.session_state.trip_id
                if trip_id:
                    trip = store.get_trip(trip_id)
                    if trip and trip.get("checklist"):
                        store.update_trip(trip_id, {"checklist": trip["checklist"]})


def render_map(plan: dict):
    all_locations = []
    for day in plan.get("days", []):
        for slot in day.get("time_slots", []):
            loc = slot["activity"].get("location", {})
            if loc.get("lat") and loc.get("lng"):
                all_locations.append({
                    "name": slot["activity"]["name"],
                    "lat": loc["lat"],
                    "lng": loc["lng"],
                    "category": slot["activity"].get("category", ""),
                    "day": day["day_number"],
                })

    if not all_locations:
        st.info("Keine Koordinaten für Kartenansicht verfügbar.")
        return

    center_lat = sum(l["lat"] for l in all_locations) / len(all_locations)
    center_lng = sum(l["lng"] for l in all_locations) / len(all_locations)

    m = folium.Map(location=[center_lat, center_lng], zoom_start=13)

    day_colors = ["red", "blue", "green", "purple", "orange"]
    cat_icons_folium = {
        "museum": "university",
        "restaurant": "cutlery",
        "sightseeing": "eye",
        "walk": "tree",
        "activity": "star",
    }

    for loc in all_locations:
        color = day_colors[(loc["day"] - 1) % len(day_colors)]
        icon_name = cat_icons_folium.get(loc["category"], "info-sign")
        folium.Marker(
            location=[loc["lat"], loc["lng"]],
            popup=folium.Popup(f"Tag {loc['day']}: {loc['name']}", max_width=200),
            tooltip=loc["name"],
            icon=folium.Icon(color=color, icon=icon_name, prefix="glyphicon"),
        ).add_to(m)

    st_folium(m, width=700, height=400)


def render_agent_insights(insights: list):
    status_icons = {
        "pending": "⏳",
        "running": "🔄",
        "completed": "✅",
        "failed": "❌",
    }
    for insight in insights:
        icon = status_icons.get(insight.get("status", ""), "•")
        st.markdown(
            f'<div class="agent-card">{icon} <strong>{insight.get("display_label", insight.get("agent_name", "Agent"))}</strong>: {insight.get("summary", "")}</div>',
            unsafe_allow_html=True,
        )


def render_proposal_banner(trip: dict):
    pending_proposals = [p for p in trip.get("proposals", []) if p["status"] == "pending"]
    if not pending_proposals:
        return

    proposal = pending_proposals[0]

    st.markdown(f"""
    <div class="proposal-banner">
        <strong>⚠️ Neuplanungsvorschlag (noch nicht übernommen)</strong><br>
        <em>{proposal['reason']}</em>
    </div>
    """, unsafe_allow_html=True)

    changes = proposal.get("changes", [])
    if changes:
        with st.expander(f"Details: {len(changes)} Änderung(en)"):
            for change in changes:
                st.markdown(f"- {change['explanation']} (Kostendelta: {change['cost_delta']:+.0f} €)")

    budget_before = proposal.get("budget_before", {})
    budget_after = proposal.get("budget_after", {})
    col1, col2 = st.columns(2)
    with col1:
        st.metric(
            "Budget vorher",
            f"{budget_before.get('planned_total', 0):.0f} €",
        )
    with col2:
        delta = budget_after.get("planned_total", 0) - budget_before.get("planned_total", 0)
        st.metric(
            "Budget nachher",
            f"{budget_after.get('planned_total', 0):.0f} €",
            delta=f"{delta:+.0f} €",
        )

    col_accept, col_reject = st.columns(2)
    with col_accept:
        if st.button("✅ Änderungen übernehmen", type="primary", key=f"accept_{proposal['id']}"):
            proposal["status"] = "accepted"
            new_plan = proposal["proposed_plan"]
            new_plan["status"] = "active"
            store.update_trip(trip["id"], {
                "active_plan": new_plan,
                "proposals": trip["proposals"],
            })
            st.success("Neuplanung übernommen!")
            st.rerun()

    with col_reject:
        if st.button("❌ Ablehnen", key=f"reject_{proposal['id']}"):
            proposal["status"] = "rejected"
            store.update_trip(trip["id"], {"proposals": trip["proposals"]})
            st.info("Vorschlag abgelehnt. Ursprünglicher Plan bleibt erhalten.")
            st.rerun()


def render_chat(trip: dict):
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    user_input = st.chat_input("Frage deinen Reiseassistenten...")
    if user_input:
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        result = coordinator.handle_chat_message(trip, user_input)
        reply = result["message"]

        st.session_state.chat_messages.append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"):
            st.write(reply)


def main():
    init_session()

    st.title("🗺️ Reiseplanungs-Agent")
    st.caption("HTW Berlin · Unternehmensanwendungen mit KI")

    col_demo, col_rain, col_plan = st.columns([2, 2, 3])
    with col_demo:
        if st.button("🚀 Demo-Reise laden (Berlin)", type="primary"):
            with st.spinner("Plane Berlin-Reise..."):
                load_demo_trip()
            st.rerun()

    trip = get_current_trip()

    if trip and trip.get("active_plan"):
        with col_rain:
            if st.button("🌧️ Regen an Tag 2 simulieren"):
                simulate_rain_day2()
                st.rerun()

    with col_plan:
        with st.expander("Eigene Reise planen"):
            with st.form("plan_form"):
                dest = st.text_input("Reiseziel", "München")
                days = st.slider("Tage", 1, 14, 3)
                budget = st.number_input("Budget (EUR)", 100.0, 10000.0, 500.0, 50.0)
                people = st.number_input("Personen", 1, 20, 2)
                travel_type = st.selectbox("Reiseart", ["solo", "couple", "family", "group"])
                interests = st.multiselect(
                    "Interessen",
                    ["Museen", "gutes Essen", "Sehenswürdigkeiten", "Spaziergänge", "Natur", "Shopping"],
                    default=["Sehenswürdigkeiten", "gutes Essen"],
                )
                submitted = st.form_submit_button("Reise planen")
                if submitted:
                    request = {
                        "destination": dest,
                        "duration_days": days,
                        "budget_total": budget,
                        "currency": "EUR",
                        "number_of_people": people,
                        "travel_type": travel_type,
                        "interests": interests or ["Sehenswürdigkeiten"],
                    }
                    with st.spinner("Plane Reise..."):
                        trip_obj = store.create_trip(request)
                        result = coordinator.handle_plan_request(request)
                        checklist_data = result["checklist"]
                        checklist_data["trip_id"] = trip_obj["id"]
                        store.update_trip(trip_obj["id"], {
                            "active_plan": result["active_plan"],
                            "checklist": checklist_data,
                            "agent_insights": result["agent_insights"],
                        })
                        st.session_state.trip_id = trip_obj["id"]
                        st.session_state.chat_messages = []
                    st.rerun()

    if not trip:
        st.info("Lade eine Demo-Reise oder plane eine eigene Reise, um zu starten.")
        return

    render_proposal_banner(trip)

    active_plan = trip.get("active_plan")
    if not active_plan:
        st.warning("Kein aktiver Reiseplan gefunden.")
        return

    req = trip["request"]
    st.markdown(
        f"**{req['destination']}** · {req['duration_days']} Tage · "
        f"{req['budget_total']} {req['currency']} · "
        f"{req['number_of_people']} Person(en) · {req['travel_type'].capitalize()} · "
        f"Interessen: {', '.join(req['interests'])}"
    )

    main_col, side_col = st.columns([3, 1])

    with main_col:
        tab_plan, tab_chat, tab_map = st.tabs(["📅 Tagesplan", "💬 Chat", "🗺️ Karte"])

        with tab_plan:
            render_tagesplan(active_plan)

        with tab_chat:
            render_chat(trip)

        with tab_map:
            render_map(active_plan)

    with side_col:
        st.markdown("### 💰 Budget")
        render_budget(active_plan["budget_summary"])

        st.markdown("---")
        st.markdown("### ✅ Checkliste")
        if trip.get("checklist"):
            render_checklist(trip["checklist"])
        else:
            st.info("Keine Checkliste vorhanden.")

        st.markdown("---")
        st.markdown("### 🤖 Agent Insights")
        insights = trip.get("agent_insights", [])
        if insights:
            render_agent_insights(insights)
        else:
            st.info("Keine Insights verfügbar.")


if __name__ == "__main__":
    main()
