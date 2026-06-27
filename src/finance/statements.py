"""Load and normalize bank statement exports into structured transactions.

Most banks let you export a statement as CSV. Column names vary, so the loader
maps common header variants to a canonical schema. Money is parsed as Decimal,
never float — floats introduce rounding error that is unacceptable for money
(0.1 + 0.2 != 0.3). This is the correct, interview-grade way to handle currency.
"""

import csv
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import List, Optional

# Canonical column -> list of accepted header variants (lowercased)
_HEADER_ALIASES = {
    "date": ["date", "transaction date", "posted date", "posting date", "trans date"],
    "description": ["description", "name", "memo", "details", "payee", "narrative"],
    "amount": ["amount", "amount (usd)", "transaction amount"],
    "debit": ["debit", "withdrawal", "withdrawals", "money out"],
    "credit": ["credit", "deposit", "deposits", "money in"],
}

_DATE_FORMATS = [
    "%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y", "%d-%m-%Y", "%m-%d-%Y",
    "%b %d, %Y", "%d %b %Y",
]


@dataclass(frozen=True)
class Transaction:
    """A single normalized transaction.

    Attributes:
        date: Date the transaction posted.
        description: Raw merchant/description text from the statement.
        amount: Signed Decimal. Positive = money in (income/credit),
            negative = money out (spending/debit).
        category: Spending category, assigned by the categorizer.
    """

    date: date
    description: str
    amount: Decimal
    category: str = "Uncategorized"

    @property
    def is_income(self) -> bool:
        return self.amount > 0

    @property
    def is_spend(self) -> bool:
        return self.amount < 0


def _clean_money(raw: str) -> Optional[Decimal]:
    """Parses a money string like '$1,234.56' or '(45.00)' into a Decimal."""
    if raw is None:
        return None
    text = raw.strip().replace(",", "").replace("$", "").replace("USD", "").strip()
    if not text:
        return None
    negative = False
    if text.startswith("(") and text.endswith(")"):  # accounting negatives
        negative = True
        text = text[1:-1]
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return -value if negative else value


def _parse_date(raw: str) -> date:
    text = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {raw!r}")


def _build_header_map(fieldnames: List[str]) -> dict:
    """Maps the CSV's actual headers to canonical names."""
    resolved = {}
    lowered = {name.lower().strip(): name for name in fieldnames}
    for canonical, variants in _HEADER_ALIASES.items():
        for variant in variants:
            if variant in lowered:
                resolved[canonical] = lowered[variant]
                break
    return resolved


def load_statement(path: str | Path) -> List[Transaction]:
    """Loads a bank CSV export into a list of normalized Transactions.

    Handles two common layouts: a single signed ``amount`` column, or
    separate ``debit``/``credit`` columns. Rows that cannot be parsed
    (e.g. blank lines, headers repeated mid-file) are skipped.

    Args:
        path: Path to the CSV statement export.

    Returns:
        Transactions sorted by date. Spending is negative, income positive.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If no date or amount columns can be identified.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Statement not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise ValueError("CSV has no header row.")
        cols = _build_header_map(reader.fieldnames)

        if "date" not in cols:
            raise ValueError(f"No date column found in {reader.fieldnames}")
        has_amount = "amount" in cols
        has_split = "debit" in cols or "credit" in cols
        if not (has_amount or has_split):
            raise ValueError(f"No amount/debit/credit column in {reader.fieldnames}")

        transactions: List[Transaction] = []
        for row in reader:
            try:
                txn_date = _parse_date(row[cols["date"]])
            except (ValueError, KeyError, TypeError):
                continue

            amount = _row_amount(row, cols, has_amount)
            if amount is None:
                continue

            description = (row.get(cols.get("description", ""), "") or "").strip()
            transactions.append(
                Transaction(date=txn_date, description=description, amount=amount)
            )

    transactions.sort(key=lambda t: t.date)
    return transactions


def load_transactions(path: str | Path) -> List[Transaction]:
    """Loads a bank statement of any supported format into transactions.

    Dispatches by file extension: ``.csv`` uses the CSV loader, ``.pdf`` uses
    the text-PDF loader. This is the entry point callers should use so the
    rest of the pipeline is format-agnostic.

    Args:
        path: Path to a .csv or .pdf bank statement export.

    Returns:
        Transactions sorted by date.

    Raises:
        ValueError: If the file extension is not supported.
    """
    suffix = Path(path).suffix.lower()
    if suffix == ".csv":
        return load_statement(path)
    if suffix == ".pdf":
        from src.finance.pdf_loader import load_pdf_statement  # lazy: avoids cycle

        return load_pdf_statement(path)
    raise ValueError(f"Unsupported statement format '{suffix}'. Use .csv or .pdf.")


def _row_amount(row: dict, cols: dict, has_amount: bool) -> Optional[Decimal]:
    """Resolves a signed amount from either a single column or debit/credit."""
    if has_amount:
        return _clean_money(row.get(cols["amount"], ""))
    debit = _clean_money(row.get(cols.get("debit", ""), "")) if "debit" in cols else None
    credit = _clean_money(row.get(cols.get("credit", ""), "")) if "credit" in cols else None
    if debit:
        return -abs(debit)
    if credit:
        return abs(credit)
    return None
