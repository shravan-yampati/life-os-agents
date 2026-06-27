"""Mentor — the Life OS chat.

Answers questions about the user's money and life, grounded in THREE things:
  1. Their **foundation** (values, goals, non-negotiables, communication tone).
  2. **Exact finance numbers** computed from their statements — never guessed.
     This is the "don't RAG numbers" rule: math in code, the LLM only narrates.
  3. (Optional) semantic recall from ingested documents via the vector store.

Structured facts + vector memory = "hybrid memory". The Mentor speaks in the
user's preferred tone (direct + numbers for Shravan; warmer for his wife).
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import List, Optional

from src.finance.analyze import analyze
from src.finance.categorize import categorize
from src.finance.safe_to_spend import safe_to_spend
from src.finance.statements import load_transactions
from src.providers.factory import ProviderFactory

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FOUNDATION_PATH = _REPO_ROOT / "brainstorms" / "life-os-foundation.md"
_DEFAULT_STATEMENT = _REPO_ROOT / "data" / "finance" / "sample_transactions.csv"

_TONE = {
    "me": "Direct, tough-love, specific numbers over vague encouragement. "
    "Tell them what they need to hear, not what they want to.",
    "wife": "Warm, encouraging, supportive, less blunt. Still honest, but gentle.",
}


@dataclass
class MentorResponse:
    answer: str
    facts_used: str = ""
    sources: List[str] = field(default_factory=list)


class Mentor:
    """The Life OS conversational mentor."""

    def __init__(self, person: str = "me"):
        self.llm = ProviderFactory.get_llm()
        self.person = person

    def _foundation(self) -> str:
        if _FOUNDATION_PATH.exists():
            return _FOUNDATION_PATH.read_text(encoding="utf-8")
        return "(No foundation document found.)"

    def _finance_facts(self, statement_path: Optional[Path]) -> str:
        """Computes EXACT finance numbers from a statement (never estimated)."""
        if not statement_path or not Path(statement_path).exists():
            return "(No statement loaded — no exact finance numbers available.)"
        txns = categorize(load_transactions(statement_path))
        if not txns:
            return "(Statement had no readable transactions.)"
        summary = analyze(txns)
        as_of = max(t.date for t in txns)  # latest day we have data for
        sts = safe_to_spend(txns, as_of)

        top = ", ".join(
            f"{cat} ${amt:,.0f}" for cat, amt in list(summary.spend_by_category.items())[:3]
        )
        return (
            f"Period analyzed up to {as_of}.\n"
            f"- Total income: ${summary.total_income:,.2f}\n"
            f"- Total spend: ${summary.total_spend:,.2f}\n"
            f"- Net saved: ${summary.net:,.2f} (savings rate {summary.savings_rate}%)\n"
            f"- Top spending: {top}\n"
            f"- Safe-to-spend for the rest of {sts.period}: "
            f"${sts.per_day:,.2f}/day ({sts.days_left} days left)"
        )

    def ask(
        self,
        question: str,
        statement_path: Optional[Path] = _DEFAULT_STATEMENT,
    ) -> MentorResponse:
        """Answers a question grounded in the user's foundation + exact finances."""
        foundation = self._foundation()
        facts = self._finance_facts(statement_path)
        tone = _TONE.get(self.person, _TONE["me"])

        prompt = (
            f"You are {self.person}'s personal finance Mentor inside their private Life "
            f"OS. Answer the question grounded ONLY in the facts below. Use specific "
            f"numbers from the EXACT FINANCE section — never invent or alter a number. "
            f"If the facts don't contain the answer, say so honestly.\n"
            f"TONE: {tone}\n\n"
            f"--- WHO THEY ARE & THEIR VALUES ---\n{foundation}\n\n"
            f"--- EXACT FINANCE NUMBERS (computed; do not change) ---\n{facts}\n\n"
            f"--- QUESTION ---\n{question}\n\n"
            f"Answer in a few tight sentences."
        )
        answer = self.llm.generate(prompt, temperature=0.3, max_tokens=2048).strip()
        return MentorResponse(answer=answer, facts_used=facts)


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description="Ask the Life OS Mentor a question.")
    parser.add_argument("question", help="Your question about your money/life")
    parser.add_argument("--person", default="me", choices=["me", "wife"])
    parser.add_argument("--statement", default=str(_DEFAULT_STATEMENT))
    args = parser.parse_args()

    resp = Mentor(person=args.person).ask(args.question, Path(args.statement))
    print("\n" + "=" * 60)
    print("  LIFE OS MENTOR")
    print("=" * 60)
    print(f"  Q: {args.question}\n")
    print(resp.answer)
    print("\n" + "-" * 60)
    print("Grounded on these exact facts:")
    print(resp.facts_used)
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
