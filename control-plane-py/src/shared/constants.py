# src/shared/constants.py
"""Canonical decision values for HITL approval outcomes."""
from __future__ import annotations

DECISION_APPROVED: frozenset[str] = frozenset({"approve", "approved", "ok"})
DECISION_REJECTED: frozenset[str] = frozenset({"reject", "rejected", "deny", "denied"})
