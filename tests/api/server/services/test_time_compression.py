"""Tests for the simulator's business-time compression helper (pitch-c5)."""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from api.server.services import time_compression


def test_compression_factor_default(monkeypatch):
    monkeypatch.delenv("SIMULATOR_TIME_COMPRESSION", raising=False)
    assert time_compression.time_compression_factor() == 60.0


def test_compression_factor_from_env(monkeypatch):
    monkeypatch.setenv("SIMULATOR_TIME_COMPRESSION", "86400")
    assert time_compression.time_compression_factor() == 86400.0


def test_business_now_at_base_returns_base(monkeypatch):
    monkeypatch.setenv("SIMULATOR_TIME_COMPRESSION", "60")
    base = datetime(2026, 1, 1, 0, 0, 0)
    time_compression.reset_base(base)
    # Zero elapsed real time -> business time == base.
    assert time_compression.business_now(real_now=base) == base


def test_business_now_advances_with_factor(monkeypatch):
    """Wall-clock 1 second @ factor 60 -> 60 business seconds."""
    monkeypatch.setenv("SIMULATOR_TIME_COMPRESSION", "60")
    base = datetime(2026, 1, 1, 0, 0, 0)
    time_compression.reset_base(base)
    real = base + timedelta(seconds=1)
    biz = time_compression.business_now(real_now=real)
    assert biz == base + timedelta(seconds=60)


def test_business_now_fast_forward_one_day_per_second(monkeypatch):
    """Factor 86400 -> 1 wall-clock second == 1 business day."""
    monkeypatch.setenv("SIMULATOR_TIME_COMPRESSION", "86400")
    base = datetime(2026, 1, 1, 0, 0, 0)
    time_compression.reset_base(base)
    # 30 wall seconds -> 30 business days.
    real = base + timedelta(seconds=30)
    biz = time_compression.business_now(real_now=real)
    assert biz == base + timedelta(days=30)


def test_business_now_explicit_base_overrides_module_base(monkeypatch):
    monkeypatch.setenv("SIMULATOR_TIME_COMPRESSION", "60")
    module_base = datetime(2020, 1, 1)
    time_compression.reset_base(module_base)
    explicit_base = datetime(2030, 6, 15, 12, 0, 0)
    real = explicit_base + timedelta(seconds=2)
    biz = time_compression.business_now(real_now=real, base=explicit_base)
    assert biz == explicit_base + timedelta(seconds=120)


def test_reset_base_default_is_now():
    before = datetime.utcnow()
    time_compression.reset_base()
    after = datetime.utcnow()
    assert before <= time_compression._BASE <= after


def test_invalid_factor_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("SIMULATOR_TIME_COMPRESSION", "not-a-number")
    assert time_compression.time_compression_factor() == 60.0
