"""Focused tests for schedule_constraints helper functions (TDD).

Tests latent type bug: _number() should return None for non-finite values.
"""
from __future__ import annotations

import math

import pytest

from verticals.airline.schedule_constraints import _number


class TestNumberHelper:
    """Tests for _number() helper function."""

    def test_number_accepts_valid_int(self) -> None:
        """Valid integers convert to float."""
        assert _number(42) == 42.0
        assert _number(0) == 0.0
        assert _number(-100) == -100.0

    def test_number_accepts_valid_float(self) -> None:
        """Valid floats pass through."""
        assert _number(3.14) == 3.14
        assert _number(0.0) == 0.0
        assert _number(-2.5) == -2.5

    def test_number_rejects_bool(self) -> None:
        """Booleans are explicitly rejected."""
        assert _number(True) is None
        assert _number(False) is None

    def test_number_rejects_non_number(self) -> None:
        """Non-numeric types return None."""
        assert _number("42") is None
        assert _number(None) is None
        assert _number([]) is None
        assert _number({}) is None
        assert _number((1, 2)) is None

    def test_number_rejects_infinity(self) -> None:
        """Infinity values should return None (not {}!)."""
        assert _number(float('inf')) is None
        assert _number(float('-inf')) is None

    def test_number_rejects_nan(self) -> None:
        """NaN should return None (not {}!)."""
        assert _number(float('nan')) is None
