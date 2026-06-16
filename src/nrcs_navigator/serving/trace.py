"""Turn the agent's streamed execution into a sequence of UI trace events.

The serving layer exposes a streaming endpoint so the frontend can show the agent
working -- which tool it is calling and a one line summary of what came back --
before and while the final answer types out, the way a coding agent shows its
steps. LangGraph already emits this: streaming the agent with both "updates" and
"messages" modes yields each tool call, each tool result, and the final answer
token by token. This module translates those raw LangGraph chunks into small,
frontend friendly event dicts and abbreviates each tool result to a single line.

The tool steps stream live so the UI can show the agent working, but the final
answer is sent as one event when it is ready (no token streaming).

Event shapes (one JSON object per line on the wire):
    {"type": "step_start", "id": <tool_call_id>, "label": "Estimating payments"}
    {"type": "step_end",   "id": <tool_call_id>, "summary": "3 programs found"}
    {"type": "final",      "reply": "Based on ..."}
    {"type": "done"}
    {"type": "error",      "message": "..."}

Kept out of app.py so the abbreviation logic is unit testable without FastAPI.
"""

import ast
import json
import logging
import re

from langgraph.errors import GraphRecursionError

from nrcs_navigator import config

logger = logging.getLogger("nrcs_navigator.serving")

# Present tense labels shown in the live trace, keyed by the tool's registered
# name (the function name LangChain exposes). Falls back to the raw name.
TOOL_LABELS = {
    "eligibility_screener": "Screening eligibility",
    "payment_estimator": "Estimating payments",
    "practice_matcher": "Matching practice standards",
    "program_availability": "Checking program availability",
}

# Friendly message used when the ReAct loop is cut off by the recursion limit,
# mirroring the non streaming /chat endpoint so both paths read the same.
RECURSION_REPLY = (
    "I wasn't able to pull this together in time. Try narrowing the request, for "
    "example a single program or one practice, and include the client's state and "
    "operation type."
)


def label_for(name: str) -> str:
    return TOOL_LABELS.get(name, name.replace("_", " ").capitalize())


def _parse(content):
    """Best effort decode of a ToolMessage's content into a dict/list.

    ToolNode stringifies a tool's dict return, and depending on version that is
    either JSON or a Python repr (single quotes), so try both. Returns the parsed
    object, or None when the content is a plain string (the eligibility_screener
    case, handled by the caller).
    """
    if isinstance(content, (dict, list)):
        return content
    if not isinstance(content, str):
        return None
    try:
        return json.loads(content)
    except (ValueError, TypeError):
        pass
    try:
        return ast.literal_eval(content)
    except (ValueError, SyntaxError):
        return None


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}" + ("" if n == 1 else "s")


def summarize_tool_result(name: str, content) -> str:
    """Abbreviate a tool's result to a single line for the live trace.

    eligibility_screener returns the matched regulation text as a plain string
    (each section prefixed with its [citation]); the other three return a dict
    with a status and a count. Anything unexpected degrades to a short snippet.
    """
    if name == "eligibility_screener":
        text = content if isinstance(content, str) else str(content)
        sections = len(re.findall(r"(?m)^\[", text))
        if sections == 0:
            return "no matching CFR sections"
        return _plural(sections, "CFR section") + " matched"

    data = _parse(content)
    if not isinstance(data, dict):
        snippet = (content if isinstance(content, str) else str(content)).strip()
        return (snippet[:80] + "...") if len(snippet) > 80 else (snippet or "done")

    status = data.get("status")
    if status and status != "success":
        return str(data.get("message") or data.get("error") or "no results")

    if name == "payment_estimator":
        return _plural(len(data.get("programs", {})), "program") + " with funding history"
    if name == "practice_matcher":
        return _plural(int(data.get("practice_count", 0)), "practice standard")
    if name == "program_availability":
        count = data.get("program_count")
        if count is None:
            count = len(data.get("available_program_codes", []))
        return _plural(int(count), "program") + " with ranking dates"

    return "done"


def iter_agent_events(agent, message: str, session_id: str):
    """Run the agent for one turn and yield trace event dicts as they happen.

    Streams in "updates" mode: each chunk is one node's output, giving the tool
    calls as the agent decides them, the tool results as they return, and finally
    the assistant's answer. Tool calls and results become step events that stream
    live; the answer (an AI message with content and no tool calls) becomes a
    single "final" event.
    """
    cfg = {
        "configurable": {"thread_id": session_id},
        "recursion_limit": config.AGENT_RECURSION_LIMIT,
    }
    try:
        for update in agent.stream(
            {"messages": [("user", message)]},
            config=cfg,
            stream_mode="updates",
        ):
            yield from _events_from_update(update)
    except GraphRecursionError:
        logger.warning("recursion limit hit for session %s", session_id)
        yield {"type": "final", "reply": RECURSION_REPLY}
    except Exception:
        logger.exception("agent stream failed for session %s", session_id)
        yield {
            "type": "error",
            "message": "The navigator service hit an error handling that message.",
        }
        return
    yield {"type": "done"}


def _events_from_update(update: dict):
    """Translate one LangGraph "updates" chunk into step and final events.

    A tool calling step is an AI message with tool_calls (one step_start each);
    a tool node yields ToolMessages (one step_end each); the final answer is the
    AI message that carries content and no tool_calls.
    """
    for node, payload in update.items():
        messages = (payload or {}).get("messages", []) if isinstance(payload, dict) else []
        for msg in messages:
            tool_calls = getattr(msg, "tool_calls", None) or []
            for call in tool_calls:
                yield {
                    "type": "step_start",
                    "id": call.get("id"),
                    "label": label_for(call.get("name", "")),
                }
            if getattr(msg, "type", None) == "tool":
                # A ToolMessage carries the result of one tool call.
                yield {
                    "type": "step_end",
                    "id": getattr(msg, "tool_call_id", None),
                    "summary": summarize_tool_result(getattr(msg, "name", ""), msg.content),
                }
            elif getattr(msg, "type", None) == "ai" and not tool_calls:
                content = getattr(msg, "content", "")
                if isinstance(content, str) and content.strip():
                    yield {"type": "final", "reply": content}
