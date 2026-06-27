# Life OS — a private, multi-agent AI for your real life (finance first)

> **Kaggle "AI Agents: Intensive Vibe Coding" Capstone** — *Concierge Agents* track.
> A private, values-grounded agent system that helps you manage your money and your
> major life decisions — starting with personal finance, designed to extend to health,
> career, and goals.

---

## The problem

Personal finance tools are generic. They don't know *you* — your goals, your risk
appetite, your non-negotiables, the fact that you and your partner decide big things
together. So their advice is generic too. And the data is scattered across statements
and portals you have to check by hand.

**Life OS** is a private AI that ingests your real financial data, computes the exact
numbers, and reasons about your decisions **grounded in your own documented values** —
then only interrupts you when a human decision actually matters.

## Why agents?

A single prompt can't do this well. Different judgments need different lenses, exact
money math must never be hallucinated, and risky actions need a human in the loop. So
the system is a **mesh of specialized agents**, each with one job:

| Agent | Role | Status |
|---|---|---|
| **Archivist** | Ingests dropped documents → text → vector memory (RAG) | ✅ |
| **Accountant** | Parses statements, categorizes, computes **exact** finance math | ✅ |
| **Mentor** | Conversational Q&A grounded in your numbers + values | ✅ |
| **Board of Directors** | 5-agent debate that rules on major life decisions | ✅ (centerpiece) |
| **Expense Sentinel** | Ambient ADK agent: screen → route → human approval (Cloud Run) | ✅ (companion) |
| **Daily Guide** | Proactive daily safe-to-spend + one nudge | 🔜 roadmap |
| **Signal Agent** | Public-catalyst alerts for opportunistic windfall plays | 🔜 roadmap |

## The centerpiece: Board of Directors

When you face a big decision, four persona advisors — **Financial CFO, Visionary CEO,
Health Coach, Devil's Advocate** — debate it. A fifth **Synthesizer** weighs the debate
against your `life-os-foundation` (your real goals, risk posture, and **non-negotiable
constraints**) and issues a ruling. The non-negotiables are sacred: the Board will
refuse any option that breaks them, no matter how persuasive the argument.

```bash
python -m src.agents.board "Should I take a $20K loan for a vacation?"
```

## Key design principles

- **Hybrid memory.** Hard facts and numbers are **computed exactly** (Decimal math) and
  never embedded or "RAG'd" — the LLM only *narrates* numbers, never invents them. Soft,
  textual things (notes, goals, past messages) live in a vector store for meaning-based
  recall. *Don't RAG your balance.*
- **Values-grounded agents.** Every agent reads a `life-os-foundation` document so it
  reasons about **this specific person's** goals, not generic advice.
- **Privacy-first.** Personal data and core values are kept local and out of version
  control; secrets live in Secret Manager; risky actions are human-in-the-loop only.

## Architecture

```
   Documents / statements            Plaid / live feeds (roadmap)
            │                                  │
            ▼                                  ▼
      [Archivist]                        [Accountant]
   text → vector store              exact finance math
            │                                  │
            └───────────────┬──────────────────┘
                            ▼
                  life-os-foundation  ← your values & non-negotiables
                            │
         ┌──────────────────┼─────────────────────┐
         ▼                  ▼                      ▼
     [Mentor]        [Board of Directors]   [Expense Sentinel — ADK, Cloud Run]
   grounded chat     5-agent debate + ruling   ambient screen → approve
```

## Course concepts demonstrated

- **Multi-agent systems (ADK)** — the Board's debate + the ADK Expense Sentinel
- **Security** — deterministic PII / prompt-injection screen before the LLM; secrets in
  Secret Manager; authenticated Cloud Run
- **Deployability** — Expense Sentinel deployed to Cloud Run (scale-to-zero)
- **Agent skills** — `agents-cli` scaffold + deploy
- **Antigravity** — used to build (see video)

## Tech stack

Gemini (`google-genai`) · Google ADK 2.0 · Cloud Run · Pub/Sub + Eventarc · FastAPI ·
PostgreSQL + pgvector (with an offline local backend) · pytest · `uv`.

## Run it locally

Works fully offline with the `local` provider — no cloud/API key needed for tests.

```bash
# 1. Install (uses uv)
uv sync --all-groups

# 2. Configure
cp .env.example .env          # for real Gemini, set GOOGLE_API_KEY and CLOUD_PROVIDER=gcp

# 3. Try it
python -m src.agents.board  "Should I buy a $40K car now or wait?"     # multi-agent debate
python -m src.agents.mentor "How am I doing on savings?"               # grounded chat
python -m src.serving.finance_cli summary data/finance/sample_transactions.csv

# 4. Tests (offline, no key required)
.venv/Scripts/python -m pytest tests -q
```

> The included `data/finance/sample_transactions.csv` is synthetic. Real statements and
> personal values stay on your machine (gitignored).

## Status

Working end-to-end on synthetic data: ingestion + RAG, finance vertical (parse →
categorize → analyze → safe-to-spend), the Mentor, and the Board of Directors. The
Expense Sentinel is deployed to Cloud Run. Daily Guide, Signal Agent, and the Eventarc
trigger are the next steps. Built one domain at a time — finance first.
