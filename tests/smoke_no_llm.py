"""No-LLM smoke test: provider, ingest, retriever, store. Run from repo root:
    python -m tests.smoke_no_llm
Should print '✓' for each section and exit 0.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone


def main() -> int:
    print("→ provider")
    from backend.providers.base import get_provider
    p = get_provider()
    rs = p.list_restaurants()
    assert len(rs) >= 25, f"expected ≥25 restaurants, got {len(rs)}"
    print(f"  ✓ {len(rs)} restaurants loaded ({rs[0].name}, ...)")

    rest = p.get_restaurant("don-angie")
    assert rest is not None and rest.name == "Don Angie"
    print(f"  ✓ get_restaurant works ({rest.name})")

    start = datetime.now(timezone.utc)
    end = start + timedelta(days=14)
    slots = p.list_open_slots("don-angie", start, end, 2)
    print(f"  ✓ list_open_slots → {len(slots)} slots over 14 days")

    fx = p.replay_fixture("fx-don-angie-1")
    assert fx.restaurant_id == "don-angie"
    print(f"  ✓ replay_fixture works ({fx.id} for {fx.restaurant_id})")

    print("→ ingest + retriever (lexical mode)")
    from backend.rag.ingest import ingest
    ingest()
    from backend.rag.retriever import retrieve
    docs = retrieve("romantic Italian West Village", k=5)
    assert len(docs) == 5
    print(f"  ✓ retrieve top-5 → first: {docs[0]['meta']['name']} (score {docs[0]['score']:.3f})")

    print("→ memory store (local file mode)")
    from backend.memory.firestore_store import get_store
    from backend.memory.state import UserPrefs, Watch
    store = get_store()
    store.upsert_user(UserPrefs(user_id="smoke-user", name="Smoke", cuisines_loved=["Italian"]))
    got = store.get_user("smoke-user")
    assert got.name == "Smoke" and "Italian" in got.cuisines_loved
    print("  ✓ user upsert + get")

    w = Watch(
        id="wch-test",
        user_id="smoke-user",
        restaurant_id="don-angie",
        party_size=2,
        date_window_start="2026-05-08",
        date_window_end="2026-05-15",
        time_window_start="17:30",
        time_window_end="22:00",
        created_at=datetime.now(timezone.utc).isoformat(),
        active=True,
    )
    store.add_watch(w)
    watches = store.list_watches(user_id="smoke-user")
    assert any(x.id == "wch-test" for x in watches)
    print(f"  ✓ watch add + list ({len(watches)} active)")

    store.cancel_watch("wch-test")
    watches = store.list_watches(user_id="smoke-user")
    assert not any(x.id == "wch-test" for x in watches)
    print("  ✓ watch cancel")

    print("→ tools (no LLM)")
    from backend.tools.reservation_tools import call_tool
    r = call_tool("search_restaurants", {"query": "Italian", "neighborhood": "West Village"})
    assert "results" in r and r["count"] > 0
    print(f"  ✓ search_restaurants → {r['count']} hits")

    r = call_tool(
        "add_watch",
        {
            "user_id": "smoke-user",
            "restaurant_id": "lilia",
            "party_size": 2,
            "date_window_start": "2026-05-12",
            "date_window_end": "2026-05-19",
        },
    )
    assert r.get("ok") is True
    print(f"  ✓ add_watch via tool dispatch ({r['watch_id']})")

    print("\n✅ No-LLM smoke passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
