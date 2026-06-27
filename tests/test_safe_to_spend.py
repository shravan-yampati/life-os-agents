"""Tests for the safe-to-spend computation — exact Decimal math."""

from datetime import date
from decimal import Decimal
from pathlib import Path

from src.finance.categorize import categorize
from src.finance.safe_to_spend import safe_to_spend
from src.finance.statements import Transaction, load_statement

# Resolve relative to the repo root so the test passes regardless of cwd.
SAMPLE_CSV = str(
    Path(__file__).resolve().parent.parent / "data" / "finance" / "sample_transactions.csv"
)


def _txn(d, desc, amt, cat):
    return Transaction(d, desc, Decimal(amt), cat)


def test_basic_safe_to_spend():
    # April: rent 1500 (fixed). May: income 3000, rent already paid 1500,
    # discretionary spent 200. As of May 15 (a 31-day month => 17 days left).
    txns = [
        _txn(date(2026, 4, 2), "RENT", "-1500.00", "Housing"),
        _txn(date(2026, 5, 1), "PAYROLL", "3000.00", "Income"),
        _txn(date(2026, 5, 2), "RENT", "-1500.00", "Housing"),
        _txn(date(2026, 5, 10), "GROCERIES", "-200.00", "Groceries"),
    ]
    s = safe_to_spend(txns, date(2026, 5, 15), savings_goal=Decimal("500"))
    assert s.days_left == 17
    assert s.income_this_period == Decimal("3000.00")
    assert s.spent_so_far == Decimal("1700.00")        # rent + groceries
    assert s.remaining_fixed_bills == Decimal("0.00")  # rent already paid this month
    # 3000 - 0 - 500 - 1700 = 800 free; 800 / 17
    assert s.safe_total == Decimal("800.00")
    assert s.per_day == Decimal("47.06")


def test_remaining_fixed_bill_not_yet_paid():
    # Rent paid in April but NOT yet in May as of May 1 -> counts as upcoming.
    txns = [
        _txn(date(2026, 4, 2), "RENT", "-1500.00", "Housing"),
        _txn(date(2026, 5, 1), "PAYROLL", "3000.00", "Income"),
    ]
    s = safe_to_spend(txns, date(2026, 5, 1), savings_goal=Decimal("0"))
    assert s.remaining_fixed_bills == Decimal("1500.00")
    # 3000 - 1500 - 0 - 0 = 1500 over 31 days
    assert s.safe_total == Decimal("1500.00")


def test_savings_transfers_excluded_from_spend():
    txns = [
        _txn(date(2026, 5, 1), "PAYROLL", "2000.00", "Income"),
        _txn(date(2026, 5, 3), "TO VANGUARD", "-500.00", "Savings/Transfers"),
    ]
    s = safe_to_spend(txns, date(2026, 5, 31), savings_goal=Decimal("0"))
    assert s.spent_so_far == Decimal("0.00")   # moving to savings isn't spending
    assert s.safe_total == Decimal("2000.00")


def test_overspend_produces_warning():
    txns = [
        _txn(date(2026, 5, 1), "PAYROLL", "1000.00", "Income"),
        _txn(date(2026, 5, 5), "SHOPPING", "-1500.00", "Shopping"),
    ]
    s = safe_to_spend(txns, date(2026, 5, 20))
    assert s.safe_total < 0
    assert any("Over budget" in n for n in s.notes)


def test_on_sample_statement():
    txns = categorize(load_statement(SAMPLE_CSV))
    s = safe_to_spend(txns, date(2026, 5, 20), savings_goal=Decimal("1000"))
    assert s.income_this_period == Decimal("5200.00")
    assert s.period == "2026-05"
    assert isinstance(s.per_day, Decimal)
