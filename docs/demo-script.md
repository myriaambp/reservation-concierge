# Tableau — 5-Minute Demo Video Script

> **Team.** Myriam Bengoechea Pardo (`mb5500`) and Blanca Valera Caballero (`bv2358`). IEORE4576 Capstone, Columbia Spring 2026.

## Roles

- **Myriam** — driver. Owns the screen + technical narration. Strongest moments: how the agent works, why the architecture matters, the final pitch close.
- **Blanca** — narrator. Owns the business framing + spoken delivery during spinner/loading moments. Strongest moments: the persona, the unit economics, the platform-partnership ask.

---

## Pre-record checklist (5 minutes before recording)

- [ ] Open `https://concierge-web-eheg65qzwa-uc.a.run.app` in a clean Chrome window. Maximize.
- [ ] Sign in as `Priya Shah` / `myriam.bp12@gmail.com`. Click **Sign in**.
- [ ] **Settings tab** → save email + cuisines `Italian, Korean` + neighborhoods `West Village, NoMad`. Click **Save preferences**.
- [ ] **Concierge tab** → type *"Watch Don Angie next Friday for 2"* → wait for the agent to confirm. Stop here. This is the watch the audience will see.
- [ ] Switch back to **Home tab**. The watch should be visible.
- [ ] Open Gmail in a second tab.
- [ ] Open **docs/one-pager.pdf** in a third tab (you'll show the unit-economics table from this).
- [ ] Test the auto-book once before recording so you know roughly how long the spinner runs (~12s on Cloud Run).

---

## Elevator pitch — Myriam delivers in 0:00–0:25

> *"Tableau is the Bloomberg Terminal for the 600 hardest reservations in New York. You tell us a restaurant, a date, and a party size. The moment a slot opens that fits, our agent books it for you and emails you the confirmation. Real diners spend hours refreshing Resy. We turn that ritual into a $19 subscription with 93% gross margin."*

22 seconds at a normal pace.

---

## The script

### 0:00–0:25 · Open & elevator pitch
**Myriam:** *delivers the elevator pitch above.*
**Screen:** the live app at `concierge-web-eheg65qzwa-uc.a.run.app` — Home tab, hero visible, Don Angie watch visible.

### 0:25–1:00 · Persona
**Blanca:** *"Meet Priya. 31. Business development at a venture firm. She books six special-occasion dinners a year. Last month she spent four hours refreshing Resy and still ate at her second-choice restaurant on her own birthday. There are 50,000 people like Priya in NYC alone. Appointment Trader did $80 million last year selling them reservations off-platform. The willingness-to-pay is proven."*
**Screen:** Stay on Home tab. Hover-highlight the persona stats so the viewer's eye follows.

### 1:00–1:20 · The watch
**Myriam:** *"Here's what Priya did before recording. She told the agent: watch Don Angie next Friday for 2. The agent registered the watch, set it to auto-book if a matching slot opens, and now polls every 2 minutes. 95% of those polls cost us nothing — the scout hash-diffs the page and short-circuits before any LLM call. That's the lever that makes the unit economics work."*
**Screen:** Click into the **Watching for you** card on Home — show the Don Angie watch with party 2 + Friday date.

### 1:20–1:35 · Switch to Demo Mode
**Myriam:** *"Now let's pretend a slot just opened. I'll switch to Demo Mode."*
**Screen:** Click the **Demo Mode** tab. Tiles for 8 restaurants visible.

### 1:35–1:45 · Trigger auto-book
**Myriam:** *"I'm clicking Auto-book on Don Angie. Watch what happens — the agent is going to open a real browser server-side and complete the booking on its own."*
**Screen:** Click the **🤖 Auto-book on Resy** button on the **Don Angie** tile. Spinner appears.

### 1:45–2:10 · Spinner narration (~12s)
**Blanca** *(during the spinner)*: *"The agent is opening Chromium on Cloud Run right now. It's navigating to the booking page with the date and party already pre-filled. It clicks the matching time, fills in Priya's name and email, submits, and captures the confirmation page. We don't have a Resy partnership yet — so the agent does this against TableTime, our sandboxed copy of Resy. The architecture is the same: the day a real partnership is signed, we flip one environment variable."*
**Screen:** Wait. Don't click. The spinner is the show.

### 2:10–2:30 · Confirmation
**Myriam:** *"And there it is — booked. Confirmation TBL-something. These are the four screenshots the agent took."*
**Screen:** Confirmation success message renders. Scroll down through the four screenshots. Briefly point at `04-confirmation.png`.

### 2:30–2:50 · The email
**Myriam:** *"And here's the email it sent."*
**Screen:** Switch to your **Gmail tab**. Open the most recent message — should be **"Slot opened: Don Angie 7:30pm Fri"** from Resend. Hover over the **Confirm on Tabletime** button so the URL preview shows briefly.

### 2:50–3:00 · Tying back
**Myriam:** *"One tap on that link takes Priya to the booking page Resy itself would render. The agent already filled it. She just confirms."*
**Screen:** Switch back to Tableau.

### 3:00–3:45 · Unit economics
**Blanca:** *"Now the economics. One user-month: 4 active watches, polling every 2 minutes. Total cost to serve — including all LLM calls, browser automation, hosting, and email — comes to about $1.30. We charge $19 a month. That's a 93% gross margin. We run Gemini 2.5 Flash on Vertex AI, which bills against our GCP credits and is 10× cheaper than Claude Sonnet per token. The hash-diff scout still does the heavy lifting — polling is 99% of call volume but only 5% of LLM tokens."*
**Screen:** Open **one-pager.pdf** in another tab. Show the unit economics table on page 2. Point at the $1.30 row.

### 3:45–4:15 · Where it breaks
**Blanca:** *"Three things break us. Without a Resy partnership we can't book on the real platforms — that's why we run on a sandbox today. Polling cadence pressure if a competitor goes sub-30-second. Cold-start without behavioral data. We name these honestly because the path forward solves them."*
**Screen:** Stay on the one-pager. Scroll to the "Where it breaks" section briefly, then to "Path forward."

### 4:15–4:45 · Path forward & ask
**Myriam:** *"The path forward is partnership with Resy, OpenTable, or Tock. The architecture is built for this. The pitch to them is simple: Appointment Trader moved $80 million in unauthorized cancellation arbitrage last year. We turn that gray market into legitimate platform revenue. Two deal structures: $2 to $4 per-booking referral fee, or license the product as Resy Concierge — the consumer-side premium tier they won't build in-house because it'd cannibalize their restaurant relationships."*
**Screen:** Switch back to Tableau → **Settings** tab → scroll to the "How does it actually book?" panel.

### 4:45–5:00 · Close
**Myriam:** *"That's Tableau. We watch. We rank. We book. Live at concierge-web-eheg65qzwa-uc.a.run.app. The agent code, the eval suite, and the one-pager are at github.com/myriaambp/reservation-concierge. Our ask: a first conversation with one of the three platforms. Thank you."*
**Screen:** Show the URL in the address bar one last time. End.

---

## Backup plan (if the deployed app fails mid-recording)

1. **Run locally**: `uvicorn backend.api.main:app --port 8000` and `streamlit run frontend/streamlit_app.py`. Local works even if Cloud Run is throttled. Same behavior.
2. **Pre-record the demo segment** (1:35–2:30) on its own as a screencap and edit it in. The auto-book flow is the riskiest 25 seconds; if it fails on the live take, splice in the pre-recorded version.

Record one full take, then re-record the demo segment 2-3 times back-to-back so you have clean takes to choose from.

---

## Delivery notes

- **Eye contact with the camera** during the elevator pitch and the pitch close. Both are Myriam.
- **Energy spike at 2:10** when the confirmation lands. This is the visual payoff. Smile. Slight pause. Let it breathe.
- **Numbers slow** during 3:00–3:45. $1.30. $19. 93%. Each one gets its own beat. Investors remember numbers.
- **The line *"we turn the gray market into legitimate platform revenue"*** is the killer line of the pitch. Don't rush it.
