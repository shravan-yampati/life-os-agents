"""Parse text-based PDF bank statements into structured transactions.

Real-world note: this handles *text* PDFs (the kind banks generate as
downloads), not scanned images. Scanned statements need OCR (e.g. Tesseract /
Cloud Document AI) — that's a later upgrade flagged in the design.

Extraction is best-effort: bank layouts vary wildly, so the line parser is
tolerant and skips anything it can't confidently read. ALWAYS sanity-check the
result with the `summary` command against the statement's printed totals.

Sign convention when parsing a single amount column:
- parentheses `(45.00)`, a leading `-`, or trailing `DR` -> spending (negative)
- a leading `+` or trailing `CR` -> income (positive)
- a bare amount -> treated as spending (statements are purchase-heavy); verify.
"""

import re
from pathlib import Path
from typing import List, Optional

from src.finance.statements import Transaction, _clean_money, _parse_date
from src.ingestion.loader import extract_text_from_pdf

# A date token at the start of a transaction line. Covers the common formats
# banks print: 04/15/2026, 4/15/26, 2026-04-15, "Apr 15, 2026", "15 Apr 2026".
_DATE_TOKEN = (
    r"(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    r"|\d{4}-\d{2}-\d{2}"
    r"|[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{2,4}"
    r"|\d{1,2}\s+[A-Za-z]{3,9}\.?\s+\d{2,4})"
)

# An amount token at the end of the line, with optional $ , sign, parens, CR/DR.
_AMOUNT_TOKEN = r"[-+(]?\$?\d[\d,]*\.\d{2}\)?(?:\s?(?:CR|DR|cr|dr))?"

_TXN_LINE = re.compile(
    rf"^\s*(?P<date>{_DATE_TOKEN})\s+(?P<desc>.+?)\s+(?P<amount>{_AMOUNT_TOKEN})\s*$"
)


def parse_statement_line(line: str) -> Optional[Transaction]:
    """Parses one statement line into a Transaction, or None if it isn't one.

    Args:
        line: A single line of extracted statement text.

    Returns:
        A Transaction (category left as default), or None if the line does not
        look like a dated transaction with an amount.
    """
    match = _TXN_LINE.match(line)
    if not match:
        return None

    try:
        txn_date = _parse_date(match.group("date"))
    except ValueError:
        return None

    raw_amount = match.group("amount").strip()
    upper = raw_amount.upper()
    is_credit = upper.endswith("CR")
    is_debit = upper.endswith("DR")
    # Strip the CR/DR marker before numeric parsing.
    numeric = re.sub(r"(?i)\s?(?:CR|DR)$", "", raw_amount)

    value = _clean_money(numeric)
    if value is None:
        return None

    magnitude = abs(value)
    explicitly_negative = value < 0 or numeric.strip().startswith("(")
    explicitly_positive = numeric.strip().startswith("+")

    if is_credit or explicitly_positive:
        amount = magnitude            # income / money in
    elif is_debit or explicitly_negative:
        amount = -magnitude           # spending / money out
    else:
        amount = -magnitude           # bare amount: assume spend (documented)

    description = match.group("desc").strip()
    return Transaction(date=txn_date, description=description, amount=amount)


def parse_statement_text(text: str) -> List[Transaction]:
    """Parses extracted statement text into transactions, sorted by date."""
    transactions = [
        txn
        for line in text.splitlines()
        if (txn := parse_statement_line(line)) is not None
    ]
    transactions.sort(key=lambda t: t.date)
    return transactions


def load_pdf_statement(path: str | Path) -> List[Transaction]:
    """Extracts and parses a text-based PDF bank statement.

    Args:
        path: Path to the PDF.

    Returns:
        Transactions sorted by date (spending negative, income positive).
    """
    return parse_statement_text(extract_text_from_pdf(path))
