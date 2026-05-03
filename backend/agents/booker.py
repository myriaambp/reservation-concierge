"""Booker — handles two modes:

1. **Chat-mode HITL**: invoked from the chat graph after the user taps Book on
   a one-off slot the supervisor surfaced. Requires a UI-minted confirmation
   token in scratchpad.

2. **Tick-mode auto-confirm**: invoked from the tick graph when scout +
   ranker found a slot that matches an active watch with auto_book=True.
   Consent was given at watch creation; we self-mint a deterministic token
   so the book_slot tool's HITL gate is satisfied.

Either way, every booking attempt goes through the same `book_slot()` tool —
the gate exists for both auditability and so the LiveResyProvider stub never
fires unintended requests.
"""
from __future__ import annotations

import secrets

from backend.agents.prompts import BOOKER_PROMPT
from backend.config import get_settings
from backend.llm.client import chat
from backend.memory.state import AgentState
from backend.tools.reservation_tools import TOOL_SCHEMAS, call_tool

BOOKER_TOOLS = [t for t in TOOL_SCHEMAS if t["name"] in {"book_slot", "record_outcome"}]


def booker_node(state: AgentState) -> dict:
    settings = get_settings()
    scratchpad = state.get("scratchpad", {}) or {}
    user_id = state.get("user_id")
    auto_confirm = bool(scratchpad.get("auto_confirm"))

    if auto_confirm:
        # Tick path: consent was given at watch creation. We mint our own token
        # so the book_slot HITL gate accepts the call. The token is one-shot.
        slot_id = scratchpad.get("booking_slot_id")
        watch_id = scratchpad.get("booking_watch_id")
        if not (slot_id and user_id):
            return {"final_response": "auto-book skipped: missing slot or user"}
        token = scratchpad.get("confirmation_token") or f"auto-{secrets.token_hex(8)}"

        booking = call_tool(
            "book_slot",
            {
                "slot_id": slot_id,
                "user_id": user_id,
                "confirmation_token": token,
            },
        )
        if watch_id:
            call_tool("record_outcome", {"watch_id": watch_id, "outcome": "booked"})

        if booking.get("error"):
            return {
                "final_response": f"auto-book failed: {booking['error'][:140]}",
                "scratchpad": {**scratchpad, "booking_outcome": booking},
            }
        return {
            "final_response": (
                f"Booked. Confirmation: {booking.get('confirmation_code', '?')}."
            ),
            "scratchpad": {**scratchpad, "booking_outcome": booking},
        }

    # ---------- Chat-mode HITL: token must come from a UI tap ----------
    slot_id = scratchpad.get("booking_slot_id")
    token = scratchpad.get("confirmation_token")
    watch_id = scratchpad.get("booking_watch_id")

    if not (slot_id and user_id and token):
        return {
            "final_response": (
                "Refused: no confirmation token. Tap Book on the slot card to confirm."
            )
        }

    user_msg = (
        f"Confirm booking. slot_id={slot_id}, user_id={user_id}, "
        f"confirmation_token={token}"
    )
    msgs: list[dict] = [{"role": "user", "content": user_msg}]
    final = ""
    for _ in range(3):
        resp = chat(
            model=settings.supervisor_model,
            system=BOOKER_PROMPT,
            messages=msgs,
            tools=BOOKER_TOOLS,
            max_tokens=2048,
            agent_name="booker",
        )
        if not resp.tool_uses:
            final = resp.text
            break
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
        results = []
        for tu in resp.tool_uses:
            r = call_tool(tu.name, tu.input)
            results.append(
                {"type": "tool_result", "tool_use_id": tu.id, "name": tu.name, "content": str(r)}
            )
        msgs.append({"role": "user", "content": results})

    if watch_id:
        call_tool("record_outcome", {"watch_id": watch_id, "outcome": "booked"})

    return {"final_response": final or "Booked."}
