"""LiveResyProvider — STUB ONLY. Never enabled in any deployed environment.

This file exists to demonstrate the abstraction is real. It must NOT be
implemented or invoked. If you need to swap in real availability data, do it
through a partner relationship and a sanctioned API, not by reverse-engineering
Resy / OpenTable's web app.
"""
from __future__ import annotations

from backend.providers.base import (
    Booking,
    ReservationProvider,
    Restaurant,
    Slot,
)


class LiveResyProvider(ReservationProvider):
    def _refuse(self) -> None:
        raise NotImplementedError(
            "LiveResyProvider is a stub. The product runs on MockResyProvider "
            "until a sanctioned partnership exists. See docs/one-pager.md."
        )

    def list_restaurants(self) -> list[Restaurant]:
        self._refuse()
        return []

    def get_restaurant(self, restaurant_id: str) -> Restaurant | None:
        self._refuse()
        return None

    def list_open_slots(self, *args, **kwargs) -> list[Slot]:
        self._refuse()
        return []

    def book_slot(self, *args, **kwargs) -> Booking:
        self._refuse()
        raise NotImplementedError

    def replay_fixture(self, fixture_id: str) -> Slot:
        self._refuse()
        raise NotImplementedError
