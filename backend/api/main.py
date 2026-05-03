"""FastAPI app — exposes chat, watch CRUD, /internal/tick, HITL booking,
and demo controls. Runs on Cloud Run as `concierge-api`.
"""
from __future__ import annotations

# Load .env into os.environ before any other imports that might read env vars.
from dotenv import load_dotenv  # noqa: E402
load_dotenv()  # noqa: E402

import secrets
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.agents.graph import chat_graph, tick_graph
from backend.config import get_settings
from backend.llm.client import get_ledger
from backend.memory.firestore_store import get_store
from backend.memory.state import UserPrefs
from backend.tools.reservation_tools import call_tool

app = FastAPI(title="Tableau API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in prod
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# In-memory token store for HITL booking flow. Production: redis or short-TTL
# Firestore docs.
_BOOKING_TOKENS: dict[str, dict] = {}


# ---------- request models ----------

class ChatRequest(BaseModel):
    user_id: str = "demo-user"
    message: str
    confirmation_token: str | None = None
    booking_slot_id: str | None = None
    booking_watch_id: str | None = None


class WatchCreateRequest(BaseModel):
    user_id: str = "demo-user"
    restaurant_id: str
    party_size: int = 2
    date_window_start: str
    date_window_end: str
    time_window_start: str = "17:30"
    time_window_end: str = "22:00"


class PrefsRequest(BaseModel):
    user_id: str
    name: str = "Guest"
    email: str = ""
    cuisines_loved: list[str] = []
    cuisines_avoided: list[str] = []
    neighborhoods: list[str] = []
    default_party_size: int = 2
    dietary: list[str] = []


class BookConfirmRequest(BaseModel):
    user_id: str
    slot_id: str
    watch_id: str | None = None


# ---------- health + cost ----------

@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "concierge-api"}


class TestEmailRequest(BaseModel):
    to: str


@app.post("/api/test-email")
def test_email(req: TestEmailRequest) -> dict:
    """Send a one-shot test email so users can verify their setup."""
    from backend.notifications.email import send_email
    result = send_email(
        req.to,
        "Tableau setup confirmed",
        (
            "Your concierge is wired up. From now on, when a slot opens for one "
            "of your watched restaurants, this is where it'll land. "
            "(That's the whole pitch.)"
        ),
    )
    return {
        "ok": result.ok,
        "provider": result.provider,
        "detail": result.detail,
    }


@app.get("/api/cost")
def cost() -> dict:
    led = get_ledger()
    return {
        "total_usd": round(led.total_usd, 4),
        "by_model": {k: round(v, 4) for k, v in led.by_model.items()},
        "by_agent": {k: round(v, 4) for k, v in led.by_agent.items()},
        "call_count": led.call_count,
    }


# ---------- chat ----------

@app.post("/api/chat")
def chat(req: ChatRequest) -> dict:
    state: dict[str, Any] = {
        "user_id": req.user_id,
        "messages": [{"role": "user", "content": req.message}],
        "scratchpad": {},
    }
    # If this chat is the second leg of an HITL booking confirmation, the
    # frontend supplies confirmation_token + slot_id, which routes via Booker.
    if req.confirmation_token:
        token_rec = _BOOKING_TOKENS.get(req.confirmation_token)
        if not token_rec or token_rec["user_id"] != req.user_id:
            raise HTTPException(403, "invalid confirmation token")
        state["scratchpad"] = {
            "confirmation_token": req.confirmation_token,
            "booking_slot_id": req.booking_slot_id or token_rec["slot_id"],
            "booking_watch_id": req.booking_watch_id or token_rec.get("watch_id"),
        }
        # Burn the token after use.
        _BOOKING_TOKENS.pop(req.confirmation_token, None)

    result = chat_graph.invoke(state)

    def _serialize(m: Any) -> dict:
        if isinstance(m, dict):
            return {"role": m.get("role", ""), "content": m.get("content", "")}
        # LangChain message object (HumanMessage / AIMessage / etc.)
        msg_type = getattr(m, "type", "ai")
        role = "user" if msg_type == "human" else "assistant"
        return {"role": role, "content": getattr(m, "content", "")}

    return {
        "reply": result.get("final_response", ""),
        "messages": [_serialize(m) for m in result.get("messages", [])],
    }


# ---------- preferences ----------

@app.get("/api/prefs/{user_id}")
def get_prefs(user_id: str) -> dict:
    return get_store().get_user(user_id).model_dump()


@app.put("/api/prefs")
def upsert_prefs(req: PrefsRequest) -> dict:
    prefs = UserPrefs(**req.model_dump())
    get_store().upsert_user(prefs)
    return {"ok": True}


# ---------- watches ----------

@app.get("/api/watches/{user_id}")
def list_watches(user_id: str) -> dict:
    watches = get_store().list_watches(user_id=user_id, active_only=True)
    return {"watches": [w.model_dump() for w in watches]}


@app.post("/api/watches")
def add_watch(req: WatchCreateRequest) -> dict:
    return call_tool("add_watch", req.model_dump())


@app.delete("/api/watches/{watch_id}")
def cancel_watch(watch_id: str) -> dict:
    get_store().cancel_watch(watch_id)
    return {"ok": True}


# ---------- HITL booking ----------

@app.post("/api/book/prepare")
def book_prepare(req: BookConfirmRequest) -> dict:
    """Mint a one-shot confirmation token. Frontend then sends it to /api/chat
    along with the user's confirm message; Booker is invoked with the token in
    scratchpad. Tokens expire on use; never reused.
    """
    token = secrets.token_urlsafe(16)
    _BOOKING_TOKENS[token] = {
        "user_id": req.user_id,
        "slot_id": req.slot_id,
        "watch_id": req.watch_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return {"confirmation_token": token}


# ---------- notifications ----------

@app.get("/api/notifications/{user_id}")
def list_notifications(user_id: str, limit: int = 20) -> dict:
    return {"notifications": get_store().recent_notifications(user_id, limit)}


# ---------- demo controls ----------

@app.post("/api/demo/replay/{fixture_id}")
def demo_replay(fixture_id: str, user_id: str = "demo-user") -> dict:
    """Trigger a synthetic 'slot opened' event for the live demo.

    Pipeline: Ranker (RAG-enriched rationale) → Auto-booker (confirms the
    booking, since consent was given at watch creation) → Notifier (writes
    the 'Booked: …' card and emails the user).
    """
    from datetime import datetime as _dt, timezone as _tz
    import uuid as _uuid
    from backend.agents.auto_booker import auto_booker_node
    from backend.agents.notifier import notifier_node
    from backend.agents.ranker import ranker_node
    from backend.memory.state import Watch
    from backend.providers.base import get_provider

    provider = get_provider()
    slot = provider.replay_fixture(fixture_id)

    # Ensure a synthetic auto_book watch exists so the auto-booker accepts it.
    store = get_store()
    demo_watch_id = f"wch-demo-{fixture_id}"
    if not any(w.id == demo_watch_id for w in store.list_watches(user_id=user_id, active_only=True)):
        store.add_watch(
            Watch(
                id=demo_watch_id,
                user_id=user_id,
                restaurant_id=slot.restaurant_id,
                party_size=slot.party_size,
                date_window_start=slot.datetime.date().isoformat(),
                date_window_end=slot.datetime.date().isoformat(),
                time_window_start="00:00",
                time_window_end="23:59",
                created_at=_dt.now(_tz.utc).isoformat(),
                active=True,
                auto_book=True,
            )
        )

    state = {
        "user_id": user_id,
        "pending_slots": [
            {
                "watch_id": demo_watch_id,
                "user_id": user_id,
                "slot_id": slot.id,
                "restaurant_id": slot.restaurant_id,
                "datetime": slot.datetime.isoformat(),
                "party_size": slot.party_size,
                "table_type": slot.table_type,
            }
        ],
    }

    # Run the post-scout chain: rank → generate-deep-link → notify.
    state.update(ranker_node(state))
    state.update(auto_booker_node(state))
    notif = notifier_node(state)
    return {
        "sent": notif.get("scratchpad", {}).get("notifications_sent", []),
        "pending_user_confirm": [
            {
                "restaurant_id": s.get("restaurant_id"),
                "restaurant_name": s.get("restaurant_name"),
                "datetime": s.get("datetime"),
                "party_size": s.get("party_size"),
                "table_type": s.get("table_type"),
                "booking_url": s.get("booking_url"),
                "booking_platform": s.get("booking_platform"),
                "booking_note": s.get("booking_note"),
            }
            for s in state.get("pending_slots", []) if s.get("pending_user_confirm")
        ],
    }


# ---------- cron-triggered tick ----------

@app.post("/internal/tick")
def tick(x_tick_token: str | None = Header(default=None)) -> dict:
    """Cron-triggered scout pass. Cloud Scheduler hits this every 2 minutes."""
    settings = get_settings()
    if x_tick_token != settings.internal_tick_token:
        raise HTTPException(401, "invalid tick token")

    # Run the tick graph for each user with active watches.
    store = get_store()
    user_ids = {w.user_id for w in store.list_watches(active_only=True)}
    if not user_ids:
        return {"status": "no active watches"}

    summary = []
    for uid in user_ids:
        result = tick_graph.invoke({"user_id": uid, "scratchpad": {}})
        notifs = result.get("scratchpad", {}).get("notifications_sent", [])
        summary.append({"user_id": uid, "notifications_sent": len(notifs)})

    return {"status": "ok", "results": summary}
