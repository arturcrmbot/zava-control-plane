"""Candidate portal routes — public /apply + token-authed /status, /offer.

Skeleton — implemented by Stream 1 candidate-portal subagent (see
docs/superpowers/plans/2026-04-30-candidate-portal-plan.md Tasks 5-7, 13).

Empty router for now so api/server/main.py registration doesn't fail.
"""
from __future__ import annotations
from fastapi import APIRouter

router = APIRouter(prefix="/api/portal", tags=["portal"])
