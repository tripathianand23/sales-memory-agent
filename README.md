# Sales Memory Agent

Sales Memory Agent is a production-quality hackathon MVP that turns sales history into a persistent advantage. It remembers prospect interactions with Hindsight memory, recalls deal-specific context, reflects on sales strategy, and generates sharper briefs and follow-up emails over time.

## Problem Statement

Most sales assistants are stateless. They can write a polished email, but they forget the CFO objection from last week, the competitor already in the account, the promised security packet, and the stakeholder who can block procurement. That creates generic outreach at exactly the moment reps need precision.

Sales Memory Agent demonstrates the difference:

- Without memory: a generic follow-up assistant.
- With Hindsight memory: a deal-aware intelligence agent that remembers objections, budget, stakeholders, competitors, risks, and commitments.

## Why Memory Matters

Hindsight is the central feature, not an implementation detail.

- `retain()` stores structured sales memories after every logged interaction.
- `recall()` retrieves raw memories when generating briefs and emails.
- `reflect()` synthesizes strategy from the remembered deal history.
- The Streamlit UI exposes retain, recall, reflect, tags, timestamps, providers, and fallback status in the Memory Inspector.

If Hindsight credentials are missing, the app uses a SQLite-backed local fallback memory store so the demo still runs. The UI clearly marks fallback mode.

## Architecture

```text
Streamlit UI
  | Dashboard, Logger, Brief, Follow-up, Before/After, Inspector
  v
FastAPI Backend
  | /interactions, /prospects, /brief, /followup, /memory, /health/memory, /seed
  v
SQLite
  | prospects, interactions, memory_activity, local_memories
  v
Hindsight Memory Wrapper
  | HindsightMemoryClient.retain_sales_memory -> Hindsight retain() or local fallback
  | HindsightMemoryClient.recall_sales_memory -> Hindsight recall() or local fallback
  | HindsightMemoryClient.reflect_sales_strategy -> Hindsight reflect() or local fallback
  v
Groq LLM
  | deal-aware sales brief and personalized follow-up generation
```

## Project Structure

```text
sales-memory-agent/
  backend/
    main.py
    db.py
    models.py
    memory.py
    llm.py
    seed.py
    requirements.txt
  frontend/
    app.py
    requirements.txt
  README.md
  DEMO_SCRIPT.md
  .env.example
```

## Setup

Use Python 3.11 or newer.

```bash
cd sales-memory-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt
cp .env.example .env
```

Add API keys to `.env` if available.

```bash
export $(grep -v '^#' .env | xargs)
```

Start the backend:

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Start the frontend in another terminal:

```bash
cd frontend
streamlit run app.py
```

Open Streamlit, click **Seed demo data**, then run the Before vs After Demo.

## Environment Variables

| Variable | Purpose |
| --- | --- |
| `GROQ_API_KEY` | Groq API key for LLM generation. If absent, deterministic local text fallback is used. |
| `GROQ_MODEL` | Groq model name. Defaults to `llama-3.3-70b-versatile`. |
| `HINDSIGHT_API_KEY` | Hindsight Cloud API key. |
| `HINDSIGHT_BASE_URL` | Hindsight base URL. Defaults to `https://api.hindsight.vectorize.io`. |
| `HINDSIGHT_BANK_ID` | Hindsight memory bank ID. |
| `HINDSIGHT_ENABLED` | Set to `false` to force local fallback memory. Defaults to `true`. |
| `HINDSIGHT_FALLBACK_ENABLED` | Set to `false` to fail instead of using fallback when Hindsight API calls fail. Defaults to `true`. |
| `BACKEND_URL` | Streamlit backend URL. Defaults to `http://localhost:8000`. |

## Hindsight Memory Integration

The backend wraps Hindsight in `backend/memory.py` with `HindsightMemoryClient`.

### What Gets Retained

Every logged interaction is stored as structured sales memory:

- Prospect, company, role, deal ID, and interaction type
- Meeting notes, objections, competitors, budget, timeline, decision makers, and next steps
- A deterministic sales insight summarizing the next strategic angle

The retain payload includes Hindsight tags and metadata:

- `prospect_name:{name}`
- `company_name:{company}`
- `deal_id:{deal_id}`
- `memory_type:sales_interaction`
- `objection_type`
- `competitor`
- `timestamp`

### What Gets Recalled

Briefs, follow-ups, and the Memory Inspector call Hindsight `recall()` with a prospect/company/deal query and sales-interaction tags. Raw recalled memories, tags, metadata, timestamps, and memory source are shown in Streamlit.

### How Memory Improves Generation

Groq receives recalled Hindsight memories as grounding context. Without memory, the app can only write a generic follow-up. With memory, it can reference prior objections, competitors, decision makers, budget concerns, and promised next steps.

### Reflect

Sales briefs also call `reflect_sales_strategy()`. With Hindsight configured, this uses Hindsight `reflect()` to synthesize strategy. In fallback mode, it produces a clearly marked local reflection over recalled fallback memories.

The app logs every memory operation to SQLite so judges can inspect what was retained, what was recalled, the tags used, provider mode, and timestamps.

### Configure Hindsight Cloud

Add these values to `.env`:

```bash
HINDSIGHT_ENABLED=true
HINDSIGHT_API_KEY=hsk_...
HINDSIGHT_BASE_URL=https://api.hindsight.vectorize.io
HINDSIGHT_BANK_ID=your-bank-id
HINDSIGHT_FALLBACK_ENABLED=true
```

Then restart FastAPI.

### Test Memory Connection

Run:

```bash
python backend/test_hindsight.py
```

The script prints memory health, sends one test retain payload, performs one recall query, and prints returned memories. It never prints API keys.

### Fallback Mode

Fallback remains available for reliable demos:

- If `HINDSIGHT_ENABLED=false`, all memory operations use local SQLite fallback memory.
- If credentials are missing, the app uses local fallback and shows a warning.
- If Hindsight API calls fail and `HINDSIGHT_FALLBACK_ENABLED=true`, the app falls back and shows the error as a warning.
- If Hindsight API calls fail and `HINDSIGHT_FALLBACK_ENABLED=false`, the API returns a failed memory status instead of fabricating Hindsight output.

## Seed Data

Seed data includes 5 companies with 3 historical interactions each:

- Acme Logistics
- Northstar Health
- BrightBank
- CloudNova
- UrbanKart

The data includes realistic objections such as pricing, competitor lock-in, security concerns, CFO approval, integration timelines, and procurement delays.

## Demo Script

See [DEMO_SCRIPT.md](DEMO_SCRIPT.md) for a judge-ready walkthrough.

## Judging Alignment

**Innovation:** Shows memory as the difference between generic generation and deal-aware sales intelligence.

**Use of Hindsight Memory:** Retain, recall, and reflect are explicit in backend functions and visible in the UI.

**Technical Implementation:** FastAPI, Streamlit, SQLite, Groq, Hindsight wrapper, Pydantic models, seed data, graceful fallback, and clear API boundaries.

**UX:** Judges can seed data, log interactions, inspect memory, and compare before/after outputs quickly.

**Real-world Impact:** Sales teams lose deals when context disappears. This MVP shows how persistent memory can improve follow-up quality, stakeholder handling, and next-step discipline.
