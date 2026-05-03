"""Tableau — themed Streamlit frontend.

Single-file Streamlit app that talks to the concierge-api over HTTP. The UI
intentionally looks editorial (serif headings, restaurant photos, restrained
chrome) so the demo doesn't read 'class project'.
"""
from __future__ import annotations

import json
import os
import time
from datetime import date, timedelta
from pathlib import Path

import httpx
import streamlit as st

API = os.getenv("API_BASE_URL", "http://localhost:8000")
USER_ID = os.getenv("DEMO_USER_ID", "priya-demo")

st.set_page_config(
    page_title="Tableau — Reservation Concierge",
    page_icon="🍷",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------- Theme ----------

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, sans-serif;
}

h1, h2, h3, .hero-title {
    font-family: 'Cormorant Garamond', serif;
    font-weight: 600;
    letter-spacing: -0.01em;
}

.hero {
    background: linear-gradient(135deg, #1a1a1a 0%, #2d1810 100%);
    color: #f5f1e8;
    padding: 48px 36px;
    border-radius: 12px;
    margin-bottom: 24px;
}
.hero-title {
    font-size: 42px;
    line-height: 1.05;
    margin: 0 0 12px 0;
}
.hero-sub {
    font-size: 18px;
    color: #d4cdb8;
    max-width: 620px;
}

.pill {
    display: inline-block;
    background: #2d1810;
    color: #f5f1e8;
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 12px;
    margin-right: 6px;
    font-weight: 500;
}
.pill-light {
    background: #f5f1e8;
    color: #2d1810;
    border: 1px solid #d4cdb8;
}
.pill-hot {
    background: #b8472f;
    color: white;
}

.card {
    background: white;
    border: 1px solid #e8e2d4;
    border-radius: 8px;
    padding: 16px 18px;
    margin-bottom: 12px;
}

.card-restaurant {
    font-family: 'Cormorant Garamond', serif;
    font-size: 22px;
    font-weight: 600;
    margin: 0 0 4px 0;
    color: #1a1a1a;
}
.card-meta { color: #6b6453; font-size: 13px; margin-bottom: 10px; }
.card-body { font-size: 14px; color: #2d1810; line-height: 1.5; }

.cost-ticker {
    background: #f5f1e8;
    border: 1px solid #d4cdb8;
    border-radius: 8px;
    padding: 12px;
    font-family: 'Inter', sans-serif;
    font-size: 13px;
}
.cost-big {
    font-family: 'Cormorant Garamond', serif;
    font-size: 28px;
    font-weight: 600;
    color: #2d1810;
}
.muted { color: #6b6453; }

footer { visibility: hidden; }
header { visibility: hidden; }
#MainMenu { visibility: hidden; }
</style>
"""

st.markdown(_CSS, unsafe_allow_html=True)


# ---------- API helpers ----------

def api_get(path: str, **params):
    try:
        return httpx.get(f"{API}{path}", params=params, timeout=15).json()
    except Exception as exc:
        return {"error": str(exc)}


def api_post(path: str, body: dict | None = None, **params):
    try:
        return httpx.post(
            f"{API}{path}", json=body or {}, params=params, timeout=60
        ).json()
    except Exception as exc:
        return {"error": str(exc)}


def api_delete(path: str):
    try:
        return httpx.delete(f"{API}{path}", timeout=10).json()
    except Exception as exc:
        return {"error": str(exc)}


# ---------- Sidebar: persona + cost ticker ----------

with st.sidebar:
    st.markdown("## Persona")
    st.markdown(
        """**Priya Shah, 31**
BD at a VC firm, UES.
Books 6 special-occasion dinners/year.
Spent 4 hrs last month refreshing Resy.
Will pay for guaranteed access."""
    )

    st.markdown("---")
    st.markdown("## Preferences")
    if "prefs_loaded" not in st.session_state:
        prefs = api_get(f"/api/prefs/{USER_ID}")
        if "error" not in prefs:
            st.session_state.prefs = prefs
        else:
            st.session_state.prefs = {
                "user_id": USER_ID,
                "name": "Priya",
                "email": "priya@example.com",
                "cuisines_loved": ["Italian", "Korean"],
                "neighborhoods": ["West Village", "Flatiron", "NoMad"],
                "default_party_size": 2,
                "skipped_restaurants": ["rezdora"],
                "booked_restaurants": [],
            }
        st.session_state.prefs_loaded = True

    prefs = st.session_state.prefs
    cuisines = st.text_input(
        "Cuisines loved", ", ".join(prefs.get("cuisines_loved", []))
    )
    nbhds = st.text_input(
        "Neighborhoods", ", ".join(prefs.get("neighborhoods", []))
    )
    party = st.number_input(
        "Default party size", 1, 12, prefs.get("default_party_size", 2)
    )
    if st.button("Save preferences"):
        api_post(
            "/api/prefs",
            {},  # no body — using PUT semantics via POST below
        )
        # Fall back: use a direct PUT.
        try:
            httpx.put(
                f"{API}/api/prefs",
                json={
                    "user_id": USER_ID,
                    "name": prefs.get("name", "Priya"),
                    "email": prefs.get("email", ""),
                    "cuisines_loved": [c.strip() for c in cuisines.split(",") if c.strip()],
                    "neighborhoods": [n.strip() for n in nbhds.split(",") if n.strip()],
                    "default_party_size": int(party),
                },
                timeout=10,
            )
            st.success("Saved.")
            st.session_state.prefs_loaded = False
        except Exception as exc:
            st.error(f"Save failed: {exc}")

    st.markdown("---")
    st.markdown("## Live unit economics")
    cost = api_get("/api/cost")
    if "error" not in cost:
        st.markdown(
            f"<div class='cost-ticker'>"
            f"<div>Session spend</div>"
            f"<div class='cost-big'>${cost.get('total_usd', 0.0):.4f}</div>"
            f"<div class='muted'>Calls: {cost.get('call_count', 0)}</div>"
            f"<div style='margin-top:8px' class='muted'>"
            f"Plan: <b>$19/mo</b> &nbsp;·&nbsp; Target COGS: <b>$2.46</b><br/>"
            f"Margin at price: <b>~87%</b>"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.caption("Demo runs against MockResyProvider. No live booking platform is touched.")


# ---------- Hero ----------

st.markdown(
    """<div class='hero'>
<div class='hero-title'>Tableau</div>
<div class='hero-sub'>The Bloomberg Terminal for the 600 restaurants where access <i>is</i> the product. We watch hard-to-book NYC tables for you and tell you the moment a slot fits.</div>
</div>""",
    unsafe_allow_html=True,
)


# ---------- Tabs ----------

tab_chat, tab_watches, tab_notifs, tab_demo, tab_about = st.tabs(
    ["💬 Concierge", "👁  Watches", "🔔 Notifications", "🎬 Demo", "ℹ️  About"]
)


# ============ Concierge Tab ============
with tab_chat:
    st.markdown("### Talk to the concierge")
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            {
                "role": "assistant",
                "content": "Tell me a restaurant + a party size + a date window, and I'll start watching. Or describe a vibe and I'll find candidates.",
            }
        ]

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    user_msg = st.chat_input("e.g. Watch Don Angie next Friday for 2.")
    if user_msg:
        st.session_state.chat_history.append({"role": "user", "content": user_msg})
        with st.chat_message("user"):
            st.write(user_msg)
        with st.chat_message("assistant"):
            with st.spinner("Concierge thinking…"):
                resp = api_post(
                    "/api/chat", {"user_id": USER_ID, "message": user_msg}
                )
            reply = resp.get("reply", resp.get("error", "(no reply)"))
            st.write(reply)
        st.session_state.chat_history.append({"role": "assistant", "content": reply})


# ============ Watches Tab ============
with tab_watches:
    st.markdown("### Active watches")
    watches = api_get(f"/api/watches/{USER_ID}").get("watches", [])
    if not watches:
        st.info("No active watches yet. Add one below or chat with the concierge.")
    for w in watches:
        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            st.markdown(
                f"<div class='card'>"
                f"<div class='card-restaurant'>{w['restaurant_id']}</div>"
                f"<div class='card-meta'>Party of {w['party_size']} · "
                f"{w['date_window_start']} → {w['date_window_end']} · "
                f"{w['time_window_start']}–{w['time_window_end']}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with col3:
            if st.button("Cancel", key=f"cancel-{w['id']}"):
                api_delete(f"/api/watches/{w['id']}")
                st.rerun()

    st.markdown("---")
    st.markdown("### Add a watch manually")
    with st.form("add_watch_form"):
        cols = st.columns([2, 1, 1, 1])
        rid = cols[0].text_input("Restaurant ID", "don-angie")
        psz = cols[1].number_input("Party size", 1, 12, 2)
        d_start = cols[2].date_input("Start date", date.today() + timedelta(days=1))
        d_end = cols[3].date_input("End date", date.today() + timedelta(days=14))
        if st.form_submit_button("Add watch"):
            r = api_post(
                "/api/watches",
                {
                    "user_id": USER_ID,
                    "restaurant_id": rid,
                    "party_size": int(psz),
                    "date_window_start": d_start.isoformat(),
                    "date_window_end": d_end.isoformat(),
                },
            )
            if r.get("ok"):
                st.success(f"Added: {r.get('summary', '')}")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error(r)


# ============ Notifications Tab ============
with tab_notifs:
    st.markdown("### Recent notifications")
    notifs = api_get(f"/api/notifications/{USER_ID}").get("notifications", [])
    if not notifs:
        st.caption("No notifications yet. Trigger one from the Demo tab.")
    for n in notifs:
        col_a, col_b = st.columns([4, 1])
        with col_a:
            st.markdown(
                f"<div class='card'>"
                f"<div class='card-restaurant'>{n.get('subject', '')}</div>"
                f"<div class='card-meta'>{n.get('created_at', '')[:19].replace('T', ' ')}</div>"
                f"<div class='card-body'>{n.get('body', '')}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with col_b:
            if n.get("slot_id"):
                if st.button("Book it", key=f"book-{n['id']}"):
                    # Two-step HITL: prepare token, then call /api/chat with token.
                    prep = api_post(
                        "/api/book/prepare",
                        {"user_id": USER_ID, "slot_id": n["slot_id"]},
                    )
                    token = prep.get("confirmation_token")
                    if not token:
                        st.error("Could not mint token.")
                    else:
                        result = api_post(
                            "/api/chat",
                            {
                                "user_id": USER_ID,
                                "message": "Confirm booking.",
                                "confirmation_token": token,
                                "booking_slot_id": n["slot_id"],
                            },
                        )
                        st.success(result.get("reply", "Booked."))


# ============ Demo Tab ============
with tab_demo:
    st.markdown("### Trigger a fixture replay")
    st.caption(
        "Demo controls only. Each fixture simulates a 'slot just opened' event "
        "for a curated restaurant + time. Hits the Ranker → Notifier path."
    )
    fixtures = [
        ("fx-don-angie-1", "Don Angie · Fri 5/8 7:30pm · two-top"),
        ("fx-carbone-1", "Carbone · Sat 5/9 9:45pm · four-top"),
        ("fx-tatiana-1", "Tatiana · Sun 5/10 6pm · four-top"),
        ("fx-rezdora-1", "Rezdôra · Thu 5/7 8:15pm · bar"),
        ("fx-atomix-1", "Atomix · Fri 6/12 6:30pm · counter"),
        ("fx-i-sodi-1", "I Sodi · Sun 5/11 7pm · two-top"),
        ("fx-lilia-1", "Lilia · Tue 5/13 9pm · two-top"),
        ("fx-frenchette-1", "Frenchette · Wed 5/14 8:30pm · main-dining"),
    ]
    cols = st.columns(2)
    for i, (fid, label) in enumerate(fixtures):
        if cols[i % 2].button(f"▶ {label}", key=fid, use_container_width=True):
            with st.spinner(f"Replaying {fid}…"):
                r = api_post(f"/api/demo/replay/{fid}", {}, user_id=USER_ID)
            if "sent" in r:
                st.success(f"Sent {len(r['sent'])} notification(s). Check the Notifications tab.")
            else:
                st.error(r)


# ============ About Tab ============
with tab_about:
    st.markdown("### Agent architecture")
    st.markdown(
        "Five LangGraph nodes — Supervisor, Scout, Ranker, Notifier, Booker — "
        "split across two graphs (chat + tick). The Scout polls availability "
        "and hash-diffs against a snapshot — 95%+ of ticks short-circuit "
        "before any LLM call, which is the lever that keeps unit economics at ~$2.46/user/mo."
    )
    arch_path = Path(__file__).resolve().parent.parent / "docs" / "chat_graph.png"
    if arch_path.exists():
        st.image(str(arch_path), caption="chat_graph", use_container_width=True)
    arch_path2 = arch_path.with_name("tick_graph.png")
    if arch_path2.exists():
        st.image(str(arch_path2), caption="tick_graph", use_container_width=True)

    st.markdown("### Class concepts")
    st.markdown("""
- **Tool calling** — `backend/tools/reservation_tools.py`
- **Multi-agent / orchestration** — `backend/agents/graph.py`
- **RAG / vector search** — `backend/rag/retriever.py`
- **Memory / state** — `backend/memory/state.py`
- **Evaluation** — `backend/evals/run_evals.py`
- **Context engineering** — `backend/agents/prompts.py`
- **Constrained decoding** (bonus) — Pydantic-validated tool inputs
""")
    st.markdown("### Where it breaks (named honestly)")
    st.markdown("""
1. Resy / OpenTable C&D — mitigated by mock-only demo + B2B partnership pivot.
2. Polling cadence: sub-30s would 4× costs and shrink margin to ~60%.
3. Cold-start: no users → no signal. Launch-with-concierge-partnership fixes it.
4. Anthropic price moves: 3× Sonnet bump → margin to ~50%.
""")
