import pytest

from api.server.data_fabric.locales import LOCALES, Locale

EXPECTED_REGIONS = ("UK", "US", "DE", "FR", "JP", "IN", "BR", "AU")


def test_all_regions_present():
    assert set(LOCALES.keys()) == set(EXPECTED_REGIONS)
    assert len(LOCALES) == 8


@pytest.mark.parametrize("region", EXPECTED_REGIONS)
def test_required_fields_non_empty(region):
    loc = LOCALES[region]
    assert isinstance(loc, Locale)
    assert loc.region == region
    assert loc.currency
    assert loc.date_format
    assert loc.decimal_separator
    assert loc.thousands_separator
    assert loc.payroll_calendar in {"monthly", "biweekly", "weekly"}
    assert isinstance(loc.salutations, tuple)
    assert len(loc.salutations) >= 2
    assert all(s for s in loc.salutations)


def test_de_requires_works_council():
    assert LOCALES["DE"].works_council_required is True


def test_non_de_works_council_default_false():
    for region, loc in LOCALES.items():
        if region == "DE":
            continue
        assert loc.works_council_required is False


def test_currency_codes_are_iso_like():
    for loc in LOCALES.values():
        assert len(loc.currency) == 3
        assert loc.currency.isupper()
