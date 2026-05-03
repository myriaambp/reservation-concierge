"""Auto-booker — tick-graph node. For each pending slot whose watch was created
with auto_book=True (the default), books the table and records a confirmation
on the slot. Notifier picks up the result and writes "Booked: …" copy.

After a successful booking we ALSO fire a restaurant-style confirmation email
so the user receives both:
  1. The Tableau alert ("Booked: Don Angie 7:30pm Fri")
  2. A Resy/OpenTable-style receipt ("Reservation confirmed — Don Angie")

Consent model: the watch creation IS the consent record. The user explicitly
told us "book it if you find one matching these parameters." We don't loop a
human in at the moment of booking because we already did at the moment of
watching.
"""
from __future__ import annotations

import secrets
from datetime import datetime as _dt

from backend.memory.firestore_store import get_store
from backend.memory.state import AgentState
from backend.providers.base import get_provider
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
            # Fire the restaurant-style confirmation email. Best-effort.
            user_email = ""
            try:
                user_email = store.get_user(slot["user_id"]).email
            except Exception:
                pass
            if user_email and "@" in user_email:
                from backend.notifications.email import send_reservation_confirmation
                provider = get_provider()
                rest = provider.get_restaurant(slot["restaurant_id"])
                rest_name = rest.name if rest else slot["restaurant_id"]
                try:
                    dt = _dt.fromisoformat(slot["datetime"])
                    date_long = dt.strftime("%A, %B %-d, %Y")  # Friday, May 8, 2026
                    time_str = dt.strftime("%-I:%M %p")          # 7:30 PM
                except Exception:
                    date_long = slot["datetime"]
                    time_str = ""
                send_reservation_confirmation(
                    to=user_email,
                    restaurant=rest_name,
                    date_long=date_long,
                    time_str=time_str,
                    party_size=slot["party_size"],
                    table_type=slot["table_type"],
                    confirmation_code=slot["confirmation_code"],
                )
                slot["restaurant_email_sent"] = True
        booked.append(slot)

    return {"pending_slots": booked}
