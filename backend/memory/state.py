"""LangGraph state schema — the per-conversation working memory.

This is the **memory / state** class concept artifact. The State TypedDict is
the single source of truth that flows between agents in the graph. Persistent
data (user prefs, watches, snapshots) lives in MemoryStore (firestore_store).
"""
from __future__ import annotations

from typing import Annotated, Any
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class Watch(BaseModel):
    id: str
    user_id: str
    restaurant_id: str
    party_size: int
    date_window_start: str  # ISO date
    date_window_end: str
    time_window_start: str = "17:30"  # HH:MM
    time_window_end: str = "22:00"
    created_at: str
    active: bool = True
    # Auto-book = consent given at watch creation. The user explicitly opts in
    # to "book it if you find one matching these parameters." Default ON.
    auto_book: bool = True


class UserPrefs(BaseModel):
    user_id: str
    name: str = "Guest"
    email: str = ""
    cuisines_loved: list[str] = Field(default_factory=list)
    cuisines_avoided: list[str] = Field(default_factory=list)
    neighborhoods: list[str] = Field(default_factory=list)
    default_party_size: int = 2
    dietary: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=lambda: ["in_app", "email"])
    skipped_restaurants: list[str] = Field(default_factory=list)
    booked_restaurants: list[str] = Field(default_factory=list)


class PendingSlot(BaseModel):
    slot_id: str
    restaurant_id: str
    datetime: str
    party_size: int
    table_type: str
    score: float = 0.0
    rationale: str = ""


class AgentState(TypedDict, total=False):
    """The shared state that flows between all 5 agents.

    `messages` uses LangGraph's add_messages reducer so each node can
    append without overwriting.
    """

    user_id: str
    messages: Annotated[list, add_messages]
    intent: str  # set by Supervisor
    watches: list[dict]  # serialized Watch objects
    user_prefs: dict  # serialized UserPrefs
    pending_slots: list[dict]  # serialized PendingSlot objects
    scratchpad: dict[str, Any]  # per-turn working memory
    next_action: str  # routing target
    final_response: str  # what we tell the user
