"""Tests for the finance vertical: parse, categorize, exact analysis."""

from decimal import Decimal
from pathlib import Path

import pytest

from src.finance.analyze import analyze
from src.finance.categorize import categorize, categorize_description
from src.finance.statements import Transaction, load_statement

# Resolve relative to the repo root so the test passes regardless of cwd.
SAMPLE_CSV = str(
    Path(__file__).resolve().parent.parent / "data" / "finance" / "sample_transactions.csv"
)

CSV_SIGNED = """Date,Description,Amount
2026-04-01,ACME PAYROLL DIRECT DEPOSIT,5000.00
2026-04-02,GREENVIEW RENT,-1500.00
2026-04-03,WHOLE FOODS MARKET,-100.00
2026-04-04,TRANSFER TO VANGUARD SAVINGS,-400.00
"""

CSV_SPLIT = """Posted Date,Memo,Debit,Credit
04/01/2026,ACME PAYROLL,,5000.00
04/02/2026,RENT PAYMENT,1500.00,
"""


def _write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_parse_signed_amount(tmp_path):
    txns = load_statement(_write(tmp_path, "s.csv", CSV_SIGNED))
    assert len(txns) == 4
    assert txns[0].amount == Decimal("5000.00")
    assert txns[0].is_income
    assert txns[1].amount == Decimal("-1500.00")
    assert txns[1].is_spend


def test_parse_debit_credit_layout(tmp_path):
    txns = load_statement(_write(tmp_path, "s.csv", CSV_SPLIT))
    assert txns[0].amount == Decimal("5000.00")   # credit -> positive
    assert txns[1].amount == Decimal("-1500.00")  # debit -> negative


def test_money_uses_decimal_not_float(tmp_path):
    txns = load_statement(_write(tmp_path, "s.csv", CSV_SIGNED))
    assert all(isinstance(t.amount, Decimal) for t in txns)


def test_accounting_negatives_and_currency_symbols(tmp_path):
    csv = "Date,Description,Amount\n2026-04-01,FEE,\"($1,234.56)\"\n"
    txns = load_statement(_write(tmp_path, "s.csv", csv))
    assert txns[0].amount == Decimal("-1234.56")


def test_categorize_keywords():
    assert categorize_description("STARBUCKS STORE #1123") == "Dining"
    assert categorize_description("GREENVIEW APARTMENTS RENT") == "Housing"
    assert categorize_description("SHELL OIL GAS STATION") == "Transport"
    assert categorize_description("ACME PAYROLL DIRECT DEPOSIT") == "Income"
    assert categorize_description("MYSTERY VENDOR XYZ") == "Other"


def test_analysis_exact_math(tmp_path):
    txns = categorize(load_statement(_write(tmp_path, "s.csv", CSV_SIGNED)))
    s = analyze(txns)
    # Income 5000; spend excludes the 400 savings transfer -> 1600 consumed
    assert s.total_income == Decimal("5000.00")
    assert s.total_spend == Decimal("1600.00")
    assert s.net == Decimal("3400.00")
    assert s.savings_rate == Decimal("68.00")
    assert s.spend_by_category["Housing"] == Decimal("1500.00")
    assert "Savings/Transfers" not in s.spend_by_category


def test_savings_rate_zero_without_income():
    txns = [
        Transaction(__import__("datetime").date(2026, 4, 1), "RENT", Decimal("-100"),
                    "Housing")
    ]
    assert analyze(txns).savings_rate == Decimal("0")


def test_sample_statement_loads():
    txns = load_statement(SAMPLE_CSV)
    assert len(txns) > 30
    s = analyze(categorize(txns))
    assert s.total_income == Decimal("10400.00")  # two 5200 paychecks
    assert len(s.by_month) == 2
