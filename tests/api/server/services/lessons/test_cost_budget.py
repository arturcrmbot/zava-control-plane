from datetime import date

from api.server.services.lessons.cost_budget import (
    CostBudget,
    estimate_usd,
)


def test_estimate_usd_uses_published_gpt4o_rates():
    # 1M input + 1M output = 2.50 + 10.00 = 12.50
    assert round(estimate_usd(input_tokens=1_000_000, output_tokens=1_000_000), 2) == 12.50


def test_record_usage_accumulates_per_domain_per_day():
    b = CostBudget(daily_budget_usd=5.0)
    today = date(2026, 5, 20)
    b.record(domain="hiring", input_tokens=100_000, output_tokens=10_000, on_date=today)
    b.record(domain="hiring", input_tokens=50_000, output_tokens=5_000, on_date=today)
    spent = b.spent_today(domain="hiring", on_date=today)
    # (150k @ 2.50/1M) + (15k @ 10/1M) = 0.375 + 0.15 = 0.525
    assert round(spent, 3) == 0.525


def test_is_over_budget_returns_true_once_threshold_crossed():
    b = CostBudget(daily_budget_usd=0.10)
    today = date(2026, 5, 20)
    assert b.is_over_budget("hiring", on_date=today) is False
    # 1M input @ $2.50 — far over the $0.10 budget
    b.record(domain="hiring", input_tokens=1_000_000, output_tokens=0, on_date=today)
    assert b.is_over_budget("hiring", on_date=today) is True


def test_different_domains_have_independent_budgets():
    b = CostBudget(daily_budget_usd=0.10)
    today = date(2026, 5, 20)
    b.record(domain="hiring", input_tokens=1_000_000, output_tokens=0, on_date=today)
    assert b.is_over_budget("hiring", on_date=today) is True
    assert b.is_over_budget("vendor_kyc", on_date=today) is False


def test_new_day_resets_implicitly():
    b = CostBudget(daily_budget_usd=0.10)
    yesterday = date(2026, 5, 19)
    today = date(2026, 5, 20)
    b.record(domain="hiring", input_tokens=1_000_000, output_tokens=0, on_date=yesterday)
    assert b.is_over_budget("hiring", on_date=yesterday) is True
    assert b.is_over_budget("hiring", on_date=today) is False
