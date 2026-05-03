"""Auto-booker — tick-graph node. For each pending slot whose watch has
auto_book=True (the default), generates a Resy/OpenTable/Tock deep link the
user can tap to confirm in one step on the real platform.

We don't pretend to have booked the slot ourselves — the user's tap on the
deep-linked Resy page is the actual booking. This is the legal-and-real path:
agent does 99% of the work (find, rank, link, deliver); the user does the
final tap (which Resy's ToS effectively requires).

Consent is still given at watch creation. The deep link is delivered both
in-app and by email so the user can confirm from anywhere.
"""
from __future__ import annotations

from datetime import datetime as _dt

from backend.booking.deep_links import build_booking_url
from backend.memory.firestore_store import get_store
from backend.memory.state import AgentState
from backend.providers.base import get_provider
from backend.tools.reservation_tools import call_tool


def auto_booker_node(state: AgentState) -> dict:
    """Iterate pending slots; generate booking deep links for each."""
    pending = state.get("pending_slots", []) or []
    if not pending:
        return {"pending_slots": []}

    store = get_store()
    watches = {w.id: w for w in store.list_watches(active_only=True)}
    enriched: list[dict] = []

    for slot in pending:
        watch_id = slot.get("watch_id")
        watch = watches.get(watch_id) if watch_id else None
        if watch is None or not getattr(watch, "auto_book", True):
            slot["pending_user_confirm"] = False
            slot["booking_url"] = None
            slot["booking_platform"] = None
            enriched.append(slot)
            continue

        try:
            dt = _dt.fromisoformat(slot["datetime"])
        except Exception:
            dt = _dt.now()

        link = build_booking_url(
            slot["restaurant_id"], dt=dt, party_size=slot["party_size"]
        )
        slot["booking_url"] = link.get("url")
        slot["booking_platform"] = link.get("platform")
        slot["booking_note"] = link.get("note")
        slot["pending_user_confirm"] = True

        enriched.append(slot)

    return {"pending_slots": enriched}
