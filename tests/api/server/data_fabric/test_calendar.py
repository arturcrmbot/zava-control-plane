from datetime import date

import pytest

from api.server.data_fabric.calendar import (
    all_periods,
    build_calendar,
    period_node_id,
    public_holidays,
)


def test_build_calendar_calendar_year():
    cal = build_calendar(2026)
    assert cal.fiscal_year == 2026
    assert cal.fiscal_year_start == date(2026, 1, 1)
    assert len(cal.quarters) == 4
    assert cal.quarters[0] == (date(2026, 1, 1), date(2026, 3, 31))
    assert cal.quarters[1] == (date(2026, 4, 1), date(2026, 6, 30))
    assert cal.quarters[2] == (date(2026, 7, 1), date(2026, 9, 30))
    assert cal.quarters[3] == (date(2026, 10, 1), date(2026, 12, 31))


def test_build_calendar_uk_fiscal():
    cal = build_calendar(2026, fiscal_start_month=4, fiscal_start_day=6)
    assert cal.fiscal_year_start == date(2026, 4, 6)
    assert cal.quarters[0][0] == date(2026, 4, 6)
    assert cal.quarters[3][1] == date(2027, 4, 5)


def test_period_node_id_formats():
    assert period_node_id("annual", 2026) == "PERIOD-2026-annual"
    assert period_node_id("quarter", 2026, quarter=2) == "PERIOD-2026-Q2"
    assert period_node_id("month", 2026, month=3) == "PERIOD-2026-M03"
    with pytest.raises(ValueError):
        period_node_id("quarter", 2026)
    with pytest.raises(ValueError):
        period_node_id("month", 2026, month=13)
    with pytest.raises(ValueError):
        period_node_id("bogus", 2026)


def test_all_periods_counts_and_labels():
    periods = all_periods(2026)
    assert len(periods) == 1 + 4 + 12
    kinds = [p["kind"] for p in periods]
    assert kinds.count("annual") == 1
    assert kinds.count("quarter") == 4
    assert kinds.count("month") == 12
    for p in periods:
        assert p["label"]
        assert p["id"].startswith("PERIOD-2026-")
        assert isinstance(p["starts"], date)
        assert isinstance(p["ends"], date)
        assert p["starts"] <= p["ends"]


@pytest.mark.parametrize(
    "region", ["UK", "US", "DE", "FR", "JP", "IN", "BR", "AU"],
)
def test_public_holidays_minimum(region):
    holidays = public_holidays(2026, region)
    assert len(holidays) >= 5
    for h in holidays:
        assert h.year == 2026


def test_public_holidays_unknown_region():
    with pytest.raises(ValueError):
        public_holidays(2026, "ZZ")
