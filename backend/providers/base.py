"""Reservation provider interface + Pydantic domain models.

This abstraction is the legal firewall: the demo runs against MockResyProvider,
and LiveResyProvider is a stub that is never enabled. The interface exists so
the day a partnership exists, we flip a flag.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Restaurant(BaseModel):
    id: str
    name: str
    cuisine: str
    neighborhood: str
    borough: str
    vibe: str
    price_tier: int = Field(ge=1, le=5)
    dress_code: str
    typical_party_sizes: list[int]
    difficulty: int = Field(ge=1, le=5, description="1=easy, 5=Carbone-tier")
    editorial: str
    tags: list[str] = Field(default_factory=list)


class Slot(BaseModel):
    id: str
    restaurant_id: str
    datetime: datetime
    party_size: int = Field(ge=1, le=20)
    table_type: str = "main-dining"
    duration_minutes: int = 90


class Booking(BaseModel):
    id: str
    slot_id: str
    restaurant_id: str
    user_id: str
    status: Literal["confirmed", "cancelled", "pending"]
    confirmation_code: str
    booked_at: datetime


class ReservationProvider(ABC):
    """Abstract reservation provider. Two implementations:
    - MockResyProvider: deterministic, used for demo and dev.
    - LiveResyProvider: stub, never enabled (legal firewall).
    """

    @abstractmethod
    def list_restaurants(self) -> list[Restaurant]: ...

    @abstractmethod
    def get_restaurant(self, restaurant_id: str) -> Restaurant | None: ...

    @abstractmethod
    def list_open_slots(
        self,
        restaurant_id: str,
        start: datetime,
        end: datetime,
        party_size: int,
    ) -> list[Slot]: ...

    @abstractmethod
    def book_slot(
        self,
        slot_id: str,
        user_id: str,
        confirmation_token: str,
    ) -> Booking: ...

    @abstractmethod
    def replay_fixture(self, fixture_id: str) -> Slot:
        """Demo-only: surface a fixture as if a slot just opened."""
        ...


def get_provider() -> ReservationProvider:
    """Factory: returns the configured provider. ALWAYS mock unless explicitly
    flipped via PROVIDER_MODE=live (which is a stub that raises)."""
    from backend.config import get_settings
    from backend.providers.mock_resy import MockResyProvider
    from backend.providers.live_resy import LiveResyProvider

    settings = get_settings()
    if settings.provider_mode == "live":
        return LiveResyProvider()
    return MockResyProvider()
