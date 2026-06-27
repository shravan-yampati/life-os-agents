"""Finance CLI — the first Life OS vertical.

Usage (from rag-lab/):
    python -m src.serving.finance_cli summary data/finance/sample_transactions.csv

Drop your own bank CSV export in place of the sample. Everything runs locally;
no data leaves your machine.
"""

import argparse
from datetime import date, datetime
from decimal import Decimal

from src.finance.analyze import FinancialSummary, analyze
from src.finance.categorize import categorize
from src.finance.safe_to_spend import SafeToSpend, safe_to_spend
from src.finance.statements import load_transactions


def _money(value: Decimal) -> str:
    return f"${value:,.2f}"


def _print_summary(s: FinancialSummary) -> None:
    print("\n" + "=" * 48)
    print("  FINANCIAL SUMMARY")
    print("=" * 48)
    print(f"  Transactions analyzed : {s.transaction_count}")
    print(f"  Total income          : {_money(s.total_income)}")
    print(f"  Total spend           : {_money(s.total_spend)}")
    print(f"  Net (saved)           : {_money(s.net)}")
    print(f"  Savings rate          : {s.savings_rate}% of income")

    print("\n  SPEND BY CATEGORY")
    print("  " + "-" * 32)
    for category, amount in s.spend_by_category.items():
        share = (amount / s.total_spend * 100) if s.total_spend else Decimal("0")
        print(f"  {category:<20} {_money(amount):>12}  ({share:.0f}%)")

    print("\n  TOP MERCHANTS")
    print("  " + "-" * 32)
    for merchant, amount in s.top_merchants[:5]:
        print(f"  {merchant[:24]:<24} {_money(amount):>12}")

    if len(s.by_month) > 1:
        print("\n  NET BY MONTH (income - spend)")
        print("  " + "-" * 32)
        for month, net in s.by_month.items():
            flag = "" if net >= 0 else "  <-- overspent"
            print(f"  {month}              {_money(net):>12}{flag}")
    print("=" * 48 + "\n")


def _print_safe(s: SafeToSpend) -> None:
    print("\n" + "=" * 48)
    print(f"  SAFE TO SPEND — {s.period} (as of {s.as_of})")
    print("=" * 48)
    print(f"  Income this period    : {_money(s.income_this_period)}")
    print(f"  - Remaining bills      : {_money(s.remaining_fixed_bills)}")
    print(f"  - Savings goal         : {_money(s.savings_goal)}")
    print(f"  - Spent so far         : {_money(s.spent_so_far)}")
    print("  " + "-" * 32)
    print(f"  Free to spend          : {_money(s.safe_total)}")
    print(f"  Days left              : {s.days_left}")
    print(f"\n  >> SAFE TO SPEND PER DAY: {_money(s.per_day)} <<")
    for note in s.notes:
        print(f"  ! {note}")
    print("=" * 48 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="finance", description="Personal finance analyzer (Life OS vertical 1)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    summ = sub.add_parser("summary", help="Summarize a bank statement (CSV or PDF)")
    summ.add_argument("path", help="Path to a bank statement export (.csv or .pdf)")

    safe = sub.add_parser("safe", help="Compute safe-to-spend per day")
    safe.add_argument("path", help="Path to a bank statement export (.csv or .pdf)")
    safe.add_argument("--as-of", help="Reference date YYYY-MM-DD (default: today)")
    safe.add_argument("--savings-goal", type=str, default="0",
                      help="Amount to set aside this period (default: 0)")

    args = parser.parse_args()

    if args.command == "summary":
        transactions = categorize(load_transactions(args.path))
        if not transactions:
            print("No transactions could be parsed from that file.")
            return
        _print_summary(analyze(transactions))
    elif args.command == "safe":
        transactions = categorize(load_transactions(args.path))
        if not transactions:
            print("No transactions could be parsed from that file.")
            return
        as_of = (
            datetime.strptime(args.as_of, "%Y-%m-%d").date()
            if args.as_of else date.today()
        )
        _print_safe(safe_to_spend(transactions, as_of, Decimal(args.savings_goal)))


if __name__ == "__main__":
    main()
