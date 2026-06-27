# Phase 1 — Finances (Technical Design)

**Purpose:** The first vertical of my Life OS. Prove the full loop — onboarding →
automated ingestion → structured + semantic storage → daily guidance with learning
loop → chat — on one domain before expanding to health, career, and planning.


## What it delivers

- A daily "safe-to-spend" figure for me and my wife, with a short personalized message
  to each of us that improves over time based on our feedback.
- A finance chatbot: ask anything about my money, get an answer grounded in my real
  accounts, history, and the decisions I made during onboarding.
- Tracks accounts, transactions, balances, loans/debts, budget, and credit score.


## Step 0: Onboarding via Grill Me

Before any code runs, the system needs to understand my financial life deeply. I run
the Grill Me skill (see `grill-me-skill.md`) on the finances domain.

What gets captured:
- All accounts (checking, savings, credit cards, investments, retirement)
- All debts and loans (amounts, rates, minimum payments, payoff strategy)
- Income sources and frequency
- Fixed bills and their due dates
- Budget philosophy (envelope style, percentage-based, or flexible)
- Savings goals and timeline
- How my wife and I split financial decisions and responsibilities
- Risk tolerance
- Credit score and how I track it
- What financial stress looks like for us
- Communication preferences (how each of us wants to be talked to about money)

Output: `brainstorms/finances.md` — the foundational context document that the daily
job and chatbot read before every interaction.


## Data & ingestion (NO manual entry)

Two automatic paths feed one normalized store:

### Path 1: Document drop zone
I drop raw bank/loan statements (PDF, CSV, exports) into one cloud folder/bucket.
An automated pipeline parses and extracts them (document AI / OCR + LLM extraction)
and converts them into structured transactions. No typing into Excel, ever.

### Path 2: Live feeds
Bank aggregation (e.g. Plaid) pulls balances, transactions, and liabilities
automatically for connected accounts.

### Notes
- Credit score is captured from its source / entered once (not available via Plaid).
- Everything is de-duplicated and categorized automatically.
- If the system can answer a question by reading an existing file, it reads the file
  instead of asking me.


## Data model (hybrid)

- **Structured store (relational):** accounts, transactions, balances, loans, budget,
  category rules, daily snapshots, feedback signals. Used for exact computation.
- **Vector store (pgvector / RAG):** brainstorm files, notes, goals, past daily
  messages, reflections, Q&A logs from Grill Me sessions. Used for meaning-based
  recall in chat.
- One Postgres database can hold both (pgvector extension).


## Daily process (scheduled)

1. Ingest new documents from drop zone + sync live feeds.
2. Normalize, de-duplicate, categorize.
3. Read `brainstorms/finances.md` for my context and preferences.
4. Read last 30 days of feedback signals (see Feedback Loop below).
5. Compute safe-to-spend per person:
   `(income this period − remaining fixed bills − savings goal − spent so far) ÷ days left`
   Math in code, not the LLM.
6. Save a daily snapshot.
7. LLM writes a personalized note for me and one for my wife, using:
   - The computed numbers
   - My context from the brainstorm file
   - Recent feedback patterns ("he acts on X, ignores Y")
   - Any flags (bill due soon, category over budget, goal milestone)
8. Deliver to each of us.


## Feedback loop (Reinforcement Learning)

### Layer 1 — Feedback-conditioned memory (build with v1)

**What gets captured (per daily message):**

| Signal          | Type       | Example                                      |
|-----------------|------------|----------------------------------------------|
| reaction        | enum       | thumbs_up, thumbs_down, ignored, acted_on    |
| outcome         | text/enum  | "budget held", "went over by $80"            |
| note            | free text  | "this tip about groceries was actually useful"|
| suggestion_type | tag        | bill_warning, savings_tip, spending_alert     |
| person          | enum       | me, wife                                     |
| date            | date       | 2026-07-15                                   |

**How it feeds back in:**
- The daily job queries: "last 30 days of feedback where person = me"
- Builds a brief summary: "Acts on bill warnings (8/8). Ignores generic savings tips
  (1/10). Prefers specific dollar amounts over percentages. Wife responds to weekly
  summaries more than daily nudges."
- This summary is included in the LLM prompt, after the computed numbers and before
  the message-writing instruction.

**Storage:** A `feedback` table in the same Postgres database. Simple structured data,
no vector embedding needed.

### Layer 2 — Lightweight RL (build after ~3 months of data)

- A contextual bandit model trained on the feedback table.
- Input features: current balances, day of month, recent spending velocity, category
  distribution, upcoming bills, past feedback pattern.
- Output: ranked list of suggestion types most likely to be both approved AND lead to
  positive outcomes.
- The daily job uses this ranking to select which suggestions to pass to the LLM.
- Retrained weekly on the latest feedback data.
- Small model (few hundred parameters), runs locally or in the same Cloud Run job.

### Design rule
Always weight OUTCOME more than APPROVAL. If I thumbs-down a warning but the warning
was correct (I did go over budget), the system should keep warning me — not stop
because I didn't like hearing it. A good mentor tells you what you need to hear.


## Chat surface

Retrieval-augmented Q&A:
1. User asks a question.
2. System queries structured tables for hard facts (balances, transactions, budget).
3. System queries pgvector for relevant context (brainstorm decisions, past messages,
   feedback notes).
4. Both are merged into a prompt with the LLM.
5. LLM answers grounded in my real data.

Example: "Why did we set our savings rate at 20%?"
→ Retrieves the Q&A log from `brainstorms/finances.md` where I explained my reasoning
  during the Grill Me session → answers with my own words and logic.


## Delivery

Telegram and/or email to each person (channel is flexible).
- Telegram: bot token + POST to sendMessage endpoint (free, simple).
- Email: via Gmail API or SMTP.
- WhatsApp: possible via Business API / Twilio (more setup, add later).


## Hosting (GCP — services flexible)

Runs entirely in my own GCP project, always-on, with no dependency on my personal
computer. Specific services can change; the functions needed are:

- A scheduler (daily trigger) → Cloud Scheduler
- A serverless runtime for pipeline, ingestion, chat backend → Cloud Run
- Object storage for the document drop zone → Cloud Storage
- A managed relational DB with vector support → Cloud SQL for PostgreSQL + pgvector
- A secrets vault for all credentials → Secret Manager
- An LLM → Vertex AI (Claude) or Anthropic API
- Document parsing → Document AI / OCR + LLM extraction


## Security & privacy (first-class)

- All credentials (bank tokens, API keys, bot tokens) in Secret Manager — never in the
  data store or in the documents.
- Encryption at rest and in transit; least-privilege access; scheduled endpoints
  authenticated, not public.
- Only aggregated figures sent to the LLM — never raw account numbers or full PII.
- Family data included only with consent.
- Regular backups.
- Brainstorm files stored encrypted — they contain deeply personal context.


## Definition of done (Phase 1)

- [ ] Grill Me session completed for finances → `brainstorms/finances.md` exists and
      has zero open flags.
- [ ] I drop a statement in the folder and it becomes searchable, categorized data with
      zero manual entry.
- [ ] Connected accounts sync automatically.
- [ ] I receive a trustworthy daily safe-to-spend message; so does my wife.
- [ ] Feedback capture is working (I can thumbs-up/down each message).
- [ ] After 2 weeks, the daily message visibly reflects my feedback patterns.
- [ ] I can chat with my finances and get grounded answers.
- [ ] All data hosted in my GCP project and protected as above.


## Candidate tools (flexible — decide later)

- Onboarding: Grill Me skill in Claude Code or Cowork
- Ingestion / parsing: Document AI / OCR + LLM extraction
- Aggregation: Plaid (or SimpleFIN)
- Runtime + schedule: Cloud Run + Cloud Scheduler
- Storage: Cloud Storage (drop zone) + Cloud SQL for PostgreSQL with pgvector
- Secrets: Secret Manager
- LLM: Claude via Vertex AI (or Anthropic API)
- Delivery: Telegram Bot API / email
- RL (Layer 2): scikit-learn contextual bandit or custom lightweight model
