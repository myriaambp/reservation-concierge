# Pitch Deck Outline (3-min cap, slides optional)

The panel has read the one-pager. Don't repeat it. Show product, then ask.

## Slide 1 — Title (5s)
**Tableau.** *The Bloomberg Terminal for the 600 restaurants where access is the product.*
Live demo URL on screen. Names + course.

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
"Three things break us. Resy can C&D us — that's why our demo runs on mock data. Polling can get cheaper to attack — we're betting on judgment, not raw frequency. Cold-start is real."
"That's why our path forward is luxury hotel concierge desks. $5K/mo per property, 50 properties, $3M ARR with one BD hire. Hotels have the behavioral data and the platform relationships. The subscription is the wedge."

## Slide 6 — The ask (10s)
"90 days, one hospitality partner. Then we open consumer."

---

## Q&A prep — 10 anticipated questions

1. **"Doesn't Resy already do notify lists?"**
   Yes, but they tell you *after* the slot is gone. We tell you with a 2-sentence rationale, in your channels, in time to book.

2. **"What's stopping Resy from building this in-house?"**
   Nothing technically. But Resy's incentives are aligned with restaurants, not diners. They'd cannibalize their own restaurant relationships if they prioritized cancellation arbitrage.

3. **"How do you avoid being the next AutoResy?"**
   AutoResy auto-booked without consent. We never auto-book — every booking goes through a HITL gate. We also operate on mock + partnership-led data, not unauthorized scraping.

4. **"Aren't your unit economics built on Anthropic pricing?"**
   Yes — and a 3× hike would compress margin to ~50%. Our LLM wrapper has model swap built in; we'd move Notifier and Scout to Haiku. The consumer market still works.

5. **"How do you get the first 1,000 users?"**
   Concierge desks at luxury hotels become channel partners. Each one already has a list of 5,000 affluent guests. Plus a referral mechanic — friends-eating-together is a built-in viral loop.

6. **"Why mock data in the demo?"**
   Because we built this to be honest. The demo proves the agent works. The legal posture is: we don't run real polling without permission. Investors should reward founders who name the regulatory question directly.

7. **"What's your churn assumption?"**
   We're modeling 5% monthly = 18-month average lifetime. The use case is sticky — restaurants stay hard to book, special occasions keep happening. We'll pressure-test with a 90-day cohort before assuming better.

8. **"Why LangGraph instead of one big prompt?"**
   Because polling is most of the cost, and a single-prompt agent re-parses intent every tick. By splitting Scout into a code-only diff with a narrow LLM escalation, we drop COGS 4×.

9. **"What's the moat once you have B2B distribution?"**
   The Ranker. The longer we've watched Priya, the better our explanation of *why a slot fits* — and that's the user-facing magic. Switching costs scale with the ranker's history.

10. **"Why are *you* the team to build this?"**
    [Your answer — leverage real strengths. If you're a Columbia IEOR student with a finance background, the unit-economics story is yours; if you're a former hospitality operator, the channel partnerships are yours.]
