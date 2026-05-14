"""Fiscal calendar + period engine.

Deterministic generator for fiscal-year, quarter, and month period nodes
plus a small hard-coded public-holiday table for the eight demo regions.
Stdlib only.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta

__all__ = [
    "FiscalCalendar",
    "build_calendar",
    "public_holidays",
    "period_node_id",
    "all_periods",
]


@dataclass(frozen=True)
class FiscalCalendar:
    fiscal_year: int
    fiscal_year_start: date
    quarters: tuple[tuple[date, date], ...]


def _add_months(d: date, months: int) -> date:
    m_index = d.month - 1 + months
    year = d.year + m_index // 12
    month = m_index % 12 + 1
    day = min(d.day, monthrange(year, month)[1])
    return date(year, month, day)


def build_calendar(
    fiscal_year: int,
    *,
    fiscal_start_month: int = 1,
    fiscal_start_day: int = 1,
) -> FiscalCalendar:
    start = date(fiscal_year, fiscal_start_month, fiscal_start_day)
    quarters: list[tuple[date, date]] = []
    cursor = start
    for _ in range(4):
        next_q = _add_months(cursor, 3)
        end_inclusive = next_q - timedelta(days=1)
        quarters.append((cursor, end_inclusive))
        cursor = next_q
    return FiscalCalendar(
        fiscal_year=fiscal_year,
        fiscal_year_start=start,
        quarters=tuple(quarters),
    )


# Hard-coded major nationals only (~10 per region). Demo, not Workday.
_FIXED_HOLIDAYS: dict[str, tuple[tuple[int, int, str], ...]] = {
    "UK": (
        (1, 1, "New Year's Day"),
        (5, 1, "Early May Bank Holiday"),
        (5, 27, "Spring Bank Holiday"),
        (8, 26, "Summer Bank Holiday"),
        (12, 25, "Christmas Day"),
        (12, 26, "Boxing Day"),
    ),
    "US": (
        (1, 1, "New Year's Day"),
        (1, 20, "Martin Luther King Jr. Day"),
        (5, 26, "Memorial Day"),
        (6, 19, "Juneteenth"),
        (7, 4, "Independence Day"),
        (9, 1, "Labor Day"),
        (11, 11, "Veterans Day"),
        (11, 27, "Thanksgiving"),
        (12, 25, "Christmas Day"),
    ),
    "DE": (
        (1, 1, "Neujahr"),
        (5, 1, "Tag der Arbeit"),
        (10, 3, "Tag der Deutschen Einheit"),
        (12, 25, "1. Weihnachtstag"),
        (12, 26, "2. Weihnachtstag"),
        (1, 6, "Heilige Drei Koenige"),
        (8, 15, "Mariae Himmelfahrt"),
        (11, 1, "Allerheiligen"),
    ),
    "FR": (
        (1, 1, "Jour de l'an"),
        (5, 1, "Fete du Travail"),
        (5, 8, "Victoire 1945"),
        (7, 14, "Fete Nationale"),
        (8, 15, "Assomption"),
        (11, 1, "Toussaint"),
        (11, 11, "Armistice"),
        (12, 25, "Noel"),
    ),
    "JP": (
        (1, 1, "Ganjitsu"),
        (2, 11, "Kenkoku Kinen no Hi"),
        (2, 23, "Tenno Tanjobi"),
        (4, 29, "Showa no Hi"),
        (5, 3, "Kenpo Kinenbi"),
        (5, 4, "Midori no Hi"),
        (5, 5, "Kodomo no Hi"),
        (8, 11, "Yama no Hi"),
        (11, 3, "Bunka no Hi"),
        (11, 23, "Kinro Kansha no Hi"),
    ),
    "IN": (
        (1, 26, "Republic Day"),
        (8, 15, "Independence Day"),
        (10, 2, "Gandhi Jayanti"),
        (12, 25, "Christmas Day"),
        (5, 1, "Labour Day"),
        (4, 14, "Ambedkar Jayanti"),
    ),
    "BR": (
        (1, 1, "Confraternizacao Universal"),
        (4, 21, "Tiradentes"),
        (5, 1, "Dia do Trabalho"),
        (9, 7, "Independencia"),
        (10, 12, "Nossa Senhora Aparecida"),
        (11, 2, "Finados"),
        (11, 15, "Proclamacao da Republica"),
        (12, 25, "Natal"),
    ),
    "AU": (
        (1, 1, "New Year's Day"),
        (1, 26, "Australia Day"),
        (4, 25, "Anzac Day"),
        (12, 25, "Christmas Day"),
        (12, 26, "Boxing Day"),
        (6, 9, "King's Birthday"),
    ),
}


def public_holidays(year: int, region: str) -> list[date]:
    """Return public holidays for the given region and year.

    Supported regions: 'UK', 'US', 'DE', 'FR', 'JP', 'IN', 'BR', 'AU'.
    """
    if region not in _FIXED_HOLIDAYS:
        raise ValueError(f"Unsupported region: {region!r}")
    return [date(year, m, d) for (m, d, _label) in _FIXED_HOLIDAYS[region]]


def period_node_id(
    kind: str,
    year: int,
    *,
    quarter: int | None = None,
    month: int | None = None,
) -> str:
    if kind == "annual":
        return f"PERIOD-{year}-annual"
    if kind == "quarter":
        if quarter is None or not 1 <= quarter <= 4:
            raise ValueError("quarter must be 1..4 for kind='quarter'")
        return f"PERIOD-{year}-Q{quarter}"
    if kind == "month":
        if month is None or not 1 <= month <= 12:
            raise ValueError("month must be 1..12 for kind='month'")
        return f"PERIOD-{year}-M{month:02d}"
    raise ValueError(f"Unknown period kind: {kind!r}")


_MONTH_LABELS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)


def all_periods(fiscal_year: int) -> list[dict]:
    """Return annual + 4 quarterly + 12 monthly period dicts (17 total)."""
    cal = build_calendar(fiscal_year)
    periods: list[dict] = []

    annual_end = _add_months(cal.fiscal_year_start, 12) - timedelta(days=1)
    periods.append({
        "id": period_node_id("annual", fiscal_year),
        "kind": "annual",
        "starts": cal.fiscal_year_start,
        "ends": annual_end,
        "label": f"FY{fiscal_year}",
    })

    for i, (q_start, q_end) in enumerate(cal.quarters, start=1):
        periods.append({
            "id": period_node_id("quarter", fiscal_year, quarter=i),
            "kind": "quarter",
            "starts": q_start,
            "ends": q_end,
            "label": f"FY{fiscal_year} Q{i}",
        })

    for m in range(1, 13):
        m_start = date(fiscal_year, m, 1)
        m_end = date(fiscal_year, m, monthrange(fiscal_year, m)[1])
        periods.append({
            "id": period_node_id("month", fiscal_year, month=m),
            "kind": "month",
            "starts": m_start,
            "ends": m_end,
            "label": f"{_MONTH_LABELS[m - 1]} {fiscal_year}",
        })

    return periods
