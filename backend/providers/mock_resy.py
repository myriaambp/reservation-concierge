"""Deterministic mock reservation provider.

Generates plausible availability for ~30 NYC hard-to-book restaurants based on a
seeded RNG keyed on (restaurant_id, date). High-difficulty restaurants surface
fewer slots; low-difficulty surface more. Supports fixture replay for live demo.
"""
from __future__ import annotations

import hashlib
import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from backend.providers.base import (
    Booking,
    ReservationProvider,
    Restaurant,
    Slot,
)

_SEED_DIR = Path(__file__).resolve().parents[2] / "seed_data"
_RESTAURANTS_PATH = _SEED_DIR / "restaurants.json"
_FIXTURES_PATH = _SEED_DIR / "fixtures.json"


def _det_seed(*parts: str) -> int:
    h = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big")


class MockResyProvider(ReservationProvider):
    def __init__(self) -> None:
        with _RESTAURANTS_PATH.open() as f:
            self._restaurants = {r["id"]: Restaurant(**r) for r in json.load(f)}
        with _FIXTURES_PATH.open() as f:
            self._fixtures = {fx["id"]: fx for fx in json.load(f)["events"]}

    def list_restaurants(self) -> list[Restaurant]:
        return list(self._restaurants.values())

    def get_restaurant(self, restaurant_id: str) -> Restaurant | None:
        return self._restaurants.get(restaurant_id)

    def list_open_slots(
        self,
        restaurant_id: str,
        start: datetime,
        end: datetime,
        party_size: int,
    ) -> list[Slot]:
        rest = self._restaurants.get(restaurant_id)
        if rest is None:
            return []

        slots: list[Slot] = []
        # Walk dinner service per day in the requested range.
        cursor = start.replace(hour=17, minute=0, second=0, microsecond=0)
        end_walk = end.replace(hour=22, minute=30)

        while cursor <= end_walk:
            day = cursor.date()
            # Generate candidate dinner times: 17:30, 18:00, ..., 22:00
            for hour in range(17, 23):
                for minute in (0, 30):
                    dt = cursor.replace(hour=hour, minute=minute)
                    if dt < start or dt > end:
                        continue

                    seed = _det_seed(
                        restaurant_id, dt.isoformat(), str(party_size)
                    )
                    rng = random.Random(seed)

                    # Higher difficulty => lower availability probability.
                    # Also: party_size mismatches with typical sizes hurt.
                    p_open = 0.30 - (rest.difficulty - 1) * 0.06
                    if party_size not in rest.typical_party_sizes:
                        p_open *= 0.4
                    # Late slots (>= 21:30) more likely to be open.
                    if hour >= 21:
                        p_open *= 1.6
                    p_open = max(0.02, min(0.6, p_open))

                    if rng.random() < p_open:
                        slots.append(
                            Slot(
                                id=f"slot-{seed:x}",
                                restaurant_id=restaurant_id,
                                datetime=dt,
                                party_size=party_size,
                                table_type=rng.choice(
                                    ["main-dining", "bar", "two-top"]
                                ),
                                duration_minutes=90,
                            )
                        )

            cursor = cursor + timedelta(days=1)
            cursor = cursor.replace(hour=17, minute=0)

        return slots

    def book_slot(
        self,
        slot_id: str,
        user_id: str,
        confirmation_token: str,
    ) -> Booking:
        # In mock mode, every confirmed call succeeds. The HITL gate enforced
        # at the agent layer is what prevents "auto-booking without consent".
        if not confirmation_token:
            raise ValueError("confirmation_token required (HITL gate)")
        return Booking(
            id=f"bkg-{uuid.uuid4().hex[:8]}",
            slot_id=slot_id,
            restaurant_id=slot_id.split("-")[0] if "-" in slot_id else "",
            user_id=user_id,
            status="confirmed",
            confirmation_code=f"TBL-{uuid.uuid4().hex[:6].upper()}",
            booked_at=datetime.now(timezone.utc),
        )

    def replay_fixture(self, fixture_id: str) -> Slot:
        fx = self._fixtures.get(fixture_id)
        if fx is None:
            raise KeyError(f"unknown fixture: {fixture_id}")
        return Slot(
            id=f"slot-fx-{fixture_id}",
            restaurant_id=fx["restaurant_id"],
            datetime=datetime.fromisoformat(fx["slot"]["datetime"]),
            party_size=fx["slot"]["party_size"],
            table_type=fx["slot"]["table_type"],
            duration_minutes=fx["slot"]["duration_minutes"],
        )

    def fixture_ids(self) -> Iterable[str]:
        return self._fixtures.keys()

    def fixture(self, fixture_id: str) -> dict | None:
        return self._fixtures.get(fixture_id)
