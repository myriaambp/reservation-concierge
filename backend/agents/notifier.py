"""Notifier — turns a ranked slot into a notification payload, fires it,
and records to history.

Class concepts: tool calling (send_notification), context engineering, memory.
"""
from __future__ import annotations

import json

from backend.agents.prompts import NOTIFIER_PROMPT
from backend.config import get_settings
from backend.llm.client import chat
from backend.memory.state import AgentState
from backend.tools.reservation_tools import call_tool


def notifier_node(state: AgentState) -> dict:
    settings = get_settings()
    pending = state.get("pending_slots", [])
    sent: list[dict] = []

    from datetime import datetime as _dt

    for slot in pending[:3]:  # throttle: never spam more than 3 per tick per user
        # Pre-compute day-of-week + readable time so the LLM doesn't have to.
        try:
            dt = _dt.fromisoformat(slot["datetime"])
            day_short = dt.strftime("%a")  # Mon, Tue, ...
            day_long = dt.strftime("%A %b %-d")
            t_str = dt.strftime("%-I:%M%p").lower().replace(":00", "")
        except Exception:
            day_short = day_long = t_str = ""

        slot_summary = {
            k: slot.get(k)
            for k in [
                "restaurant_name",
                "party_size",
                "table_type",
                "booking_platform",
                "booking_url",
            ]
        }
        slot_summary["day_short"] = day_short  # e.g. "Fri"
        slot_summary["day_long"] = day_long    # e.g. "Friday May 8"
        slot_summary["time_str"] = t_str       # e.g. "7:30pm"
        prompt_input = (
            f"Slot: {json.dumps(slot_summary)}\n"
            f"Rationale: {slot.get('rationale', '')}\n"
            f"Pending user confirm: {bool(slot.get('pending_user_confirm'))}"
        )
        resp = chat(
            model=settings.worker_model,
            system=NOTIFIER_PROMPT,
            messages=[{"role": "user", "content": prompt_input}],
            max_tokens=400,
            agent_name="notifier",
            temperature=0.2,
            disable_thinking=True,  # JSON template-fill, no need to think
        )
        text = resp.text
        # Gemini sometimes wraps JSON in ```json ... ``` fences.
        if text.startswith("```"):
            inner = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if inner.endswith("```"):
                inner = inner.rsplit("```", 1)[0]
            text = inner.strip()

        # Best-effort JSON parse; fall back to plain text on failure.
        subject = slot.get("restaurant_name", "Slot")
        body = slot.get("rationale", "Slot opened.")
        try:
            parsed = json.loads(text)
            subject = parsed.get("subject", subject)
            body = parsed.get("body", body)
        except json.JSONDecodeError:
            pass

        # Fire via tool — records to store + sends email.
        call_tool(
            "send_notification",
            {
                "user_id": slot["user_id"],
                "channel": "in_app",
                "subject": subject,
                "body": body,
                "slot_id": slot["slot_id"],
                "booking_url": slot.get("booking_url"),
                "booking_platform": slot.get("booking_platform"),
            },
        )
        sent.append(
            {
                "slot_id": slot["slot_id"],
                "subject": subject,
                "body": body,
                "booking_url": slot.get("booking_url"),
                "booking_platform": slot.get("booking_platform"),
            }
        )

    return {"scratchpad": {"notifications_sent": sent}}
