"""Tests for PDF statement ingestion.

The line parser is tested directly on representative text (deterministic, no
PDF needed). One integration test generates a real PDF with reportlab, extracts
it with pypdf, and verifies the round-trip — proving actual PDF text extraction
works, not just the regex.
"""

from datetime import date
from decimal import Decimal

import pytest

from src.finance.categorize import categorize
from src.finance.pdf_loader import parse_statement_line, parse_statement_text
from src.finance.statements import load_transactions


def test_parse_basic_line_is_spend():
    txn = parse_statement_line("04/15/2026  WHOLE FOODS MARKET  $142.36")
    assert txn is not None
    assert txn.date == date(2026, 4, 15)
    assert txn.description == "WHOLE FOODS MARKET"
    assert txn.amount == Decimal("-142.36")  # bare amount -> spend


def test_parse_credit_marker_is_income():
    txn = parse_statement_line("2026-04-01  ACME PAYROLL DEPOSIT  5,200.00 CR")
    assert txn.amount == Decimal("5200.00")


def test_parse_debit_marker_is_spend():
    txn = parse_statement_line("2026-04-02  RENT PAYMENT  1,850.00 DR")
    assert txn.amount == Decimal("-1850.00")


def test_parse_parentheses_negative():
    txn = parse_statement_line("Apr 03, 2026  SERVICE FEE  ($35.00)")
    assert txn.date == date(2026, 4, 3)
    assert txn.amount == Decimal("-35.00")


def test_non_transaction_lines_ignored():
    assert parse_statement_line("STATEMENT PERIOD: APRIL 2026") is None
    assert parse_statement_line("Page 1 of 3") is None
    assert parse_statement_line("") is None


def test_parse_multiline_text_sorts_by_date():
    text = """Your Bank Statement
Account: ****1234

05/02/2026  GREENVIEW RENT  1,850.00 DR
04/01/2026  ACME PAYROLL  5,200.00 CR
04/05/2026  STARBUCKS  $8.75

Closing balance: 3,341.25
"""
    txns = parse_statement_text(text)
    assert len(txns) == 3
    assert [t.date.day for t in txns] == [1, 5, 2]  # sorted
    assert txns[0].amount == Decimal("5200.00")


def test_pdf_round_trip(tmp_path):
    reportlab = pytest.importorskip("reportlab")
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    pdf_path = tmp_path / "statement.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    text = c.beginText(40, 720)
    for line in [
        "MONTHLY STATEMENT - ACME BANK",
        "Account ****9999",
        "",
        "04/01/2026  ACME CORP PAYROLL  5,200.00 CR",
        "04/02/2026  GREENVIEW APARTMENTS RENT  1,850.00 DR",
        "04/05/2026  STARBUCKS STORE 1123  8.75",
        "04/12/2026  TRADER JOES  88.20",
        "End of statement",
    ]:
        text.textLine(line)
    c.drawText(text)
    c.save()

    txns = categorize(load_transactions(pdf_path))
    assert len(txns) == 4
    income = [t for t in txns if t.is_income]
    assert len(income) == 1
    assert income[0].amount == Decimal("5200.00")
    rent = next(t for t in txns if "RENT" in t.description)
    assert rent.amount == Decimal("-1850.00")
    assert rent.category == "Housing"


def test_dispatcher_rejects_unknown_format(tmp_path):
    p = tmp_path / "statement.txt"
    p.write_text("nope", encoding="utf-8")
    with pytest.raises(ValueError):
        load_transactions(p)
