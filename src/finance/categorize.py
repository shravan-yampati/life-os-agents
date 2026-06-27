"""Automatic transaction categorization — no manual data entry.

A first-pass, rule-based categorizer: it matches keywords in the transaction
description to a spending category. This is deliberately simple and transparent
(you can see exactly why something was categorized). Later it can be upgraded to
an LLM classifier for the long tail, but rules handle the bulk cheaply and
deterministically — and cost/determinism matter.
"""

from dataclasses import replace
from typing import Dict, List

from src.finance.statements import Transaction

# Category -> substrings that imply it (checked case-insensitively, in order).
_RULES: Dict[str, List[str]] = {
    "Income": ["payroll", "salary", "direct deposit", "deposit from", "interest paid"],
    "Housing": ["rent", "mortgage", "landlord", "hoa", "property"],
    "Utilities": ["electric", "water", "gas company", "internet", "comcast",
                  "verizon", "at&t", "utility", "power"],
    "Groceries": ["grocery", "supermarket", "whole foods", "trader joe", "safeway",
                  "kroger", "aldi", "costco", "walmart", "h-e-b", "heb"],
    "Dining": ["restaurant", "cafe", "coffee", "starbucks", "mcdonald", "chipotle",
               "doordash", "uber eats", "grubhub", "pizza", "bar ", "diner"],
    "Transport": ["uber", "lyft", "shell", "chevron", "exxon", "gas station",
                  "fuel", "parking", "metro", "transit", "toll"],
    "Subscriptions": ["netflix", "spotify", "hulu", "disney+", "youtube premium",
                      "prime", "icloud", "adobe", "subscription", "patreon"],
    "Shopping": ["amazon", "target", "best buy", "ebay", "etsy", "store", "mall"],
    "Health": ["pharmacy", "cvs", "walgreens", "doctor", "clinic", "dental",
               "medical", "insurance", "gym", "fitness"],
    "Savings/Transfers": ["transfer", "savings", "investment", "vanguard",
                          "fidelity", "robinhood", "venmo", "zelle", "withdrawal"],
}


def categorize_description(description: str) -> str:
    """Returns the spending category for a description, or 'Other'."""
    text = description.lower()
    for category, keywords in _RULES.items():
        if any(keyword in text for keyword in keywords):
            return category
    return "Other"


def categorize(transactions: List[Transaction]) -> List[Transaction]:
    """Returns transactions with their ``category`` field assigned.

    Positive amounts that match no income rule are still tagged by keyword;
    a positive amount with category 'Other' is treated as income downstream.
    """
    return [
        replace(txn, category=categorize_description(txn.description))
        for txn in transactions
    ]
