"""Locale registry for the eight demo regions.

Hard-coded crude regional rules (currency, formatting, statutory
expense limits, payroll cadence, works-council flag, salutations).
Used by downstream seeders + UI to localise demo data. Stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Locale", "LOCALES"]


@dataclass(frozen=True)
class Locale:
    region: str
    currency: str
    date_format: str
    decimal_separator: str
    thousands_separator: str
    statutory_expense_limit_per_day: float | None
    payroll_calendar: str
    works_council_required: bool
    salutations: tuple[str, ...]


LOCALES: dict[str, Locale] = {
    "UK": Locale(
        region="UK",
        currency="GBP",
        date_format="DD/MM/YYYY",
        decimal_separator=".",
        thousands_separator=",",
        statutory_expense_limit_per_day=150.0,
        payroll_calendar="monthly",
        works_council_required=False,
        salutations=("Mr", "Ms", "Mrs", "Miss", "Dr", "Prof"),
    ),
    "US": Locale(
        region="US",
        currency="USD",
        date_format="MM/DD/YYYY",
        decimal_separator=".",
        thousands_separator=",",
        statutory_expense_limit_per_day=200.0,
        payroll_calendar="biweekly",
        works_council_required=False,
        salutations=("Mr.", "Ms.", "Mrs.", "Miss", "Dr.", "Prof."),
    ),
    "DE": Locale(
        region="DE",
        currency="EUR",
        date_format="DD.MM.YYYY",
        decimal_separator=",",
        thousands_separator=".",
        statutory_expense_limit_per_day=120.0,
        payroll_calendar="monthly",
        works_council_required=True,
        salutations=("Herr", "Frau", "Dr.", "Prof."),
    ),
    "FR": Locale(
        region="FR",
        currency="EUR",
        date_format="DD/MM/YYYY",
        decimal_separator=",",
        thousands_separator=" ",
        statutory_expense_limit_per_day=130.0,
        payroll_calendar="monthly",
        works_council_required=False,
        salutations=("M.", "Mme", "Mlle", "Dr", "Prof."),
    ),
    "JP": Locale(
        region="JP",
        currency="JPY",
        date_format="YYYY/MM/DD",
        decimal_separator=".",
        thousands_separator=",",
        statutory_expense_limit_per_day=15000.0,
        payroll_calendar="monthly",
        works_council_required=False,
        salutations=("Mr", "Ms", "Dr", "Prof", "san"),
    ),
    "IN": Locale(
        region="IN",
        currency="INR",
        date_format="DD/MM/YYYY",
        decimal_separator=".",
        thousands_separator=",",
        statutory_expense_limit_per_day=4000.0,
        payroll_calendar="monthly",
        works_council_required=False,
        salutations=("Mr", "Ms", "Mrs", "Dr", "Prof", "Shri", "Smt"),
    ),
    "BR": Locale(
        region="BR",
        currency="BRL",
        date_format="DD/MM/YYYY",
        decimal_separator=",",
        thousands_separator=".",
        statutory_expense_limit_per_day=400.0,
        payroll_calendar="monthly",
        works_council_required=False,
        salutations=("Sr.", "Sra.", "Srta.", "Dr.", "Prof."),
    ),
    "AU": Locale(
        region="AU",
        currency="AUD",
        date_format="DD/MM/YYYY",
        decimal_separator=".",
        thousands_separator=",",
        statutory_expense_limit_per_day=180.0,
        payroll_calendar="biweekly",
        works_council_required=False,
        salutations=("Mr", "Ms", "Mrs", "Miss", "Dr", "Prof"),
    ),
}
