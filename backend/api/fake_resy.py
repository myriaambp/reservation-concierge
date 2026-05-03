"""Fake Resy — a Tableau-controlled reservation site the agent books against
during demos. Visually echoes real Resy/OpenTable so the demo feels real;
architecturally it lives behind the same `ReservationProvider` interface
as the production stub. The day a partnership exists we point at their
domain; the agent code doesn't change.

Routes:
  GET  /fake-resy/{slug}?date=YYYY-MM-DD&seats=N
       Restaurant page with clickable time slots.
  GET  /fake-resy/{slug}/book?date=...&seats=N&time=HH:MM
       Booking form (name + email) for a specific time.
  POST /fake-resy/{slug}/book
       Submits the booking, redirects to confirmation page.
  GET  /fake-resy/confirmation/{code}
       Confirmation page with reservation details.
"""
from __future__ import annotations

import json
import secrets
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse


router = APIRouter(prefix="/fake-resy", tags=["fake-resy"])


_REPO_ROOT = Path(__file__).resolve().parents[2]
_RESTAURANTS_PATH = _REPO_ROOT / "seed_data" / "restaurants.json"

_BOOKINGS: dict[str, dict] = {}  # in-memory: code -> booking record


def _load_restaurants() -> dict[str, dict]:
    with _RESTAURANTS_PATH.open() as f:
        return {r["id"]: r for r in json.load(f)}


def _times_for(slug: str, on_date: date, party: int) -> list[str]:
    """Deterministic available-time list per (slug, date, party). Mirrors the
    feel of MockResyProvider — high-difficulty restaurants surface fewer slots."""
    import hashlib
    import random

    rs = _load_restaurants().get(slug, {})
    difficulty = int(rs.get("difficulty", 3))
    candidates = ["17:30", "18:00", "18:30", "19:00", "19:30",
                  "20:00", "20:30", "21:00", "21:30", "22:00"]
    seed = int(hashlib.md5(f"{slug}|{on_date}|{party}".encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    keep_prob = max(0.15, 0.55 - (difficulty - 1) * 0.07)
    return [t for t in candidates if rng.random() < keep_prob]


# ---------- HTML ----------

_BASE_CSS = """
  * { box-sizing: border-box; }
  body { margin:0; font-family:-apple-system,'Inter','Helvetica Neue',sans-serif; background:#fafaf7; color:#111; }
  a { color:#111; }
  .wrap { max-width:880px; margin:0 auto; padding:32px 28px 48px; }
  .brand { font-size:13px; letter-spacing:0.18em; text-transform:uppercase; color:#888; margin-bottom:24px; }
  .brand b { color:#111; }
  h1 { font-family:'Cormorant Garamond',Georgia,serif; font-size:44px; line-height:1; margin:0 0 6px; letter-spacing:-0.015em; }
  .meta { color:#666; font-size:14px; margin-bottom:28px; }
  .pill { display:inline-block; padding:3px 10px; background:#fff; border:1px solid #e5e5e0; border-radius:999px; font-size:12px; color:#444; margin-right:6px; }
  .when { background:#fff; border:1px solid #e5e5e0; border-radius:10px; padding:18px 22px; margin:18px 0; }
  .when-label { font-size:12px; color:#888; letter-spacing:0.1em; text-transform:uppercase; margin-bottom:8px; }
  .when-value { font-size:18px; font-weight:600; }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(110px,1fr)); gap:8px; margin-top:20px; }
  .slot { background:#fff; border:1px solid #d6d4cc; padding:14px 0; border-radius:8px; text-align:center; font-size:14px; font-weight:500; cursor:pointer; transition:all .15s; text-decoration:none; color:#111; display:block; }
  .slot:hover { border-color:#111; background:#111; color:#fff; }
  .empty { background:#fff; border:1px dashed #d6d4cc; padding:32px; border-radius:10px; text-align:center; color:#888; }
  form { background:#fff; border:1px solid #e5e5e0; border-radius:10px; padding:22px 26px; max-width:480px; }
  label { display:block; font-size:12px; color:#666; letter-spacing:0.06em; text-transform:uppercase; margin:14px 0 6px; }
  input { width:100%; padding:11px 12px; font-size:15px; border:1px solid #d6d4cc; border-radius:6px; font-family:inherit; }
  input:focus { outline:none; border-color:#111; }
  button.primary { margin-top:20px; background:#111; color:#fff; border:none; padding:13px 30px; border-radius:6px; font-size:14px; font-weight:600; letter-spacing:0.02em; cursor:pointer; }
  button.primary:hover { background:#000; }
  .confirm-card { background:#fff; border:1px solid #e5e5e0; border-radius:12px; padding:32px 36px; margin-top:24px; }
  .check { width:54px; height:54px; border-radius:50%; background:#0d8f43; color:#fff; font-size:30px; display:flex; align-items:center; justify-content:center; margin-bottom:18px; }
  .row { display:flex; padding:8px 0; border-bottom:1px solid #f0eee8; font-size:14px; }
  .row:last-child { border:none; }
  .row .k { width:140px; color:#888; }
  .row .v { font-weight:500; }
  .code { font-family:'SF Mono',Menlo,monospace; }
  .footer { margin-top:36px; font-size:12px; color:#888; line-height:1.5; }
"""


def _layout(title: str, body_html: str) -> str:
    return f"""<!doctype html>
<html><head><meta charset='utf-8'>
<title>{title} · TableTime</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600&family=Inter:wght@400;500;600&display=swap" rel="stylesheet"/>
<style>{_BASE_CSS}</style></head>
<body><div class='wrap'>
<div class='brand'><b>TableTime</b></div>
{body_html}
<div class='footer'>TableTime · sandbox booking domain · powered by Tableau</div>
</div></body></html>"""


# ---------- Routes ----------

@router.get("/{slug}", response_class=HTMLResponse)
def restaurant_page(
    slug: str,
    date: Annotated[str | None, Query()] = None,
    seats: Annotated[int, Query(ge=1, le=12)] = 2,
) -> HTMLResponse:
    rs = _load_restaurants().get(slug)
    if rs is None:
        raise HTTPException(404, f"unknown restaurant: {slug}")

    on_date = (
        datetime.fromisoformat(date).date()
        if date else (datetime.now(timezone.utc).date() + timedelta(days=5))
    )
    times = _times_for(slug, on_date, seats)
    pretty_date = on_date.strftime("%A, %B %-d, %Y")

    if not times:
        slots_html = "<div class='empty'>No openings for this date and party. Try another day.</div>"
    else:
        slots_html = "<div class='grid'>" + "".join(
            f"<a class='slot' href='/fake-resy/{slug}/book?date={on_date.isoformat()}&seats={seats}&time={t}' data-test='time-slot' data-time='{t}'>{_fmt_time(t)}</a>"
            for t in times
        ) + "</div>"

    body = f"""
<h1>{rs['name']}</h1>
<div class='meta'>{rs['cuisine']} · {rs['neighborhood']}, {rs['borough']} · price {'$' * rs['price_tier']}</div>
<div class='pill'>Dress: {rs.get('dress_code','smart casual')}</div>
<div class='pill'>Difficulty: {rs.get('difficulty', 3)}/5</div>

<div class='when'>
  <div class='when-label'>Looking for</div>
  <div class='when-value'>{pretty_date} &middot; party of {seats}</div>
</div>

<h3 style='font-family:Cormorant Garamond,Georgia,serif;font-weight:600'>Available times</h3>
{slots_html}
"""
    return HTMLResponse(_layout(rs["name"], body))


@router.get("/{slug}/book", response_class=HTMLResponse)
def book_form(
    slug: str,
    date: Annotated[str, Query()],
    seats: Annotated[int, Query(ge=1, le=12)],
    time: Annotated[str, Query()],
) -> HTMLResponse:
    rs = _load_restaurants().get(slug)
    if rs is None:
        raise HTTPException(404, f"unknown restaurant: {slug}")
    on_date = datetime.fromisoformat(date).date()
    pretty_date = on_date.strftime("%A, %B %-d, %Y")

    body = f"""
<h1>Reserve at {rs['name']}</h1>
<div class='meta'>{pretty_date} &middot; {_fmt_time(time)} &middot; party of {seats}</div>

<form method='post' action='/fake-resy/{slug}/book'>
  <input type='hidden' name='slug' value='{slug}'/>
  <input type='hidden' name='date' value='{date}'/>
  <input type='hidden' name='seats' value='{seats}'/>
  <input type='hidden' name='time' value='{time}'/>

  <label for='name'>Name on reservation</label>
  <input id='name' name='name' required placeholder='First Last' data-test='name-input'/>

  <label for='email'>Email</label>
  <input id='email' name='email' type='email' required placeholder='you@example.com' data-test='email-input'/>

  <button class='primary' type='submit' data-test='submit-booking'>Reserve</button>
</form>
"""
    return HTMLResponse(_layout(f"Reserve at {rs['name']}", body))


@router.post("/{slug}/book")
def submit_booking(
    slug: str,
    date: Annotated[str, Form()],
    seats: Annotated[int, Form()],
    time: Annotated[str, Form()],
    name: Annotated[str, Form()],
    email: Annotated[str, Form()],
):
    rs = _load_restaurants().get(slug)
    if rs is None:
        raise HTTPException(404, f"unknown restaurant: {slug}")

    code = f"TBL-{secrets.token_hex(3).upper()}"
    _BOOKINGS[code] = {
        "code": code,
        "slug": slug,
        "name_on_reservation": name,
        "email": email,
        "date": date,
        "time": time,
        "party_size": seats,
        "restaurant_name": rs["name"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return RedirectResponse(
        url=f"/fake-resy/confirmation/{code}", status_code=303
    )


@router.get("/confirmation/{code}", response_class=HTMLResponse)
def confirmation(code: str) -> HTMLResponse:
    booking = _BOOKINGS.get(code)
    if booking is None:
        raise HTTPException(404, "confirmation not found")
    on_date = datetime.fromisoformat(booking["date"]).date()
    pretty_date = on_date.strftime("%A, %B %-d, %Y")

    body = f"""
<div class='confirm-card'>
  <div class='check'>✓</div>
  <h1 style='margin:0 0 4px'>You're booked.</h1>
  <div class='meta'>Confirmation sent to {booking['email']}</div>

  <div style='margin-top:18px'>
    <div class='row'><div class='k'>Restaurant</div><div class='v'>{booking['restaurant_name']}</div></div>
    <div class='row'><div class='k'>Date</div><div class='v'>{pretty_date}</div></div>
    <div class='row'><div class='k'>Time</div><div class='v'>{_fmt_time(booking['time'])}</div></div>
    <div class='row'><div class='k'>Party</div><div class='v'>{booking['party_size']}</div></div>
    <div class='row'><div class='k'>Name</div><div class='v'>{booking['name_on_reservation']}</div></div>
    <div class='row'><div class='k'>Confirmation</div><div class='v code'>{code}</div></div>
  </div>
</div>
"""
    return HTMLResponse(_layout("Reservation confirmed", body))


def _fmt_time(t: str) -> str:
    """24h 'HH:MM' → 12h '7:30pm'."""
    try:
        h, m = t.split(":")
        h_int = int(h)
        suffix = "pm" if h_int >= 12 else "am"
        h12 = h_int - 12 if h_int > 12 else (h_int or 12)
        return f"{h12}:{m}{suffix}"
    except Exception:
        return t
