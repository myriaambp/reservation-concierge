"""Ranker — given a pending slot + user prefs + RAG context, write the 'why'.

Class concepts: RAG (rag_lookup), context engineering (RANKER_PROMPT),
constrained decoding (Pydantic-validated tool inputs upstream).
"""
from __future__ import annotations

from backend.agents.prompts import RANKER_PROMPT
from backend.config import get_settings
from backend.llm.client import chat
from backend.memory.firestore_store import get_store
from backend.memory.state import AgentState
from backend.providers.base import get_provider
from backend.tools.reservation_tools import call_tool


def ranker_node(state: AgentState) -> dict:
    """For each pending slot, retrieve restaurant context and write a 'why' note."""
    settings = get_settings()
    pending = state.get("pending_slots", [])
    if not pending:
        return {"pending_slots": []}

    provider = get_provider()
    store = get_store()
    enriched: list[dict] = []

    for slot in pending:
        rest = provider.get_restaurant(slot["restaurant_id"])
        if rest is None:
            continue
        prefs = store.get_user(slot["user_id"])

        # RAG: pull editorial context (always returns the seeded restaurant doc).
        rag = call_tool(
            "rag_lookup",
            {
                "query": f"{rest.name} {rest.cuisine} {rest.neighborhood} vibe",
                "k": 3,
            },
        )
        rag_text = "\n".join(d.get("text", "") for d in rag.get("docs", [])[:3])

        user_msg = (
            f"Slot: {rest.name} on {slot['datetime']} for "
            f"{slot['party_size']} ({slot['table_type']}).\n"
            f"User prefs: cuisines_loved={prefs.cuisines_loved}, "
            f"neighborhoods={prefs.neighborhoods}, "
            f"skipped={prefs.skipped_restaurants[-3:]}.\n"
            f"Restaurant context:\n{rag_text}"
        )
        resp = chat(
            model=settings.worker_model,
            system=RANKER_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
            max_tokens=400,
            agent_name="ranker",
            temperature=0.3,
            disable_thinking=True,  # 2-sentence formatter, no need to think
        )
        rationale = resp.text

        enriched.append(
            {
                **slot,
                "score": _score(prefs, rest),
                "rationale": rationale,
                "restaurant_name": rest.name,
            }
        )

    enriched.sort(key=lambda s: s["score"], reverse=True)
    return {"pending_slots": enriched}


def _score(prefs, restaurant) -> float:
    """Cheap, explainable score: cuisine match + neighborhood match + difficulty bonus."""
    score = 0.0
    if any(c.lower() in restaurant.cuisine.lower() for c in prefs.cuisines_loved):
        score += 0.5
    if any(n.lower() in restaurant.neighborhood.lower() for n in prefs.neighborhoods):
        score += 0.2
    if restaurant.id in prefs.booked_restaurants:
        score -= 0.4  # avoid spamming places they already went
    if restaurant.id in prefs.skipped_restaurants:
        score -= 0.6
    score += (restaurant.difficulty - 3) * 0.05  # bias toward truly hard
    return score
