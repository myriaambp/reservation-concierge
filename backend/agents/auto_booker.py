"""Auto-booker — tick-graph node. For each pending slot whose watch was created
with auto_book=True (the default), books the table and records a confirmation
on the slot. Notifier picks up the result and writes "Booked: …" copy.

Consent model: the watch creation IS the consent record. The user explicitly
told us "book it if you find one matching these parameters." We don't loop a
human in at the moment of booking because we already did at the moment of
watching.
"""
from __future__ import annotations

import secrets

from backend.memory.firestore_store import get_store
from backend.memory.state import AgentState
from backend.tools.reservation_tools import call_tool


def auto_booker_node(state: AgentState) -> dict:
    """Iterate pending slots; auto-book any tied to an auto_book=True watch."""
    pending = state.get("pending_slots", []) or []
    if not pending:
        return {"pending_slots": []}

    store = get_store()

    # Pre-fetch watches once, index by id, so we don't hit the store per slot.
    watches = {w.id: w for w in store.list_watches(active_only=True)}

    booked: list[dict] = []
    for slot in pending:
        watch_id = slot.get("watch_id")
        watch = watches.get(watch_id) if watch_id else None
        if watch is None or not getattr(watch, "auto_book", True):
            # Not an auto-book watch. Pass through so notifier can write a
            # "Tap to book" card instead.
            slot["auto_booked"] = False
            booked.append(slot)
            continue

        token = f"auto-{secrets.token_hex(8)}"
        booking = call_tool(
            "book_slot",
            {
                "slot_id": slot["slot_id"],
                "user_id": slot["user_id"],
                "confirmation_token": token,
            },
        )
        if booking.get("error"):
            slot["auto_booked"] = False
            slot["booking_error"] = booking["error"][:160]
        else:
            slot["auto_booked"] = True
            slot["confirmation_code"] = booking.get("confirmation_code", "")
            slot["booked_at"] = booking.get("booked_at", "")
            # Cancel the watch — it's done.
            call_tool(
                "record_outcome",
                {"watch_id": watch_id, "outcome": "booked"},
            )
        booked.append(slot)

    return {"pending_slots": booked}
