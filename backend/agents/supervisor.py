"""Supervisor — chat-mode entrypoint. Receives user message, decides actions
via tool use, returns a final natural-language reply.

Class concepts on display:
- Tool calling: bound to TOOL_SCHEMAS (portable JSON-Schema format,
  converted to Gemini FunctionDeclarations inside backend.llm.client).
- Multi-agent orchestration: conditionally routes to BookerAgent when the user
  is confirming a booking (HITL pivot).
- Context engineering: SUPERVISOR_PROMPT is versioned in prompts.py.
- Constrained decoding: every tool input is Pydantic-validated.
"""
from __future__ import annotations

from typing import Any

from backend.agents.prompts import SUPERVISOR_PROMPT
from backend.config import get_settings
from backend.llm.client import chat
from backend.memory.state import AgentState
from backend.tools.reservation_tools import TOOL_SCHEMAS, call_tool

# Tools the Supervisor can invoke directly. Booker has its own narrower set.
SUPERVISOR_TOOLS = [
    t for t in TOOL_SCHEMAS
    if t["name"] in {
        "search_restaurants",
        "get_user_prefs",
        "list_watches",
        "add_watch",
        "list_open_slots",
        "rag_lookup",
        "record_outcome",
    }
]


def _to_message_dicts(state: AgentState) -> list[dict[str, Any]]:
    """Convert LangGraph messages into the unified message-dict format used by
    backend.llm.client (Anthropic-shape, translated to Gemini downstream).
    """
    out = []
    for m in state.get("messages", []):
        role = "user" if getattr(m, "type", None) == "human" else "assistant"
        # Handle both LangChain message types and dicts.
        content = getattr(m, "content", None) or m.get("content", "")
        out.append({"role": role, "content": content})
    return out


def supervisor_node(state: AgentState) -> dict:
    """Run the supervisor: tool-use loop until a final text answer is returned."""
    from datetime import date

    settings = get_settings()
    msgs = _to_message_dicts(state)

    # Inject (today, user_id) into the latest user message so the model resolves
    # relative dates ("next Friday") correctly and never has to ask for IDs.
    if msgs:
        msgs[-1]["content"] = (
            f"[today={date.today().isoformat()} "
            f"user_id={state.get('user_id', 'demo-user')}] "
            f"{msgs[-1]['content']}"
        )

    final_text: str = ""
    for _ in range(6):  # safety: bounded tool-use loop
        resp = chat(
            model=settings.supervisor_model,
            system=SUPERVISOR_PROMPT,
            messages=msgs,
            tools=SUPERVISOR_TOOLS,
            max_tokens=2048,  # Flash thinking budget can eat into smaller caps
            agent_name="supervisor",
        )

        if not resp.tool_uses:
            final_text = resp.text
            break

        # Append the assistant turn (with tool_use blocks) and tool results.
        msgs.append(
            {
                "role": "assistant",
                "content": [
                    *([{"type": "text", "text": resp.text}] if resp.text else []),
                    *[
                        {"type": "tool_use", "id": tu.id, "name": tu.name, "input": tu.input}
                        for tu in resp.tool_uses
                    ],
                ],
            }
        )
        tool_results = []
        for tu in resp.tool_uses:
            result = call_tool(tu.name, tu.input)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "name": tu.name,
                    "content": str(result),
                }
            )
        msgs.append({"role": "user", "content": tool_results})

    return {
        "final_response": final_text or "Done.",
        "messages": [{"role": "assistant", "content": final_text or "Done."}],
    }
