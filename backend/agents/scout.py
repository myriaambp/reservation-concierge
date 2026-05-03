"""Scout — tick-mode poller. Cron-triggered. NOT user-facing.

For each active watch:
1. Pull current open slots from the provider.
2. Hash the slot list. Compare to last snapshot.
3. If unchanged: short-circuit (NO LLM call). 95%+ of ticks land here, which is
   why our COGS stays under $3/user/month.
4. If changed: emit pending_slots for the Ranker.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from backend.memory.firestore_store import get_store
from backend.memory.state import AgentState
from backend.providers.base import get_provider


def _slot_hash(slots: list[Any]) -> str:
    if not slots:
        return "empty"
    canon = "|".join(
        f"{s.id}:{s.datetime.isoformat()}:{s.party_size}:{s.table_type}"
        for s in sorted(slots, key=lambda x: x.id)
    )
    return hashlib.sha256(canon.encode()).hexdigest()[:16]


def scout_node(state: AgentState) -> dict:
    """Run one tick across all active watches in scope."""
    store = get_store()
    provider = get_provider()
    user_id = state.get("user_id")
    watches = store.list_watches(user_id=user_id, active_only=True)

    pending: list[dict] = []
    for w in watches:
        try:
            start = datetime.fromisoformat(w.date_window_start).replace(
                tzinfo=timezone.utc
            )
            end = datetime.fromisoformat(w.date_window_end).replace(
                hour=23, minute=59, tzinfo=timezone.utc
            )
        except ValueError:
            continue

        slots = provider.list_open_slots(
            w.restaurant_id, start, end, w.party_size
        )

        # Hash-diff: short-circuit if unchanged.
        h = _slot_hash(slots)
        prev = store.get_snapshot(f"{w.id}")
        if prev == h:
            continue

        store.set_snapshot(f"{w.id}", h)

        # Filter time-of-day windows.
        for s in slots:
            t = s.datetime.time().isoformat(timespec="minutes")
            if w.time_window_start <= t <= w.time_window_end:
                pending.append(
                    {
                        "watch_id": w.id,
                        "user_id": w.user_id,
                        "slot_id": s.id,
                        "restaurant_id": s.restaurant_id,
                        "datetime": s.datetime.isoformat(),
                        "party_size": s.party_size,
                        "table_type": s.table_type,
                    }
                )

    return {"pending_slots": pending}
