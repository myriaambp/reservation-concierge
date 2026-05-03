# Tableau — The Reservation Concierge Agent

> *The Bloomberg Terminal for the 600 restaurants where access* is *the product.*

A multi-agent system that monitors hard-to-book NYC restaurants on your behalf, explains *why* a slot fits when it opens, and books with one tap.

- **Live demo:** _https://concierge-web-<hash>-uc.a.run.app_ (filled in after deploy)
- **Business one-pager:** [docs/one-pager.md](docs/one-pager.md)
- **Architecture diagram:** [docs/architecture.png](docs/architecture.png)
- **Course:** IEORE4576 Agentic AI for Analytics, Columbia, Spring 2026

---

## What it does

1. User says *"Watch Don Angie, party of 2, next Friday or Saturday after 7pm."*
2. Supervisor agent parses intent → registers a `Watch`.
3. Every 2 minutes, a Scout sub-agent polls availability and hash-diffs against the last snapshot. **95% of ticks short-circuit on the hash — no LLM call.**
4. On a slot opening, a Ranker agent retrieves restaurant context (RAG) + user history and writes a personalized "why this fits" note.
5. A Notifier agent fires an in-app toast and email.
6. User taps **Book** → Booker agent enters a HITL confirmation gate before calling `book_slot()`.

## Class concepts (rubric calls for 3+; we ship 6)

| Concept | Where in the code | What to look at |
|---|---|---|
| **Tool calling** (Feb 16 lecture) | `backend/tools/reservation_tools.py` | Anthropic tool schemas + dispatch table; every agent decision is a tool call |
| **Multi-agent / orchestration** | `backend/agents/graph.py`, `backend/agents/{supervisor,scout,ranker,notifier,booker}.py` | LangGraph `StateGraph` with 5 nodes + conditional routing |
| **RAG / vector search** | `backend/rag/retriever.py`, `backend/rag/ingest.py` | Vertex `text-embedding-005` → Firestore vector index (FAISS local fallback) |
| **Memory / state** | `backend/memory/state.py`, `backend/memory/firestore_store.py` | LangGraph `State` TypedDict + Firestore-backed user prefs / watches |
| **Evaluation** (Feb 09 lecture) | `backend/evals/run_evals.py`, `backend/evals/cases.json` | 20-case suite, LLM-as-judge using Opus, intent + ranking + notification quality |
| **Context engineering** (Feb 02 lecture) | `backend/agents/prompts.py` | Per-agent system prompts, tool-result compression, scratchpad pruning |

Bonus: **Constrained decoding** (Feb 16 lecture) — every tool input is a Pydantic-validated schema, fed to Anthropic as a JSON Schema; outputs are guaranteed-shape.

## Tech stack & why

| Choice | Why this for *this* business |
|---|---|
| **LangGraph** | Multi-agent orchestration is the rubric concept the panel will scrutinize most. The graph is screenshottable. State checkpointer doubles as the memory primitive. |
| **Claude (Opus 4.7 supervisor + booker, Sonnet 4.6 workers)** | Cheap workers for the 95%-no-LLM polling path; expensive only at the user-facing decision points. Drives our $2.46/user-month COGS. |
| **Firestore (incl. vector search)** | Replaces Cloud SQL + pgvector + Memorystore in one service — single-digit-cents/user/month at our scale, scales to millions without re-architecting. |
| **Cloud Run** | Min-instances=0, scales-to-zero. We pay only when users chat. Critical for our 87% margin at $19/mo. |
| **Cloud Scheduler → /internal/tick** | Cron-as-a-service. We don't run a Pub/Sub topic or Cloud Tasks queue, saving 1 day of plumbing and ~$5/month minimum spend. |
| **Streamlit (themed)** | Two-day delta vs Next.js, and our user is buying the *agent's intelligence*, not pixel-perfect UI. |
| **Mock provider behind an interface** | The `LiveResyProvider` stub exists, never enabled. The day Resy partners (or we acquire a Tock-style relationship), we flip a flag. Plan for it; don't act on it. |

## Run locally

```bash
git clone <repo-url> reservation-concierge
cd reservation-concierge

# 1. Create venv + install
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env: ANTHROPIC_API_KEY, GCP_PROJECT_ID, etc.

# 3. (Optional) Use the local Firestore emulator
# gcloud emulators firestore start --host-port=localhost:8088
# export FIRESTORE_EMULATOR_HOST=localhost:8088

# 4. Seed the restaurant knowledge base
python -m backend.rag.ingest

# 5. Run the eval suite (sanity)
python -m backend.evals.run_evals

# 6. Start the API
uvicorn backend.api.main:app --reload --port 8000

# 7. In another terminal, start the UI
streamlit run frontend/streamlit_app.py
```

Open <http://localhost:8501>.

## Deploy to GCP

```bash
# One-time setup (replace PROJECT_ID)
gcloud config set project PROJECT_ID
gcloud services enable \
  run.googleapis.com \
  cloudscheduler.googleapis.com \
  firestore.googleapis.com \
  aiplatform.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com

# Build + deploy
bash infra/deploy.sh
```

The script provisions both Cloud Run services, the Firestore vector index, the Cloud Scheduler cron, and writes the URLs to `.env.deploy`.

## Repo layout

```
reservation-concierge/
├── backend/
│   ├── agents/             # 5-node LangGraph (multi-agent class concept)
│   ├── tools/              # Anthropic tool schemas (tool-use class concept)
│   ├── rag/                # ingest + retriever (RAG class concept)
│   ├── memory/             # State + Firestore store (memory class concept)
│   ├── evals/              # 20-case suite + LLM-as-judge (evals class concept)
│   ├── providers/          # ReservationProvider interface + Mock
│   ├── llm/                # Anthropic client wrapper, cost tracker
│   ├── api/                # FastAPI: /api/chat, /api/watch, /internal/tick
│   └── config.py           # Pydantic settings
├── frontend/
│   └── streamlit_app.py    # Themed Streamlit UI
├── infra/
│   ├── Dockerfile
│   ├── cloudbuild.yaml
│   └── deploy.sh
├── docs/
│   ├── one-pager.md        # Business doc (rubric submission)
│   ├── pitch-deck-outline.md
│   └── architecture.png
├── seed_data/
│   ├── restaurants.json    # 30 NYC hard-to-book restaurants
│   └── fixtures.json       # demo replay
└── README.md
```

## Team

- Myriam Bengoechea Pardo (`mb5500`)
- Blanca Valera Caballero (`bv2358`)

## License

MIT — see [LICENSE](LICENSE).
