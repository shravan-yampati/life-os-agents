"""Tests for the Daily Guide agent."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.config import settings
from src.agents.daily_guide import build_flags, generate_daily_message, DailyMessage
from src.finance.analyze import FinancialSummary
from src.finance.safe_to_spend import SafeToSpend
from src.finance.statements import Transaction


@pytest.fixture
def offline_mock(monkeypatch):
    """Forces the LLM provider to 'local' for offline tests."""
    monkeypatch.setattr(settings, "CLOUD_PROVIDER", "local")


def test_build_flags():
    summary = FinancialSummary(
        total_income=Decimal("5000"),
        total_spend=Decimal("2000"),
        net=Decimal("3000"),
        savings_rate=Decimal("60"),
        spend_by_category={"Dining": Decimal("500"), "Groceries": Decimal("1500")},
        top_merchants=[],
        transaction_count=10
    )
    sts = SafeToSpend(
        period="2026-06",
        as_of=date(2026, 6, 15),
        days_left=16,
        income_this_period=Decimal("5000"),
        spent_so_far=Decimal("2000"),
        remaining_fixed_bills=Decimal("1000"),
        savings_goal=Decimal("500"),
        safe_total=Decimal("1500"),
        per_day=Decimal("93.75")
    )
    txns = []  # not used by build_flags directly right now
    
    flags = build_flags(txns, summary, sts)
    
    # Assert contents
    assert any("Safe-to-spend: $93.75/day" in f for f in flags)
    assert any("Dining makes up 25.0% of total spend ($500.00)" in f for f in flags)
    assert any("Remaining fixed bills estimated at: $1,000.00" in f for f in flags)
    assert any("Savings pace: currently saved $3,000.00 (Savings rate: 60%)" in f for f in flags)
    assert not any("Over budget" in f for f in flags)


def test_build_flags_over_budget():
    summary = FinancialSummary(
        total_income=Decimal("1000"),
        total_spend=Decimal("2000"),
        net=Decimal("-1000"),
        savings_rate=Decimal("0"),
        spend_by_category={"Dining": Decimal("2000")},
        top_merchants=[],
        transaction_count=5
    )
    sts = SafeToSpend(
        period="2026-06",
        as_of=date(2026, 6, 15),
        days_left=16,
        income_this_period=Decimal("1000"),
        spent_so_far=Decimal("2000"),
        remaining_fixed_bills=Decimal("0"),
        savings_goal=Decimal("0"),
        safe_total=Decimal("-1000"),
        per_day=Decimal("0")
    )
    
    flags = build_flags([], summary, sts)
    assert any("Warning: Over budget! Safe total is negative." in f for f in flags)


def test_generate_daily_message_offline(offline_mock, tmp_path):
    """Tests the full generation using the local mock provider."""
    # Write a dummy foundation file
    foundation = tmp_path / "life-os-foundation.md"
    foundation.write_text("Test foundation.")
    
    # Create a minimal valid statement.
    statement = tmp_path / "statement.csv"
    statement.write_text("Date,Description,Amount\n2026-06-10,Test Income,1000.00\n")
    
    msg = generate_daily_message(
        person="me",
        statement_path=statement,
        as_of=date(2026, 6, 15),
        foundation_path=foundation
    )
    
    assert isinstance(msg, DailyMessage)
    assert msg.person == "me"
    assert "Safe-to-spend" in msg.facts
    assert len(msg.message) > 0 
