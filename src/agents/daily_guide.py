"""Daily Guide — proactive daily finance message."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import List, Optional

from src.finance.analyze import FinancialSummary, analyze
from src.finance.categorize import categorize
from src.finance.safe_to_spend import SafeToSpend, safe_to_spend
from src.finance.statements import load_transactions, Transaction
from src.providers.factory import ProviderFactory

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FOUNDATION_PATH = _REPO_ROOT / "brainstorms" / "life-os-foundation.md"
_DEFAULT_STATEMENT = _REPO_ROOT / "data" / "finance" / "sample_transactions.csv"

_TONE = {
    "me": "Direct, tough-love, specific numbers over vague encouragement. Tell them what they need to hear, not what they want to.",
    "wife": "Warm, encouraging, supportive, less blunt. Still honest, but gentle.",
}


@dataclass
class DailyMessage:
    person: str
    date: date
    facts: str
    flags: List[str]
    message: str


def build_flags(txns: List[Transaction], summary: FinancialSummary, sts: SafeToSpend) -> List[str]:
    """Computes exact, numerical flags from the financial data."""
    flags = []
    flags.append(f"Safe-to-spend: ${sts.per_day:,.2f}/day for the remaining {sts.days_left} days of {sts.period}.")
    
    if summary.total_spend > 0:
        dining_spend = summary.spend_by_category.get("Dining", Decimal("0"))
        dining_pct = (dining_spend / summary.total_spend * 100).quantize(Decimal("0.1"))
        flags.append(f"Dining makes up {dining_pct}% of total spend (${dining_spend:,.2f}).")
    else:
        flags.append("Dining makes up 0.0% of total spend ($0.00).")
    
    flags.append(f"Remaining fixed bills estimated at: ${sts.remaining_fixed_bills:,.2f}.")
    flags.append(f"Savings pace: currently saved ${summary.net:,.2f} (Savings rate: {summary.savings_rate}%).")
    
    if sts.safe_total < 0:
        flags.append("Warning: Over budget! Safe total is negative.")

    return flags


def generate_daily_message(
    person: str = "me", 
    statement_path: Optional[Path] = _DEFAULT_STATEMENT, 
    as_of: Optional[date] = None, 
    foundation_path: Optional[Path] = _FOUNDATION_PATH
) -> DailyMessage:
    """Generates the daily guide message by orchestrating data + LLM."""
    if as_of is None:
        as_of = date.today()
        
    llm = ProviderFactory.get_llm()
    
    if foundation_path and Path(foundation_path).exists():
        foundation = Path(foundation_path).read_text(encoding="utf-8")
    else:
        foundation = "(No foundation document found.)"

    if statement_path and Path(statement_path).exists():
        txns = categorize(load_transactions(statement_path))
        if not txns:
            summary = FinancialSummary(Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), {}, [], transaction_count=0)
            sts = SafeToSpend(as_of.strftime("%Y-%m"), as_of, 1, Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"))
            txns = []
        else:
            summary = analyze(txns)
            as_of_actual = max(t.date for t in txns)
            sts = safe_to_spend(txns, as_of_actual)
    else:
        summary = FinancialSummary(Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), {}, [], transaction_count=0)
        sts = SafeToSpend(as_of.strftime("%Y-%m"), as_of, 1, Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"))
        txns = []

    flags = build_flags(txns, summary, sts)
    facts = "\n".join(f"- {f}" for f in flags)
    
    tone = _TONE.get(person, _TONE["me"])
    prompt = (
        f"You are {person}'s personal Life OS daily guide. Write a brief, proactive daily message (≤6 sentences).\n"
        f"Base it ENTIRELY on the exact facts/flags computed below. NEVER invent or alter a number.\n"
        f"TONE: {tone}\n\n"
        f"--- WHO THEY ARE & THEIR VALUES ---\n{foundation}\n\n"
        f"--- EXACT FINANCE FACTS FOR TODAY ---\n{facts}\n"
    )
    
    answer = llm.generate(prompt, temperature=0.3, max_tokens=2048).strip()
    
    return DailyMessage(
        person=person,
        date=as_of,
        facts=facts,
        flags=flags,
        message=answer
    )


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
        
    parser = argparse.ArgumentParser(description="Generate the Daily Guide message.")
    parser.add_argument("--person", default="me", choices=["me", "wife"])
    parser.add_argument("--statement", default=str(_DEFAULT_STATEMENT))
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print(f"  LIFE OS DAILY GUIDE (for: {args.person})")
    print("=" * 60)
    
    try:
        msg = generate_daily_message(person=args.person, statement_path=Path(args.statement))
        print("\nCOMPUTED FACTS:")
        print(msg.facts)
        print("\n" + "-" * 60)
        print("MESSAGE:\n")
        print(msg.message)
    except Exception as e:
        print(f"\nError generating daily guide: {e}")
        
    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    main()
