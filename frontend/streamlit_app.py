"""Tableau — themed Streamlit frontend.

Editorial-grade UI: dark cream + black + gold palette, Cormorant Garamond
serif headings, generous whitespace, restaurant cards with restraint. The user
flow is HOME → CONCIERGE → SETTINGS, with a separate DEMO tab for the
fixture-replay controls during the live class demo.
"""
from __future__ import annotations

import os
import time
from datetime import date, timedelta
from pathlib import Path

import httpx
import streamlit as st

API = os.getenv("API_BASE_URL", "http://localhost:8000")
USER_ID = os.getenv("DEMO_USER_ID", "priya-demo")
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"

st.set_page_config(
    page_title="Tableau — Reservation Concierge",
    page_icon="🍷",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ---------- Theme ----------

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500;600;700&family=Inter:wght@300;400;500;600&display=swap');

/* Hide Streamlit chrome */
header[data-testid="stHeader"] { display: none; }
footer { display: none; }
#MainMenu { display: none; }
button[kind="header"] { display: none; }
[data-testid="collapsedControl"] { display: block; }
.stDeployButton { display: none !important; }

/* Body */
.stApp {
    background: #f5f1e8;
}
[data-testid="stSidebar"] {
    background: #fffdf8;
    border-right: 1px solid #e8e2d4;
}
.main .block-container {
    padding-top: 2rem;
    padding-bottom: 4rem;
    max-width: 1180px;
}

/* Typography */
html, body, [class*="css"], .stMarkdown, p, span, div, label, button, input, textarea {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    color: #1a1a1a;
}
h1, h2, h3, .serif {
    font-family: 'Cormorant Garamond', Georgia, serif !important;
    font-weight: 600 !important;
    letter-spacing: -0.015em !important;
    color: #1a1a1a !important;
}
h1 { font-size: 42px !important; line-height: 1.05 !important; margin-bottom: 4px !important; }
h2 { font-size: 28px !important; line-height: 1.15 !important; margin-bottom: 2px !important; }
h3 { font-size: 20px !important; line-height: 1.2 !important; }

/* Hero */
.hero {
    background: linear-gradient(135deg, #1a1a1a 0%, #2d1810 60%, #3d2415 100%);
    color: #f5f1e8;
    padding: 38px 36px 32px;
    border-radius: 14px;
    margin-bottom: 28px;
    position: relative;
    overflow: hidden;
}
.hero::after {
    content: '';
    position: absolute;
    top: -40%;
    right: -10%;
    width: 480px;
    height: 480px;
    background: radial-gradient(circle, rgba(184,153,104,0.18) 0%, rgba(184,153,104,0) 60%);
    pointer-events: none;
}
.hero-eyebrow {
    text-transform: uppercase;
    letter-spacing: 0.18em;
    font-size: 11px;
    color: #b89968;
    font-weight: 500;
    margin-bottom: 6px;
}
.hero-title {
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 52px;
    line-height: 1;
    font-weight: 600;
    color: #f5f1e8;
    margin: 0 0 8px 0;
    letter-spacing: -0.02em;
}
.hero-tagline {
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 22px;
    font-style: italic;
    line-height: 1.3;
    color: #d4cdb8;
    max-width: 640px;
    margin: 0 0 18px 0;
}
.hero-sub {
    font-size: 14px;
    color: #d4cdb8;
    max-width: 600px;
    line-height: 1.5;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    border-bottom: 1px solid #e8e2d4;
    margin-bottom: 22px;
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    border: none;
    padding: 10px 16px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    letter-spacing: 0.04em;
    color: #6b6453;
    text-transform: uppercase;
}
.stTabs [aria-selected="true"] {
    color: #1a1a1a !important;
    border-bottom: 2px solid #b89968 !important;
}

/* Section heading + subtitle */
.section-head {
    margin: 6px 0 4px 0;
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 32px;
    font-weight: 600;
    color: #1a1a1a;
    letter-spacing: -0.015em;
    line-height: 1;
}
.section-sub {
    font-size: 14px;
    color: #6b6453;
    margin-bottom: 22px;
    line-height: 1.5;
    max-width: 640px;
}
.divider {
    height: 1px;
    background: #e8e2d4;
    margin: 28px 0 20px 0;
}

/* Stat row */
.stat-row { display: flex; gap: 14px; margin-bottom: 24px; }
.stat {
    flex: 1;
    background: #fffdf8;
    border: 1px solid #e8e2d4;
    border-radius: 10px;
    padding: 18px 20px;
}
.stat-label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: #6b6453;
    margin-bottom: 8px;
    font-weight: 500;
}
.stat-value {
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 38px;
    line-height: 1;
    color: #1a1a1a;
    font-weight: 600;
}
.stat-trend {
    font-size: 12px;
    color: #b89968;
    margin-top: 4px;
    font-weight: 500;
}

/* Cards */
.r-card {
    background: #fffdf8;
    border: 1px solid #e8e2d4;
    border-radius: 12px;
    padding: 20px 22px;
    margin-bottom: 14px;
    transition: border-color 0.15s ease;
}
.r-card:hover {
    border-color: #b89968;
}
.r-card-name {
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 26px;
    font-weight: 600;
    color: #1a1a1a;
    margin: 0 0 4px 0;
    line-height: 1.05;
}
.r-card-meta {
    font-size: 13px;
    color: #6b6453;
    margin-bottom: 14px;
    letter-spacing: 0.02em;
}
.r-card-body {
    font-size: 14px;
    line-height: 1.5;
    color: #2d1810;
    margin-bottom: 12px;
}
.r-card-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 12px;
    border-top: 1px solid #efe9d8;
    font-size: 12px;
    color: #6b6453;
}

/* Chips / pills */
.chip {
    display: inline-block;
    padding: 3px 10px;
    background: #f5f1e8;
    border: 1px solid #e8e2d4;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 500;
    color: #2d1810;
    letter-spacing: 0.04em;
    margin-right: 6px;
    margin-bottom: 4px;
}
.chip-gold {
    background: #fdf6e6;
    border-color: #e6cc8a;
    color: #6e5520;
}
.chip-dark {
    background: #1a1a1a;
    border-color: #1a1a1a;
    color: #f5f1e8;
}

/* Difficulty stars */
.stars {
    color: #b89968;
    letter-spacing: 2px;
    font-size: 13px;
}
.stars-empty { color: #d4cdb8; }

/* Empty states */
.empty {
    text-align: center;
    padding: 48px 20px;
    background: #fffdf8;
    border: 1px dashed #d4cdb8;
    border-radius: 12px;
    color: #6b6453;
}
.empty-title {
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 24px;
    color: #2d1810;
    margin-bottom: 6px;
}
.empty-sub {
    font-size: 14px;
    line-height: 1.5;
    max-width: 380px;
    margin: 0 auto;
}

/* Buttons (Streamlit overrides) */
.stButton > button {
    font-family: 'Inter', sans-serif !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    letter-spacing: 0.02em !important;
    border-radius: 8px !important;
    border: 1px solid #e8e2d4 !important;
    padding: 8px 18px !important;
    background: #fffdf8 !important;
    color: #1a1a1a !important;
}
.stButton > button:hover {
    border-color: #b89968 !important;
    color: #1a1a1a !important;
}
.stButton > button[kind="primary"] {
    background: #1a1a1a !important;
    color: #f5f1e8 !important;
    border-color: #1a1a1a !important;
}
.stButton > button[kind="primary"]:hover {
    background: #2d1810 !important;
    color: #f5f1e8 !important;
}

/* Form fields */
.stTextInput input, .stTextArea textarea, .stSelectbox > div > div, .stNumberInput input, .stDateInput input {
    background: #fffdf8 !important;
    border-radius: 8px !important;
    border: 1px solid #e8e2d4 !important;
    font-family: 'Inter', sans-serif !important;
}
.stTextInput input:focus {
    border-color: #b89968 !important;
}

/* Chat */
[data-testid="stChatMessage"] {
    background: transparent !important;
    border: none !important;
    padding: 8px 0 !important;
}
[data-testid="stChatMessageContent"] {
    background: #fffdf8;
    border: 1px solid #e8e2d4;
    border-radius: 10px;
    padding: 12px 14px;
    line-height: 1.5;
}

/* Cost ticker (Demo tab) */
.cost-card {
    background: #1a1a1a;
    color: #f5f1e8;
    border-radius: 12px;
    padding: 18px 22px;
}
.cost-label {
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-size: 11px;
    color: #b89968;
    margin-bottom: 4px;
}
.cost-big {
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 42px;
    line-height: 1;
    color: #f5f1e8;
    font-weight: 600;
}
.cost-detail {
    font-size: 11px;
    color: #d4cdb8;
    margin-top: 8px;
    line-height: 1.5;
}

/* Make full-width primary action buttons */
div.stButton > button.full {
    width: 100%;
}
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
            f"{API}{path}", json=body or {}, params=params, timeout=120
        ).json()
    except Exception as exc:
        return {"error": str(exc)}


def api_put(path: str, body: dict | None = None):
    try:
        return httpx.put(f"{API}{path}", json=body or {}, timeout=15).json()
    except Exception as exc:
        return {"error": str(exc)}


def api_delete(path: str):
    try:
        return httpx.delete(f"{API}{path}", timeout=10).json()
    except Exception as exc:
        return {"error": str(exc)}


# ---------- Session bootstrap ----------

if "prefs" not in st.session_state:
    p = api_get(f"/api/prefs/{USER_ID}")
    if "error" in p:
        st.session_state.prefs = {
            "user_id": USER_ID, "name": "Priya", "email": "",
            "cuisines_loved": ["Italian", "Korean"],
            "neighborhoods": ["West Village", "Flatiron", "NoMad"],
            "default_party_size": 2,
            "skipped_restaurants": [], "booked_restaurants": [],
        }
    else:
        st.session_state.prefs = p

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


# ---------- Hero ----------

prefs = st.session_state.prefs
greeting = "Good evening" if 17 <= int(time.strftime("%H")) else "Good day"

st.markdown(
    f"""<div class='hero'>
<div class='hero-eyebrow'>The Reservation Concierge</div>
<div class='hero-title'>Tableau</div>
<div class='hero-tagline'>{greeting}{', ' + prefs.get('name', '').split()[0] if prefs.get('name') else ''}.</div>
<div class='hero-sub'>We watch the 600 hardest tables in New York and ping you when one fits. You tap once. We confirm.</div>
</div>""",
    unsafe_allow_html=True,
)


# ---------- Tabs ----------

tab_labels = ["Home", "Concierge", "Settings"]
if DEMO_MODE:
    tab_labels.append("Demo Mode")
tabs = st.tabs(tab_labels)


# ============================================================
# HOME — primary user view
# ============================================================
with tabs[0]:
    st.markdown(
        '<div class="section-head">Your tables</div>'
        '<div class="section-sub">Watches we&rsquo;re tracking and recent alerts when slots opened.</div>',
        unsafe_allow_html=True,
    )

    # Stat row
    watches = api_get(f"/api/watches/{USER_ID}").get("watches", []) or []
    notifs = api_get(f"/api/notifications/{USER_ID}").get("notifications", []) or []

    # Active = watches still in active state. Booked = confirmed reservations
    # (notifications that came back with a confirmation_code in the body).
    n_watches = len(watches)
    n_booked = sum(1 for n in notifs if "confirmation" in (n.get("body", "") + n.get("subject", "")).lower())
    n_alerts = len(notifs)

    st.markdown(
        f"""<div class='stat-row'>
  <div class='stat'><div class='stat-label'>Watching now</div><div class='stat-value'>{n_watches}</div><div class='stat-trend'>{'polling every 2 min' if n_watches else 'add one to start'}</div></div>
  <div class='stat'><div class='stat-label'>Tables secured</div><div class='stat-value'>{n_booked}</div><div class='stat-trend'>{'auto-booked on your behalf' if n_booked else 'when a slot matches'}</div></div>
  <div class='stat'><div class='stat-label'>Recent alerts</div><div class='stat-value'>{n_alerts}</div><div class='stat-trend'>across active watches</div></div>
</div>""",
        unsafe_allow_html=True,
    )

    col_left, col_right = st.columns([1.4, 1])

    # ---- Active watches ----
    with col_left:
        st.markdown('<h3>Watching now</h3>', unsafe_allow_html=True)
        if not watches:
            st.markdown(
                """<div class='empty'>
<div class='empty-title'>No active watches</div>
<div class='empty-sub'>Tell the concierge what you want — "Watch Don Angie next Friday for 2" — or use the form below.</div>
</div>""",
                unsafe_allow_html=True,
            )
        else:
            # Build a name lookup so cards show real restaurant names, not IDs.
            for w in watches:
                rid = w.get("restaurant_id", "")
                pretty_name = rid.replace("-", " ").title()
                difficulty = ""  # filled below if available
                date_label = (
                    w["date_window_start"]
                    if w["date_window_start"] == w["date_window_end"]
                    else f"{w['date_window_start']} → {w['date_window_end']}"
                )
                c1, c2 = st.columns([5, 1])
                with c1:
                    st.markdown(
                        f"""<div class='r-card'>
<div class='r-card-name'>{pretty_name}</div>
<div class='r-card-meta'>Party of {w['party_size']} &middot; {date_label} &middot; {w['time_window_start']}&ndash;{w['time_window_end']}</div>
<div class='r-card-footer'>
  <span><span class='chip'>watching</span> <span class='chip chip-gold'>polling /2 min</span></span>
  <span style='color:#6b6453'>since {w['created_at'][:10]}</span>
</div>
</div>""",
                        unsafe_allow_html=True,
                    )
                with c2:
                    if st.button("Cancel", key=f"cancel-{w['id']}"):
                        api_delete(f"/api/watches/{w['id']}")
                        st.rerun()

        # Quick-add expander
        with st.expander("+ Add a watch manually"):
            with st.form("add_watch_form"):
                cols = st.columns([2, 1, 1, 1])
                rid = cols[0].text_input(
                    "Restaurant ID",
                    "don-angie",
                    help="e.g. don-angie, carbone, lilia, atomix",
                )
                psz = cols[1].number_input("Party", 1, 12, 2)
                d_start = cols[2].date_input("From", date.today() + timedelta(days=1))
                d_end = cols[3].date_input("To", date.today() + timedelta(days=14))
                submit = st.form_submit_button("Add watch", type="primary")
                if submit:
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
                        time.sleep(0.4)
                        st.rerun()
                    else:
                        st.error(r)

    # ---- Recent alerts ----
    with col_right:
        st.markdown('<h3>Recent alerts</h3>', unsafe_allow_html=True)
        if not notifs:
            st.markdown(
                """<div class='empty'>
<div class='empty-title'>Nothing yet</div>
<div class='empty-sub'>Alerts land here when a slot opens for one of your watches. Try a Demo Mode replay if you want to see one now.</div>
</div>""",
                unsafe_allow_html=True,
            )
        else:
            for n in notifs[:5]:
                created = n.get("created_at", "")[:16].replace("T", " ")
                subject = n.get("subject", "")
                booked_chip = ""
                if "booked" in subject.lower():
                    booked_chip = "<span class='chip chip-dark'>confirmed</span>"
                email_tag = ""
                if n.get("email_status", "").endswith(":ok"):
                    email_tag = (
                        f"<span class='chip chip-gold'>emailed via "
                        f"{n['email_status'].split(':')[0]}</span>"
                    )
                st.markdown(
                    f"""<div class='r-card'>
<div class='r-card-name' style='font-size:20px'>{subject}</div>
<div class='r-card-meta'>{created}</div>
<div class='r-card-body'>{n.get('body','')}</div>
<div class='r-card-footer'>
  <span>{booked_chip} {email_tag}</span>
  <span></span>
</div>
</div>""",
                    unsafe_allow_html=True,
                )


# ============================================================
# CONCIERGE — chat
# ============================================================
with tabs[1]:
    st.markdown(
        '<div class="section-head">Concierge</div>'
        '<div class="section-sub">Tell the concierge what you want in plain English. It can search restaurants, watch tables, list what it&rsquo;s tracking, and explain why a slot fits.</div>',
        unsafe_allow_html=True,
    )

    if not st.session_state.chat_history:
        st.markdown(
            """<div class='empty' style='text-align:left;padding:24px 28px'>
<div class='empty-title' style='margin-bottom:10px'>Try one of these</div>
<div class='empty-sub' style='margin:0'>
&middot; Watch Don Angie next Friday for 2.<br/>
&middot; What are you watching for me?<br/>
&middot; Find me a Korean tasting menu in NoMad.<br/>
&middot; Anything open at Carbone next weekend?
</div>
</div>""",
            unsafe_allow_html=True,
        )

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    user_msg = st.chat_input("Watch a restaurant, ask a question…")
    if user_msg:
        st.session_state.chat_history.append({"role": "user", "content": user_msg})
        with st.chat_message("user"):
            st.write(user_msg)
        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                resp = api_post(
                    "/api/chat", {"user_id": USER_ID, "message": user_msg}
                )
            reply = resp.get("reply", resp.get("error", "(no reply)"))
            st.write(reply)
        st.session_state.chat_history.append({"role": "assistant", "content": reply})


# ============================================================
# SETTINGS — email + preferences
# ============================================================
with tabs[2]:
    st.markdown(
        '<div class="section-head">Settings</div>'
        '<div class="section-sub">Set your email so we can ping you when a slot opens. Tell us your taste so the ranker knows what to surface.</div>',
        unsafe_allow_html=True,
    )

    p = st.session_state.prefs
    st.markdown('<h3>Notifications</h3>', unsafe_allow_html=True)
    email = st.text_input(
        "Email address",
        p.get("email", ""),
        placeholder="you@example.com",
        help="Required to send alerts. We don't share or sell.",
    )

    cols = st.columns([1, 1, 4])
    with cols[0]:
        save_clicked = st.button("Save email", type="primary", key="save-email")
    with cols[1]:
        test_clicked = st.button("Send test email", key="test-email")

    if save_clicked:
        new_prefs = {**p, "email": email.strip()}
        r = api_put("/api/prefs", new_prefs)
        if r.get("ok"):
            st.session_state.prefs = new_prefs
            st.success("Saved.")
        else:
            st.error(r)

    if test_clicked:
        if not email.strip():
            st.warning("Enter an email first.")
        else:
            with st.spinner("Sending test email…"):
                res = api_post("/api/test-email", {"to": email.strip()})
            if res.get("ok"):
                st.success(
                    f"Sent via **{res.get('provider')}**. "
                    f"Check {email}. (If it's the console fallback, "
                    f"add a RESEND_API_KEY or GMAIL_APP_PASSWORD to .env.)"
                )
            else:
                st.error(
                    f"Send failed via **{res.get('provider')}**: {res.get('detail','')}. "
                    f"See README for setup options."
                )

    st.markdown(
        """<div style='font-size:12px;color:#6b6453;margin-top:6px;line-height:1.5'>
Email setup options:<br/>
&middot; <b>Resend</b> (recommended) — sign up free at resend.com → paste API key into <code>.env</code> as <code>RESEND_API_KEY</code>.<br/>
&middot; <b>Gmail SMTP</b> — generate an App Password at <a href='https://myaccount.google.com/apppasswords' target='_blank'>myaccount.google.com/apppasswords</a> → set <code>GMAIL_USER</code> + <code>GMAIL_APP_PASSWORD</code>.<br/>
&middot; If neither is set, alerts log to console (still in-app, just no email).
</div>""",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<h3>Taste &amp; defaults</h3>', unsafe_allow_html=True)

    name = st.text_input("Name", p.get("name", ""), placeholder="Your name")
    cuisines = st.text_input(
        "Cuisines you love",
        ", ".join(p.get("cuisines_loved", [])),
        placeholder="Italian, Korean, Japanese",
    )
    nbhds = st.text_input(
        "Neighborhoods you frequent",
        ", ".join(p.get("neighborhoods", [])),
        placeholder="West Village, NoMad, Flatiron",
    )
    party = st.number_input(
        "Default party size",
        1, 12, p.get("default_party_size", 2),
    )

    if st.button("Save preferences", type="primary", key="save-prefs"):
        new_prefs = {
            **p,
            "name": name,
            "email": email.strip(),
            "cuisines_loved": [c.strip() for c in cuisines.split(",") if c.strip()],
            "neighborhoods": [n.strip() for n in nbhds.split(",") if n.strip()],
            "default_party_size": int(party),
        }
        r = api_put("/api/prefs", new_prefs)
        if r.get("ok"):
            st.session_state.prefs = new_prefs
            st.success("Preferences saved.")
        else:
            st.error(r)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<h3>How does it actually book?</h3>', unsafe_allow_html=True)
    st.markdown(
        """<div style='font-size:14px;line-height:1.6;color:#2d1810;max-width:680px'>

<b>Today, in this demo:</b> Tableau runs against a <code>MockResyProvider</code> with curated NYC restaurants. No live reservation platform is touched. The agent goes through the full pipeline — find slot, rank fit, book, notify — but the booking only writes to our own database. This keeps us out of any platform's terms of service while we prove out the agent.

<br/><br/>

<b>In production, three real-world paths, in order of credibility:</b>

<br/><br/>
<b>1. B2B partnership (the play).</b> Luxury hotel concierge desks (Aman, 1 Hotels, Faena) pay for a white-labeled API. Hotels already have direct relationships with restaurants — they place the booking on the guest's behalf through channels they're authorized to use. We're the intelligence layer; they're the rails.

<br/><br/>
<b>2. Concierge-in-the-loop.</b> When an alert fires for a paid user, a human concierge at Tableau makes the booking through their own personal Resy account — exactly how high-end concierge services work today. Margin is thinner but no platform fights us.

<br/><br/>
<b>3. Sanctioned API.</b> The architecture has a <code>ReservationProvider</code> interface with a <code>LiveResyProvider</code> stub that's never enabled. The day a partnership exists, we flip the flag. We never reverse-engineer a public API.

<br/><br/>

The HITL gate (you have to opt in to a watch with a date, time, and party size) means we never auto-book anything you didn't ask us to. Consent is given at watch creation, not at the moment of booking.
</div>""",
        unsafe_allow_html=True,
    )


# ============================================================
# DEMO MODE — fixture replay (only when DEMO_MODE)
# ============================================================
if DEMO_MODE:
    with tabs[3]:
        st.markdown(
            '<div class="section-head">Demo Mode</div>'
            '<div class="section-sub">Simulates a slot opening for a curated restaurant. Runs the full Ranker → Auto-Booker → Notifier path: the agent confirms the booking on your behalf and emails you the confirmation. </div>',
            unsafe_allow_html=True,
        )

        st.markdown('<h3>Trigger a slot opening</h3>', unsafe_allow_html=True)
        fixtures = [
            ("fx-don-angie-1", "Don Angie", "Fri 5/8, 7:30pm · two-top"),
            ("fx-carbone-1", "Carbone", "Sat 5/9, 9:45pm · four-top"),
            ("fx-tatiana-1", "Tatiana", "Sun 5/10, 6pm · four-top"),
            ("fx-rezdora-1", "Rezdôra", "Thu 5/7, 8:15pm · bar"),
            ("fx-atomix-1", "Atomix", "Fri 6/12, 6:30pm · counter"),
            ("fx-i-sodi-1", "I Sodi", "Sun 5/11, 7pm · two-top"),
            ("fx-lilia-1", "Lilia", "Tue 5/13, 9pm · two-top"),
            ("fx-frenchette-1", "Frenchette", "Wed 5/14, 8:30pm · main-dining"),
        ]
        cols = st.columns(2)
        for i, (fid, name, desc) in enumerate(fixtures):
            with cols[i % 2]:
                st.markdown(
                    f"""<div class='r-card' style='margin-bottom:8px'>
<div class='r-card-name' style='font-size:22px'>{name}</div>
<div class='r-card-meta'>{desc}</div>
</div>""",
                    unsafe_allow_html=True,
                )
                if st.button(f"▶ Replay slot opening", key=fid, use_container_width=True):
                    with st.spinner(f"Ranker → auto-booker → notifier…"):
                        r = api_post(f"/api/demo/replay/{fid}", {}, user_id=USER_ID)
                    if "sent" in r:
                        sent = r["sent"]
                        booked = r.get("auto_booked", [])
                        if sent and booked:
                            n = sent[0]
                            b = booked[0]
                            st.success(
                                f"**{n['subject']}**\n\n"
                                f"{n['body']}\n\n"
                                f"Confirmation: `{b.get('confirmation_code', '?')}` · "
                                f"Check the **Home** tab to see it land."
                            )
                        elif sent:
                            st.info(f"Notified but not booked: {sent[0]['subject']}")
                        else:
                            st.info("Notifier ran but emitted nothing (check logs).")
                    else:
                        st.error(r)
