"""Safe-to-spend: the headline number of the finance vertical.

Computed entirely in code with Decimal arithmetic — never by the LLM. The LLM
will later *narrate* this figure in a daily message, but the number itself is a
fact the user can trust.

Formula (from the Phase 1 design):
    safe_total = income_this_period
               - remaining_fixed_bills      (bills expected but not yet paid)
               - savings_goal               (what you intend to keep)
               - spent_so_far               (all consumption already this period)
    per_day    = safe_total / days_left
"""

import calendar
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Dict, List, Set

from src.finance.statements import Transaction

_CENTS = Decimal("0.01")

# Categories that are recurring, non-discretionary monthly bills.
DEFAULT_FIXED_CATEGORIES: Set[str] = {"Housing", "Utilities", "Subscriptions"}
_NON_CONSUMPTION = {"Savings/Transfers", "Income"}


def _q(value: Decimal) -> Decimal:
    return value.quantize(_CENTS)


@dataclass
class SafeToSpend:
    """Result of a safe-to-spend computation for one period (a calendar month)."""

    period: str                      # e.g. "2026-05"
    as_of: date
    days_left: int                   # including as_of itself
    income_this_period: Decimal
    spent_so_far: Decimal            # all consumption this period (fixed + discretionary)
    remaining_fixed_bills: Decimal   # estimated bills not yet paid this period
    savings_goal: Decimal
    safe_total: Decimal              # money free to spend over the rest of the period
    per_day: Decimal                 # safe_total / days_left
    notes: List[str] = field(default_factory=list)


def estimate_remaining_fixed(
    transactions: List[Transaction],
    as_of: date,
    fixed_categories: Set[str],
) -> Decimal:
    """Estimates fixed bills expected this period but not yet paid.

    Heuristic: for each fixed category, take what was paid in the *previous*
    month as the expected monthly amount, then subtract what has already been
    paid this month. The remainder (floored at zero) is what's still coming.

    Args:
        transactions: All known transactions (categorized).
        as_of: The reference date defining "this period".
        fixed_categories: Categories treated as recurring fixed bills.

    Returns:
        Estimated remaining fixed spend for the rest of the period (Decimal).
    """
    this_key = as_of.strftime("%Y-%m")
    prev_year, prev_month = (as_of.year, as_of.month - 1) if as_of.month > 1 else (as_of.year - 1, 12)
    prev_key = f"{prev_year:04d}-{prev_month:02d}"

    expected: Dict[str, Decimal] = {c: Decimal("0") for c in fixed_categories}
    paid_this_month: Dict[str, Decimal] = {c: Decimal("0") for c in fixed_categories}

    for txn in transactions:
        if not txn.is_spend or txn.category not in fixed_categories:
            continue
        key = txn.date.strftime("%Y-%m")
        magnitude = -txn.amount
        if key == prev_key:
            expected[txn.category] += magnitude
        elif key == this_key and txn.date <= as_of:
            paid_this_month[txn.category] += magnitude

    remaining = Decimal("0")
    for category in fixed_categories:
        still_due = expected[category] - paid_this_month[category]
        if still_due > 0:
            remaining += still_due
    return remaining


def safe_to_spend(
    transactions: List[Transaction],
    as_of: date,
    savings_goal: Decimal = Decimal("0"),
    fixed_categories: Set[str] = DEFAULT_FIXED_CATEGORIES,
) -> SafeToSpend:
    """Computes the safe-to-spend figure for the period containing ``as_of``.

    Args:
        transactions: Categorized transactions (any history; only the relevant
            period and the prior month are used).
        as_of: The day to compute for. Days left counts from this day inclusive.
        savings_goal: Amount to set aside this period before spending.
        fixed_categories: Categories treated as recurring fixed bills.

    Returns:
        A SafeToSpend with exact figures and explanatory notes.
    """
    period = as_of.strftime("%Y-%m")
    days_in_month = calendar.monthrange(as_of.year, as_of.month)[1]
    days_left = days_in_month - as_of.day + 1

    income = Decimal("0")
    spent_so_far = Decimal("0")
    for txn in transactions:
        if txn.date.strftime("%Y-%m") != period or txn.date > as_of:
            continue
        if txn.is_income:
            income += txn.amount
        elif txn.is_spend and txn.category not in _NON_CONSUMPTION:
            spent_so_far += -txn.amount

    remaining_fixed = estimate_remaining_fixed(transactions, as_of, fixed_categories)
    safe_total = income - remaining_fixed - savings_goal - spent_so_far
    per_day = _q(safe_total / days_left) if days_left > 0 else Decimal("0")

    notes: List[str] = []
    if income == 0:
        notes.append("No income recorded yet this period — figure may be incomplete.")
    if remaining_fixed == 0:
        notes.append("No upcoming fixed bills estimated (no prior-month history?).")
    if safe_total < 0:
        notes.append("Over budget: committed spending exceeds income minus savings.")

    return SafeToSpend(
        period=period,
        as_of=as_of,
        days_left=days_left,
        income_this_period=_q(income),
        spent_so_far=_q(spent_so_far),
        remaining_fixed_bills=_q(remaining_fixed),
        savings_goal=_q(savings_goal),
        safe_total=_q(safe_total),
        per_day=per_day,
        notes=notes,
    )
