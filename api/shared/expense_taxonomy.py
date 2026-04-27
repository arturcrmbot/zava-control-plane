"""Shared types for the POC1 expense-compliance domain.

These constants are duplicated across the synthetic data generator, the accuracy
harness, the validator, and the React UI. Keeping them in one place prevents
verdict/category drift between the layers."""
from __future__ import annotations
from typing import Literal

Verdict = Literal["green", "amber", "red"]

VERDICTS: tuple[Verdict, ...] = ("green", "amber", "red")

ExpenseCategory = Literal["meals", "travel", "accommodation", "entertainment", "miscellaneous"]

CATEGORIES: tuple[ExpenseCategory, ...] = (
    "meals", "travel", "accommodation", "entertainment", "miscellaneous",
)

Market = Literal["UK", "US", "DE", "IN"]

MARKETS: tuple[Market, ...] = ("UK", "US", "DE", "IN")

CURRENCY_BY_MARKET: dict[Market, str] = {"UK": "GBP", "US": "USD", "DE": "EUR", "IN": "INR"}
