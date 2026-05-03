# Tableau — One-Pager

> *The Bloomberg Terminal for the 600 restaurants where access* is *the product.*

---

## The user

**Priya Shah, 31. Business development at a venture firm. Upper East Side.** She books six special-occasion dinners a year — anniversaries, client wins, friend birthdays for groups of six. She has Resy, OpenTable, Tock, and Yelp Reservations on her home screen. Last month she spent **roughly four hours refreshing them** and still ate at her second-choice restaurant on her own birthday.

There are ~50,000 people like Priya in NYC alone: 28-to-45-year-old professionals making $200K+ who treat the hardest reservations as social signaling and would happily pay $19/month to outsource the refresh-and-pray ritual. Tableau is for them. Not for the long tail of casual diners — Resy already serves those well.

---

## The problem

Priya's behavior today:

1. Sets a phone alarm for 9:00 AM exactly 30 days before the date she wants. Refreshes the Carbone calendar at 10:00 AM ET. Loses to bots and scalpers within 8 seconds.
2. Joins the Resy notify list, gets one email a week saying "a slot opened" — but only after it's already gone.
3. Buys reservations on Appointment Trader for $50–$500 each. Appointment Trader sold $80M+ of reservations last year, almost all to people like Priya. **The willingness-to-pay is proven.**

What she actually needs:
- Continuous monitoring she doesn't have to think about.
- A *judgment layer* — most "open slots" don't fit (wrong time, wrong size, wrong vibe). She wants the ones that fit her.
- One tap to confirm.

---

## The product

A multi-agent system. Five LangGraph nodes:

1. **Supervisor** — parses "watch Don Angie next Friday for 2" into a structured `Watch`.
2. **Scout** — every 2 minutes, polls availability and hash-diffs against the last snapshot. **95% of ticks short-circuit on the hash, never calling an LLM.** This is the lever that makes the unit economics work.
3. **Ranker** — when a slot opens, retrieves restaurant context (RAG over food-media editorial) plus user history and writes a 2-sentence "why this fits."
4. **Notifier** — fires an in-app + email notification.
5. **Booker** — Human-in-the-loop. Refuses to act without a confirmation token minted from the user's tap.

Live demo: <https://concierge-web-_HASH_-uc.a.run.app>.

---

## Unit economics — one user-month

Assumes 4 active watches, 2-minute polling cadence, 30-day window.

| Item | Volume | Cost |
|---|---|---|
| Scout polling — 95% short-circuit on hash; 5% trigger Sonnet (300 in / 50 out) | ~1,400 ticks | **$1.30** |
| Ranker (Sonnet, 2K in / 400 out) on 8 slot-opens | 8 | $0.10 |
| Supervisor + chat (Opus, 5 turns, 3K in / 600 out) | 5 | $0.45 |
| Booker (Opus, 4K in / 500 out) on 2 successful books | 2 | $0.20 |
| Embeddings (Vertex `text-embedding-005`, amortized) | one-time | $0.01 |
| Cloud Run + Firestore (amortized over 100 users) | — | $0.40 |
| Email (SendGrid free up to 100/day) | 8 | $0.00 |
| **Total COGS** | | **~$2.46** |

**Pricing**
- **Concierge $19/mo** — 4 watches, in-app + email
- **Concierge+ $49/mo** — 10 watches, priority queue, SMS

**Gross margin** at $19: **87%**. Breakeven CAC at 6-mo payback: ~$60. Aspirational LTV at 18-mo retention: ~$340.

### Where it breaks (named honestly)

1. **Resy / OpenTable cease-and-desist.** Most likely outcome of unauthorized scraping. **Mitigation** built into the architecture: every provider call sits behind an interface; the demo runs on `MockResyProvider` only. The path forward is partnership, not adversarial scraping. We have a B2B pivot pre-built (below).
2. **Polling cadence pressure.** If a competitor offers sub-30-second polling, costs scale 4× and margin compresses to ~60%. Still profitable, but the moat shifts from raw frequency to ranker quality.
3. **Cold-start.** No users → no behavioral signal → the Ranker reduces to defaults. We mitigate by launching with a partner concierge desk (one already in conversation, see below) so the Ranker has multi-user behavioral data on Day 1.
4. **Anthropic price moves.** A 3× Sonnet price hike compresses margin to ~50%. The LLM client wrapper is built around an `agent_name` cost ledger; swapping Sonnet for Haiku 4.5 on the Notifier and Scout would recover most of it.

### Path forward

White-label API → luxury hotel concierge desks (Aman, 1 Hotels, Faena, Mark Hotel). Tested estimate: **$5,000/mo per property × 50 properties → $3M ARR with one BD hire.** This pivot solves both cold-start (hotels supply behavioral data) and ToS risk (hotels have direct restaurant relationships). The consumer subscription is the wedge; concierge B2B is the business.

---

## Why these technical choices

| Choice | How it serves the user, problem, or economics |
|---|---|
| **Multi-agent (LangGraph)** | The user's question ("watch this thing for me") naturally decomposes into specialists: parsing, polling, ranking, formatting, booking. A single-prompt agent would re-do the parsing every tick — that's the cost trap multi-agent avoids. |
| **Hash-diff Scout that mostly skips the LLM** | The single biggest lever in our economics. Polling is the dominant cost; making 95% of polls free changes the COGS from $5 to $1.30. |
| **Claude Opus 4.7 supervisor + Sonnet 4.6 workers** | Opus runs only at human-facing decision points (intent parsing, booking confirmation). Sonnet runs the volume work. Total LLM share of COGS is ~$2/user/mo — an 11% cost-to-revenue ratio. |
| **Firestore (incl. vector search) instead of Postgres + pgvector + Memorystore** | One service, single-digit-cents scaling, no minimum spend. Replaces three GCP services that would cost ~$50/mo idle. Critical at MVP — we pay nothing until users show up. |
| **Cloud Run min-instances=0** | Idle cost approaches zero. We can run at $19 user-month margin from user 1. |
| **HITL gate on the Booker** | Refuses to call `book_slot` without a token minted from the user's tap. Both a UX win (no surprise charges) and a legal posture (we don't auto-book without consent). |
| **`MockResyProvider` behind a `ReservationProvider` interface** | The product runs on mock data. The day a partnership exists, we flip a flag and the *agent stack doesn't change*. This is the architectural answer to the legal question. |

---

## What we're asking for

A path to launch with one luxury-hotel concierge partner. We have the agent stack, the pricing model, and a defensible architectural answer to the regulatory question. We need 90 days and a single hospitality-side relationship to validate B2B pricing before opening the consumer flywheel.

---

*Built by Myriam Bengoechea Pardo (`mb5500`) and Blanca Valera Caballero (`bv2358`) for IEORE4576 — Agentic AI for Analytics, Columbia, Spring 2026. GitHub: <https://github.com/myriaambp/reservation-concierge>.*
