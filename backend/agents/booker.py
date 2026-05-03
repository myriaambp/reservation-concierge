"""Booker — HITL-gated booking. Only invoked when the user clicks Book in the UI
and the frontend has minted a confirmation_token tied to that interaction.

The HITL gate is enforced two ways:
1. The supervisor's prompt never calls book_slot directly.
2. The book_slot tool itself refuses on missing confirmation_token.

This is our 'we don't auto-book' guarantee — both technical and contractual.
"""
from __future__ import annotations

from backend.agents.prompts import BOOKER_PROMPT
from backend.config import get_settings
from backend.llm.client import chat
from backend.memory.state import AgentState
from backend.tools.reservation_tools import ANTHROPIC_TOOLS, call_tool

BOOKER_TOOLS = [t for t in ANTHROPIC_TOOLS if t["name"] in {"book_slot", "record_outcome"}]


def booker_node(state: AgentState) -> dict:
    settings = get_settings()
    scratchpad = state.get("scratchpad", {}) or {}
    slot_id = scratchpad.get("booking_slot_id")
    user_id = state.get("user_id")
    token = scratchpad.get("confirmation_token")
    watch_id = scratchpad.get("booking_watch_id")

    if not (slot_id and user_id and token):
        return {
            "final_response": (
                "Refused: no confirmation token. Tap Book again from the slot "
                "card to confirm."
            )
        }

    user_msg = (
        f"Confirm booking. slot_id={slot_id}, user_id={user_id}, "
        f"confirmation_token={token}"
    )

    resp = chat(
        model=settings.supervisor_model,
        system=BOOKER_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
        tools=BOOKER_TOOLS,
        max_tokens=512,
        agent_name="booker",
    )

    msgs: list[dict] = [{"role": "user", "content": user_msg}]
    final = ""
    for _ in range(3):
        tool_uses = [b for b in resp.content if b.type == "tool_use"]
        text_blocks = [b for b in resp.content if b.type == "text"]
        if not tool_uses:
            final = "\n".join(b.text for b in text_blocks).strip()
            break
        msgs.append(
            {"role": "assistant", "content": [b.model_dump() for b in resp.content]}
        )
        results = []
        for tu in tool_uses:
            r = call_tool(tu.name, tu.input)
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": str(r),
                }
            )
        msgs.append({"role": "user", "content": results})
        resp = chat(
            model=settings.supervisor_model,
            system=BOOKER_PROMPT,
            messages=msgs,
            tools=BOOKER_TOOLS,
            max_tokens=512,
            agent_name="booker",
        )

    if watch_id:
        call_tool("record_outcome", {"watch_id": watch_id, "outcome": "booked"})

    return {"final_response": final or "Booked."}
