"""Tests for api.server.services.model_pricing."""
from __future__ import annotations

import pytest

from api.server.services import model_pricing


def test_cost_for_gpt41_input_only():
    # 1M input tokens at $2/M = $2.00
    assert model_pricing.cost_for("gpt-4.1", 1_000_000, 0) == pytest.approx(2.00)


def test_cost_for_gpt41_output_only():
    # 1M output tokens at $8/M = $8.00
    assert model_pricing.cost_for("gpt-4.1", 0, 1_000_000) == pytest.approx(8.00)


def test_cost_for_gpt41_mixed():
    # 500k in @ $2/M + 250k out @ $8/M = 1.00 + 2.00 = 3.00
    assert model_pricing.cost_for("gpt-4.1", 500_000, 250_000) == pytest.approx(3.00)


def test_cost_for_mini_cheaper_than_full():
    full = model_pricing.cost_for("gpt-4.1", 100_000, 100_000)
    mini = model_pricing.cost_for("gpt-4.1-mini", 100_000, 100_000)
    assert mini < full


def test_cost_for_unknown_model_falls_back_with_warning(caplog):
    with caplog.at_level("WARNING"):
        cost = model_pricing.cost_for("does-not-exist-9000", 1_000_000, 0)
    assert cost == pytest.approx(2.00)  # gpt-4.1 fallback
    assert any("unknown model" in r.message for r in caplog.records)


def test_cost_for_clamps_negative_tokens():
    assert model_pricing.cost_for("gpt-4.1", -500, -500) == 0.0


def test_cost_for_handles_none_tokens():
    assert model_pricing.cost_for("gpt-4.1", None, None) == 0.0  # type: ignore[arg-type]


def test_pricing_source_is_dated():
    assert model_pricing.PRICING_SOURCE.startswith("azure-published-")
    assert "2026" in model_pricing.PRICING_SOURCE
