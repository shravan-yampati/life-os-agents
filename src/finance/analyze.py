"""Exact financial computations over structured transactions.

Every number here is computed with Decimal arithmetic — these are facts, not
estimates. This is the "structured" half of hybrid memory: the LLM will later
read these exact figures rather than guessing them from retrieved text.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Tuple

from src.finance.statements import Transaction

_CENTS = Decimal("0.01")


def _q(value: Decimal) -> Decimal:
    """Quantizes to cents."""
    return value.quantize(_CENTS)


@dataclass
class FinancialSummary:
    """Exact roll-up of a set of transactions."""

    total_income: Decimal
    total_spend: Decimal  # positive magnitude of money out
    net: Decimal
    savings_rate: Decimal  # percent of income kept, 0 if no income
    spend_by_category: Dict[str, Decimal]
    top_merchants: List[Tuple[str, Decimal]]
    by_month: Dict[str, Decimal] = field(default_factory=dict)  # month -> net
    transaction_count: int = 0


def analyze(transactions: List[Transaction]) -> FinancialSummary:
    """Computes an exact financial summary from categorized transactions.

    Income is the sum of positive amounts; spend is the magnitude of negative
    amounts excluding internal Savings/Transfers (moving money to savings is
    not consumption). Savings rate = net / income.

    Args:
        transactions: Categorized transactions.

    Returns:
        A FinancialSummary with exact Decimal figures.
    """
    total_income = Decimal("0")
    total_spend = Decimal("0")
    spend_by_category: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    merchant_spend: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    by_month: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    for txn in transactions:
        month_key = txn.date.strftime("%Y-%m")
        by_month[month_key] += txn.amount
        if txn.is_income:
            total_income += txn.amount
        elif txn.is_spend:
            magnitude = -txn.amount
            if txn.category != "Savings/Transfers":
                total_spend += magnitude
                spend_by_category[txn.category] += magnitude
                merchant = txn.description or "(unknown)"
                merchant_spend[merchant] += magnitude

    net = total_income - total_spend
    savings_rate = (
        _q(net / total_income * Decimal("100")) if total_income > 0 else Decimal("0")
    )

    top_merchants = sorted(
        ((m, _q(v)) for m, v in merchant_spend.items()),
        key=lambda kv: kv[1],
        reverse=True,
    )[:10]

    return FinancialSummary(
        total_income=_q(total_income),
        total_spend=_q(total_spend),
        net=_q(net),
        savings_rate=savings_rate,
        spend_by_category={
            k: _q(v)
            for k, v in sorted(
                spend_by_category.items(), key=lambda kv: kv[1], reverse=True
            )
        },
        top_merchants=top_merchants,
        by_month={k: _q(by_month[k]) for k in sorted(by_month)},
        transaction_count=len(transactions),
    )
