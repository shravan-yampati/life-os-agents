# Reinforcement Learning — Life OS Feedback & Learning Spec

## What this is
The specification for how your Life OS learns and improves over time from your daily
interactions. This is NOT the same as the Grill Me skill — that captures who you are
on day zero. This captures how you respond to the system over weeks and months, so it
gets smarter.

## The two concepts, clearly separated

| Aspect         | Grill Me (Onboarding)                    | Reinforcement Learning (Ongoing)         |
|----------------|------------------------------------------|------------------------------------------|
| When           | Day zero, once per domain                | Day 30+, runs forever                    |
| What it does   | Extracts knowledge from your brain       | Learns from your behavior over time      |
| How it works   | AI asks you questions, you answer        | System observes what you do with its output|
| Output         | Brainstorm files (your context)          | Feedback signals (your patterns)         |
| Analogy        | Onboarding a new employee                | That employee getting better at their job |
| Fills with     | Knowledge                                | Wisdom                                   |


## Layer 1: Feedback-Conditioned Memory (build with v1)

### Overview
Store simple signals about how you respond to each daily message. Feed those signals
back to the LLM as context so it adapts its recommendations without any model training.

### Feedback signals to capture

```sql
CREATE TABLE feedback (
    id              SERIAL PRIMARY KEY,
    date            DATE NOT NULL,
    person          VARCHAR(20) NOT NULL,        -- 'me' or 'wife'
    message_id      VARCHAR(50) NOT NULL,        -- links to the daily message
    suggestion_type VARCHAR(50),                 -- bill_warning, savings_tip,
                                                 -- spending_alert, goal_progress,
                                                 -- general_nudge, weekly_summary
    reaction        VARCHAR(20),                 -- thumbs_up, thumbs_down,
                                                 -- ignored, acted_on
    outcome         VARCHAR(100),                -- 'budget_held', 'went_over_by_80',
                                                 -- 'saved_target_amount',
                                                 -- 'paid_bill_on_time'
    outcome_positive BOOLEAN,                    -- true = good result, false = bad
    note            TEXT,                         -- free text: "this was actually useful"
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_feedback_person_date ON feedback(person, date);
CREATE INDEX idx_feedback_suggestion_type ON feedback(suggestion_type);
```

### How to capture feedback
Options (implement at least one):
1. **Telegram inline buttons:** Each daily message includes thumbs-up / thumbs-down /
   "I did this" buttons. One tap, stored immediately.
2. **End-of-day prompt:** A single evening message: "Quick check — did today's tips
   help? 👍 👎" with reply options.
3. **Weekly review:** A Sunday message asking about the week's suggestions.
4. **Outcome tracking:** Automated — compare "suggested saving $200" with actual
   account balance change. No human input needed for this one.

### How the daily job uses feedback

Before calling the LLM, the daily job runs this query:

```sql
-- Get the last 30 days of feedback patterns for this person
SELECT
    suggestion_type,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE reaction = 'acted_on') as acted_on,
    COUNT(*) FILTER (WHERE reaction = 'ignored') as ignored,
    COUNT(*) FILTER (WHERE reaction = 'thumbs_up') as liked,
    COUNT(*) FILTER (WHERE outcome_positive = true) as good_outcome,
    COUNT(*) FILTER (WHERE outcome_positive = false) as bad_outcome
FROM feedback
WHERE person = 'me'
  AND date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY suggestion_type
ORDER BY total DESC;
```

This produces a summary like:
```
bill_warning:    8 sent, 8 acted on, 7 good outcomes — KEEP SENDING
savings_tip:     10 sent, 1 acted on, 0 good outcomes — REDUCE OR REPHRASE
spending_alert:  5 sent, 4 acted on, 3 good outcomes — KEEP SENDING
goal_progress:   4 sent, 3 liked, 2 good outcomes — KEEP SENDING
general_nudge:   12 sent, 2 acted on, 1 good outcome — STOP OR CHANGE APPROACH
```

This summary is injected into the LLM prompt:
```
## Feedback patterns (last 30 days)
- He always acts on bill warnings (8/8) and they lead to good outcomes.
- He ignores generic savings tips (1/10 acted on). Stop sending generic ones;
  only send savings tips tied to a specific goal or deadline.
- She prefers weekly summaries over daily nudges (acted on 6/6 weekly vs 3/15 daily).
- Spending alerts work well (4/5 acted on).
- General nudges are ignored. Replace with specific, actionable items.

Use these patterns to decide what to include and what to skip in today's message.
```

### Timeline
- Build the feedback table and capture mechanism in v1 (week 1-2).
- The system starts adapting its messages within 2 weeks of daily use.
- Visible personalization improvement within 30 days.


## Layer 2: Lightweight RL / Contextual Bandit (build after ~3 months)

### Overview
Once you have ~90 days of feedback data (hundreds of signals), train a small model
that genuinely optimizes which suggestions to surface.

### Architecture
```
Daily state → Bandit model → Ranked suggestions → LLM writes message
     ↑                              ↓
     └── Feedback signals ──────────┘
```

### Input features (state vector)
- Current checking balance (normalized)
- Current credit card balance (normalized)
- Days until next major bill
- Days remaining in pay period
- Spending velocity (last 7 days vs. average)
- Category distribution (% dining, groceries, transport, etc.)
- Day of week
- Day of month
- Recent feedback pattern (last 7 days: ratio of acted_on to ignored)
- Number of open goals
- Streak (days in a row of positive outcomes)

### Output
A score for each suggestion type. The daily job takes the top 2-3 and passes them
to the LLM for message writing.

### Reward function
```
reward = (0.3 × approval_score) + (0.7 × outcome_score)

where:
  approval_score = 1 if acted_on or thumbs_up, 0 if ignored, -0.5 if thumbs_down
  outcome_score  = 1 if outcome_positive, 0 if no outcome recorded, -1 if negative
```

Note: outcome is weighted MORE than approval (70/30). This prevents the system from
becoming a yes-man that only tells you what you want to hear.

### Implementation
- Use scikit-learn or a simple PyTorch model.
- Retrain weekly on the full feedback history.
- Model is tiny (few hundred parameters) — runs in the same Cloud Run job.
- A/B test: for the first month, run the bandit alongside the simple feedback-memory
  approach and compare which produces better outcomes.

### Timeline
- Don't build this until you have at least 90 days of feedback data.
- Premature optimization with too little data will produce a worse model than the
  simple feedback-memory approach.


## Layer 3: Full RLHF (skip for now)

Fine-tuning the LLM's weights using your personal feedback. This requires:
- Thousands of interaction examples
- Significant compute cost
- Risk of overfitting to one person's preferences
- Complex infrastructure (training pipeline, evaluation, deployment)

**Recommendation: skip this entirely.** Layers 1 and 2 will give you 95%+ of the
personalization you want. Only revisit if you have a very specific need that the
first two layers can't solve, and you have 1000+ feedback signals.


## The yes-man problem (critical design constraint)

The single biggest risk of any learning system optimized on user feedback is that it
learns to flatter you instead of help you.

Signs the system is becoming a yes-man:
- It stops sending warnings you previously thumbs-downed, even when the warnings
  were correct.
- It only shows you positive news about your finances.
- It stops challenging your spending in categories you're emotionally attached to.
- Your approval score goes up but your actual financial outcomes go down.

Mitigations built into this design:
1. Outcome weight (70%) > approval weight (30%) in the reward function.
2. A monthly "honesty audit": compare the system's suggestions against actual
   financial performance. If outcomes are declining but approval is rising, the
   system is drifting.
3. A hardcoded rule: bill warnings and over-budget alerts are NEVER suppressed
   regardless of feedback. Some messages are mandatory.
4. A quarterly re-grill: every 3 months, run a mini Grill Me session focused on
   "what's changed, what's working, what isn't" to recalibrate.


## Data flow summary

```
Day 0:   Grill Me → brainstorms/*.md → vector store + daily context
         (knowledge extraction, one-time)

Day 1+:  Bank feeds + document drops → structured data → computation
         Brainstorm context + computed numbers → LLM → daily message
         (automated pipeline, daily)

Day 1+:  You react to message → feedback table
         (signal capture, daily)

Day 30+: Feedback patterns → injected into LLM prompt
         (Layer 1: feedback-conditioned memory, automatic)

Day 90+: Feedback history → bandit model → suggestion ranking
         (Layer 2: lightweight RL, weekly retrain)
```
