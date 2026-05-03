"""Supervisor — chat-mode entrypoint. Receives user message, decides actions
via tool use, returns a final natural-language reply.

Class concepts on display:
- Tool calling: bound to the full ANTHROPIC_TOOLS schema.
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
from backend.tools.reservation_tools import ANTHROPIC_TOOLS, call_tool

# Tools the Supervisor can invoke directly. Booker has its own narrower set.
SUPERVISOR_TOOLS = [
    t for t in ANTHROPIC_TOOLS
    if t["name"] in {
        "search_restaurants",
        "get_user_prefs",
        "add_watch",
        "list_open_slots",
        "rag_lookup",
        "record_outcome",
    }
]


def _to_anthropic_messages(state: AgentState) -> list[dict[str, Any]]:
    """Convert LangGraph messages to Anthropic message format."""
    out = []
    for m in state.get("messages", []):
        role = "user" if getattr(m, "type", None) == "human" else "assistant"
        # Handle both LangChain message types and dicts.
        content = getattr(m, "content", None) or m.get("content", "")
        out.append({"role": role, "content": content})
    return out


def supervisor_node(state: AgentState) -> dict:
    """Run the supervisor: tool-use loop until a final text answer is returned."""
    settings = get_settings()
    msgs = _to_anthropic_messages(state)

    # Inject user_id context the model would otherwise have to ask for.
    if msgs:
        msgs[-1]["content"] = (
            f"[user_id={state.get('user_id', 'demo-user')}] "
            f"{msgs[-1]['content']}"
        )

    final_text: str = ""
    for _ in range(6):  # safety: bounded tool-use loop
        resp = chat(
            model=settings.supervisor_model,
            system=SUPERVISOR_PROMPT,
            messages=msgs,
            tools=SUPERVISOR_TOOLS,
            max_tokens=1024,
            agent_name="supervisor",
        )

        # Collect tool_use blocks; if none, we're done.
        tool_uses = [b for b in resp.content if b.type == "tool_use"]
        text_blocks = [b for b in resp.content if b.type == "text"]

        if not tool_uses:
            final_text = "\n".join(b.text for b in text_blocks).strip()
            break

        # Append the assistant turn (with tool_use blocks) and tool results.
        msgs.append(
            {
                "role": "assistant",
                "content": [b.model_dump() for b in resp.content],
            }
        )
        tool_results = []
        for tu in tool_uses:
            result = call_tool(tu.name, tu.input)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": str(result),
                }
            )
        msgs.append({"role": "user", "content": tool_results})

    return {
        "final_response": final_text or "Done.",
        "messages": [{"role": "assistant", "content": final_text or "Done."}],
    }
