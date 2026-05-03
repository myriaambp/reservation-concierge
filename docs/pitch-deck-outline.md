# Pitch Deck Outline (3-min cap, slides optional)

The panel has read the one-pager. Don't repeat it. Show product, then ask.

## Slide 1 — Title (5s)
**Tableau.** *The Bloomberg Terminal for the 600 restaurants where access is the product.*
Live demo URL on screen.
Myriam Bengoechea Pardo (`mb5500`) · Blanca Valera Caballero (`bv2358`) — IEORE4576, Spring 2026.

## Slide 2 — The user, in one breath (10s)
"Priya. 31. VC business development. Spent four hours last month refreshing Resy and ate at her second-choice restaurant on her own birthday."

## Slide 3 — Demo (90s — the centerpiece)
1. Open Tableau. (5s)
2. Type into chat: *"Watch Don Angie next Friday for 2."* (15s)
3. Switch to Watches tab — confirm watch added. (10s)
4. Switch to **agent trace tab** (Langfuse if up; else Streamlit debug panel) — narrate: "This is the supervisor calling `add_watch`. This is the Scout polling. The hash matched, so no LLM call." (25s)
5. Hit "Replay fixture" → Don Angie 7:30pm Friday opens. Notification arrives in-app. Read the Ranker's "why this fits" line aloud. (20s)
6. Tap "Book it." HITL modal. Confirm. Confirmation code. (15s)

## Slide 4 — Why this works as a business (35s)
- Show cost ticker on screen: ~$0.04 spend during the demo.
- "$2.46 cost / $19 price = 87% margin."
- "Appointment Trader did $80M last year. The willingness to pay is proven."
- "We're not building a marketplace. We're building the intelligence layer on top of one."

## Slide 5 — Where it breaks + the pivot (30s)
"Three things break us. Without sanctioned API access we never book on the real platforms — that's why our demo runs against a sandbox we own. Polling can get cheaper to attack. Cold-start is real."
"That's why our path forward is partnership with Resy, OpenTable, or Tock. The architecture already speaks their interface — we flip one env var when a contract exists. Two structures we'd take: $2–4 per-booking referral, or license the product as Resy Concierge. Appointment Trader did $80M of unauthorized cancellation arbitrage last year. We turn that gray-market demand into legitimate platform revenue."

## Slide 6 — The ask (10s)
"A first conversation with one of the three platforms. We have the agent stack and the deal structure. We need API access."

---

## Q&A prep — 10 anticipated questions

1. **"Doesn't Resy already do notify lists?"**
   Yes, but they tell you *after* the slot is gone. We tell you with a 2-sentence rationale, in your channels, in time to book.

2. **"What's stopping Resy from building this in-house?"**
   Nothing technically. But Resy's incentives are aligned with restaurants, not diners. They'd cannibalize their own restaurant relationships if they prioritized cancellation arbitrage.

3. **"How do you avoid being the next AutoResy?"**
   AutoResy scraped real Resy without consent and auto-booked accounts they didn't own. We do neither. The agent runs against a Tableau-controlled sandbox (TableTime); the path to real bookings is partnership. Consent is given at watch creation — the user explicitly opts into a date, time, and party.

4. **"What if Vertex / Gemini pricing moves?"**
   We chose Gemini 2.5 Flash on Vertex because it bills against our GCP credits (zero out-of-pocket while we iterate) and is ~10× cheaper than Sonnet per token. Our LLM client (`backend/llm/client.py`) is provider-agnostic — `LLMResponse` unifies the shape and switching to Anthropic, OpenAI, or self-hosted only changes the inside of `chat()`. A 3× Vertex hike cuts margin from 93% to ~80%; we'd absorb it.

5. **"How do you get the first 1,000 users?"**
   NYC food media — Eater, Infatuation, New Forkers, Resy's own newsletter — is hungry for the "how to actually book the unbookable" story. Plus a referral mechanic (you and the friends you eat with each get a watch). Once we land a platform partnership, the platform's own user base becomes the funnel.

6. **"Why mock data in the demo?"**
   Because we built this to be honest. The demo proves the agent works. The legal posture is: we don't run real polling without permission. Investors should reward founders who name the regulatory question directly.

7. **"What's your churn assumption?"**
   We're modeling 5% monthly = 18-month average lifetime. The use case is sticky — restaurants stay hard to book, special occasions keep happening. We'll pressure-test with a 90-day cohort before assuming better.

8. **"Why LangGraph instead of one big prompt?"**
   Because polling is most of the cost, and a single-prompt agent re-parses intent every tick. By splitting Scout into a code-only diff with a narrow LLM escalation, we drop COGS 4×.

9. **"What's the moat once you have a platform partnership?"**
   The Ranker — the longer we've watched a user, the better our 'why this slot fits' explanation, and that's the user-facing magic. Plus the partnership itself is the moat: once Resy is incentive-aligned with us they don't sign deal #2 with our competitor.

10. **"Why are *you* the team to build this?"**
    [Your answer — leverage real strengths. If you're a Columbia IEOR student with a finance background, the unit-economics story is yours; if you're a former hospitality operator, the channel partnerships are yours.]
