"""Accelerator -> FastAPI callback after a voice screen call ends.

Skeleton — implemented by Stream 2 voice-real subagent (see
docs/superpowers/plans/2026-04-30-voice-real-plan.md Phase 1 Task 1).

Empty router for now so api/server/main.py registration doesn't fail.
"""
from __future__ import annotations
from fastapi import APIRouter

router = APIRouter(prefix="/api/portal/voice", tags=["portal", "voice"])
