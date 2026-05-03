"""Anthropic tool surface — the **tool calling** class concept artifact.

Each tool is:
1. A Pydantic input model (the **constrained decoding** class concept artifact;
   Anthropic feeds the JSON Schema to the model so outputs are guaranteed-shape).
2. A pure Python implementation that calls into providers / store / RAG.

Tools are exposed to LangGraph via `ANTHROPIC_TOOLS` (schemas) and
`TOOL_DISPATCH` (name → callable). Agents reference these by name.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from pydantic import BaseModel, Field

from backend.memory.firestore_store import get_store
from backend.memory.state import UserPrefs, Watch
from backend.providers.base import get_provider


# --------- Pydantic input models (constrained decoding) ----------

class SearchRestaurantsInput(BaseModel):
    query: str = Field(description="Free-text search, e.g. 'romantic Italian West Village'")
    cuisine: str | None = Field(default=None, description="Filter to a cuisine, optional")
    neighborhood: str | None = Field(default=None, description="Neighborhood filter, optional")
    max_difficulty: int | None = Field(default=None, ge=1, le=5)


class GetUserPrefsInput(BaseModel):
    user_id: str


class ListWatchesInput(BaseModel):
    user_id: str
    active_only: bool = True


class AddWatchInput(BaseModel):
    user_id: str
    restaurant_id: str
    party_size: int = Field(ge=1, le=20)
    date_window_start: str = Field(description="ISO date YYYY-MM-DD, inclusive")
    date_window_end: str = Field(description="ISO date YYYY-MM-DD, inclusive")
    time_window_start: str = "17:30"
    time_window_end: str = "22:00"


class ListOpenSlotsInput(BaseModel):
    restaurant_id: str
    date_window_start: str
    date_window_end: str
    party_size: int


class BookSlotInput(BaseModel):
    slot_id: str
    user_id: str
    confirmation_token: str = Field(
        description="HITL gate. Must be the user-provided token from the UI confirm step. Without it, the call refuses."
    )


class RagLookupInput(BaseModel):
    query: str
    k: int = 5


class SendNotificationInput(BaseModel):
    user_id: str
    channel: str = Field(description="'in_app' or 'email'")
    subject: str
    body: str
    slot_id: str | None = None
    booking_url: str | None = Field(
        default=None,
        description="Deep link the user taps to confirm on Resy/Tock/OpenTable.",
    )
    booking_platform: str | None = None


class RecordOutcomeInput(BaseModel):
    watch_id: str
    outcome: str = Field(description="'booked' | 'missed' | 'cancelled' | 'declined'")


class ReplayFixtureInput(BaseModel):
    fixture_id: str = Field(description="Demo-only. Replays a seeded slot-open event.")


# --------- implementations ----------

def search_restaurants(args: dict) -> dict:
    inp = SearchRestaurantsInput(**args)
    provider = get_provider()
    results = []
    q_lower = inp.query.lower()
    for r in provider.list_restaurants():
        if inp.cuisine and inp.cuisine.lower() not in r.cuisine.lower():
            continue
        if inp.neighborhood and inp.neighborhood.lower() not in r.neighborhood.lower():
            continue
        if inp.max_difficulty is not None and r.difficulty > inp.max_difficulty:
            continue
        # Cheap relevance: substring match on name/cuisine/vibe/tags/editorial.
        haystack = " ".join(
            [r.name, r.cuisine, r.vibe, " ".join(r.tags), r.editorial]
        ).lower()
        if q_lower and not any(tok in haystack for tok in q_lower.split()):
            continue
        results.append(
            {
                "id": r.id,
                "name": r.name,
                "cuisine": r.cuisine,
                "neighborhood": r.neighborhood,
                "difficulty": r.difficulty,
                "vibe": r.vibe,
                "snippet": r.editorial[:200],
            }
        )
    return {"results": results[:8], "count": len(results)}


def get_user_prefs(args: dict) -> dict:
    inp = GetUserPrefsInput(**args)
    return get_store().get_user(inp.user_id).model_dump()


def list_watches(args: dict) -> dict:
    inp = ListWatchesInput(**args)
    watches = get_store().list_watches(user_id=inp.user_id, active_only=inp.active_only)
    return {
        "watches": [w.model_dump() for w in watches],
        "count": len(watches),
    }


def add_watch(args: dict) -> dict:
    inp = AddWatchInput(**args)
    watch = Watch(
        id=f"wch-{uuid.uuid4().hex[:8]}",
        user_id=inp.user_id,
        restaurant_id=inp.restaurant_id,
        party_size=inp.party_size,
        date_window_start=inp.date_window_start,
        date_window_end=inp.date_window_end,
        time_window_start=inp.time_window_start,
        time_window_end=inp.time_window_end,
        created_at=datetime.now(timezone.utc).isoformat(),
        active=True,
    )
    get_store().add_watch(watch)
    return {"watch_id": watch.id, "ok": True, "summary": _watch_summary(watch)}


def _watch_summary(w: Watch) -> str:
    return (
        f"Watching {w.restaurant_id} for party of {w.party_size}, "
        f"{w.date_window_start} → {w.date_window_end} between "
        f"{w.time_window_start}–{w.time_window_end}."
    )


def list_open_slots(args: dict) -> dict:
    inp = ListOpenSlotsInput(**args)
    provider = get_provider()
    start = datetime.fromisoformat(inp.date_window_start).replace(
        tzinfo=timezone.utc
    )
    end = datetime.fromisoformat(inp.date_window_end).replace(
        hour=23, minute=59, tzinfo=timezone.utc
    )
    slots = provider.list_open_slots(
        inp.restaurant_id, start, end, inp.party_size
    )
    return {
        "slots": [s.model_dump(mode="json") for s in slots[:10]],
        "count": len(slots),
    }


def book_slot(args: dict) -> dict:
    inp = BookSlotInput(**args)
    provider = get_provider()
    booking = provider.book_slot(inp.slot_id, inp.user_id, inp.confirmation_token)
    get_store().record_booking(booking.model_dump(mode="json"))
    return booking.model_dump(mode="json")


def rag_lookup(args: dict) -> dict:
    """Lazy import — RAG retriever loads embeddings at module init."""
    from backend.rag.retriever import retrieve

    inp = RagLookupInput(**args)
    docs = retrieve(inp.query, k=inp.k)
    return {"docs": docs}


def send_notification(args: dict) -> dict:
    inp = SendNotificationInput(**args)
    payload = {
        "id": f"ntf-{uuid.uuid4().hex[:8]}",
        "user_id": inp.user_id,
        "channel": inp.channel,
        "subject": inp.subject,
        "body": inp.body,
        "slot_id": inp.slot_id,
        "booking_url": inp.booking_url,
        "booking_platform": inp.booking_platform,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    store = get_store()

    # Best-effort: also fire a real email if the user has one saved.
    email_status = "skipped"
    user_email = ""
    try:
        user = store.get_user(inp.user_id)
        user_email = user.email
    except Exception:
        pass

    if user_email and "@" in user_email:
        from backend.notifications.email import send_email
        cta = (
            f"Confirm on {inp.booking_platform.capitalize()} →"
            if inp.booking_platform else "Confirm reservation →"
        )
        result = send_email(
            user_email,
            inp.subject,
            inp.body,
            slot_url=inp.booking_url,
            cta_label=cta,
        )
        email_status = f"{result.provider}:{'ok' if result.ok else 'fail'}"
        payload["email_status"] = email_status
        payload["email_to"] = user_email

    store.record_notification(payload)
    return {
        "ok": True,
        "notification_id": payload["id"],
        "email_status": email_status,
    }


def record_outcome(args: dict) -> dict:
    inp = RecordOutcomeInput(**args)
    if inp.outcome == "booked":
        # Cancel the watch (it's done).
        get_store().cancel_watch(inp.watch_id)
    return {"ok": True}


def replay_fixture(args: dict) -> dict:
    inp = ReplayFixtureInput(**args)
    provider = get_provider()
    slot = provider.replay_fixture(inp.fixture_id)
    return slot.model_dump(mode="json")


# --------- Anthropic-format tool schemas (one source of truth) ----------

def _schema(model: type[BaseModel]) -> dict:
    """Pydantic v2 model -> Anthropic tool input_schema."""
    s = model.model_json_schema()
    # Anthropic wants top-level "type": "object" + "properties"; pydantic v2
    # delivers that natively, but strip $defs/extras for cleanliness.
    return {
        "type": "object",
        "properties": s.get("properties", {}),
        "required": s.get("required", []),
    }


ANTHROPIC_TOOLS: list[dict] = [
    {
        "name": "search_restaurants",
        "description": "Search the curated NYC hard-to-book restaurant catalog. Use for ambiguous user queries before adding a watch.",
        "input_schema": _schema(SearchRestaurantsInput),
    },
    {
        "name": "get_user_prefs",
        "description": "Load the user's saved preferences (cuisines, neighborhoods, party size, dietary, channels).",
        "input_schema": _schema(GetUserPrefsInput),
    },
    {
        "name": "list_watches",
        "description": "List active watches for the user. Use when the user asks 'what are you watching for me' or wants to review/cancel.",
        "input_schema": _schema(ListWatchesInput),
    },
    {
        "name": "add_watch",
        "description": "Register a watch on a restaurant for a date/time window. Returns watch_id.",
        "input_schema": _schema(AddWatchInput),
    },
    {
        "name": "list_open_slots",
        "description": "List currently-open reservation slots for a restaurant in a date range.",
        "input_schema": _schema(ListOpenSlotsInput),
    },
    {
        "name": "book_slot",
        "description": "Book a specific slot. REQUIRES a confirmation_token from the user-facing UI confirm step. Refuses without one (HITL gate).",
        "input_schema": _schema(BookSlotInput),
    },
    {
        "name": "rag_lookup",
        "description": "Retrieve restaurant editorial context (Eater 38, NYT 100, food-media snippets) for ranking and explanation. Returns top-k passages.",
        "input_schema": _schema(RagLookupInput),
    },
    {
        "name": "send_notification",
        "description": "Send an in-app or email notification to the user.",
        "input_schema": _schema(SendNotificationInput),
    },
    {
        "name": "record_outcome",
        "description": "Record the outcome of a watch (booked / missed / cancelled / declined). Cancels the watch when booked.",
        "input_schema": _schema(RecordOutcomeInput),
    },
    {
        "name": "replay_fixture",
        "description": "Demo-only. Replays a seeded slot-open event for a restaurant.",
        "input_schema": _schema(ReplayFixtureInput),
    },
]


TOOL_DISPATCH: dict[str, Callable[[dict], dict]] = {
    "search_restaurants": search_restaurants,
    "get_user_prefs": get_user_prefs,
    "list_watches": list_watches,
    "add_watch": add_watch,
    "list_open_slots": list_open_slots,
    "book_slot": book_slot,
    "rag_lookup": rag_lookup,
    "send_notification": send_notification,
    "record_outcome": record_outcome,
    "replay_fixture": replay_fixture,
}


def call_tool(name: str, args: dict) -> dict:
    """Dispatch a tool call by name. Pydantic validation happens inside each fn."""
    if name not in TOOL_DISPATCH:
        return {"error": f"unknown tool: {name}"}
    try:
        return TOOL_DISPATCH[name](args)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
