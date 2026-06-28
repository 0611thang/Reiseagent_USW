import os
import json

STEPS = []


def reset_trace():
    STEPS.clear()


def log_step(agent, info, tool=""):
    STEPS.append({"agent": agent, "info": info, "tool": tool})


def get_trace():
    return list(STEPS)


def call_tools(agent_name, messages, tools, prompt_id="", model="llama-3.3-70b-versatile"):
    """
    Tool-Calling via Groq. Gibt ("tool", name, args) oder ("text", content, {}) zurück.
    Bei fehlendem Key oder Fehler: ("text", "", {}).
    """
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        log_step(agent_name, f"[{prompt_id}] call_tools skipped — kein API-Key")
        return ("text", "", {})

    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        msg = response.choices[0].message
        if msg.tool_calls:
            tc = msg.tool_calls[0]
            name = tc.function.name
            args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            log_step(agent_name, f"[{prompt_id}] tool_call → {name}")
            print(f"[{agent_name}] tool → {name}")
            return ("tool", name, args)
        content = msg.content or ""
        log_step(agent_name, f"[{prompt_id}] text → {len(content)} Zeichen")
        return ("text", content, {})
    except Exception as e:
        log_step(agent_name, f"[{prompt_id}] call_tools error — {type(e).__name__}")
        return ("text", "", {})


def call(agent_name, prompt, prompt_id="", variables=None, max_tokens=500, model="llama-3.3-70b-versatile"):
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        log_step(agent_name, f"[{prompt_id}] skipped — kein API-Key")
        return None

    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )
        text = response.choices[0].message.content
        short = text[:80].replace("\n", " ")
        log_step(agent_name, f"[{prompt_id}] → {len(text)} Zeichen: {short}…")
        print(f"[{agent_name}] LLM → {len(text)} Zeichen")
        return text
    except Exception as e:
        log_step(agent_name, f"[{prompt_id}] error — {type(e).__name__}")
        return None
