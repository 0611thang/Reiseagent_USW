import os
from typing import TypedDict

import llm
import prompts
from langgraph.graph import StateGraph, END

TOOL_NAMES = [
    "change_time",
    "replan_day",
    "suggest_alternatives",
    "delete_activity",
    "fill_plan",
    "replace_activity",
    "add_activity",
    "sync_calendar",
    "answer_question",
]

TOOLS = [
    {"type": "function", "function": {
        "name": "change_time",
        "description": "Eine Aktivität im Reiseplan zeitlich verschieben (z.B. Abendessen auf 20 Uhr).",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "replan_day",
        "description": "Einen Tag oder Abschnitt des Reiseplans komplett neu planen.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "suggest_alternatives",
        "description": "Alternativen oder Vorschläge für eine bestehende Aktivität anzeigen.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "delete_activity",
        "description": "Eine Aktivität aus dem Reiseplan löschen oder entfernen.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "fill_plan",
        "description": "Leere Zeitslots im Reiseplan auffüllen oder den Plan vervollständigen.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "replace_activity",
        "description": "Eine Aktivität durch eine andere ersetzen oder einen angezeigten Vorschlag annehmen.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "add_activity",
        "description": "Eine neue Aktivität zum Reiseplan hinzufügen.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "sync_calendar",
        "description": "Den Reiseplan mit Google Calendar synchronisieren oder eintragen.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "answer_question",
        "description": "Eine allgemeine Frage zum Reiseplan beantworten, wenn keine andere Aktion passt.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }},
]


class TripState(TypedDict):
    trip: dict
    message: str
    reply: dict
    tool_name: str


def _orchestrator_node(state: TripState) -> TripState:
    messages = [
        {"role": "system", "content": prompts.ORCHESTRATOR},
        {"role": "user", "content": state["message"]},
    ]
    kind, value, _args = llm.call_tools("orchestrator", messages, TOOLS, prompt_id="ORCHESTRATOR")
    if kind == "tool" and value in TOOL_NAMES:
        tool_name = value
    else:
        tool_name = "answer_question"
    llm.log_step("orchestrator", f"Entscheidung → {tool_name}")
    print(f"[orchestrator] → {tool_name}")
    return {**state, "tool_name": tool_name}


def _route(state: TripState) -> str:
    return state["tool_name"]


def _make_handler_node(tool_name: str):
    def node(state: TripState) -> TripState:
        from agents import coordinator as coord
        handler_map = {
            "change_time": coord._change_time_from_chat,
            "replan_day": coord._replan_day_or_section_from_chat,
            "suggest_alternatives": coord._suggest_alternatives_from_chat,
            "delete_activity": coord._delete_activity_from_chat,
            "fill_plan": coord._fill_plan_from_chat,
            "replace_activity": coord._replace_activity_from_chat,
            "add_activity": coord._add_activity_from_chat,
            "sync_calendar": coord._try_sync_calendar_from_chat,
            "answer_question": lambda trip, msg: coord._groq_response(
                trip, msg, os.getenv("GROQ_API_KEY", "")
            ),
        }
        fn = handler_map[tool_name]
        reply = fn(state["trip"], state["message"])
        if reply is None:
            reply = coord._rule_based_response(state["trip"], state["message"])
        return {**state, "reply": reply}
    return node


_compiled_graph = None


def _get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        builder = StateGraph(TripState)
        builder.add_node("orchestrator", _orchestrator_node)
        for name in TOOL_NAMES:
            builder.add_node(name, _make_handler_node(name))
        builder.set_entry_point("orchestrator")
        builder.add_conditional_edges("orchestrator", _route, {name: name for name in TOOL_NAMES})
        for name in TOOL_NAMES:
            builder.add_edge(name, END)
        _compiled_graph = builder.compile()
    return _compiled_graph


def run_chat(trip: dict, message: str) -> dict:
    graph = _get_graph()
    state = graph.invoke({
        "trip": trip,
        "message": message,
        "reply": {},
        "tool_name": "answer_question",
    })
    return state["reply"]
