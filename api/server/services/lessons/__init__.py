"""Lesson store: shared, governed, cross-agent memory tier.

Public surface:
  - Lesson, LessonScope, LessonProvenance, LessonCandidate (types)
  - LessonStore (Protocol), InMemoryLessonStore (tests)
  - Mem0LessonStore (default impl, lazy-imports mem0)
  - LessonGovernor (the one path callers use)
  - KuzuLessonProvenance (provenance writes)
"""
from api.server.services.lessons.governor import LessonGovernor
from api.server.services.lessons.kuzu_provenance import KuzuLessonProvenance
from api.server.services.lessons.mem0_store import Mem0LessonStore
from api.server.services.lessons.store import InMemoryLessonStore, LessonStore
from api.server.services.lessons.types import (
    Lesson,
    LessonCandidate,
    LessonProvenance,
    LessonScope,
)

__all__ = [
    "Lesson",
    "LessonCandidate",
    "LessonGovernor",
    "LessonProvenance",
    "LessonScope",
    "LessonStore",
    "InMemoryLessonStore",
    "KuzuLessonProvenance",
    "Mem0LessonStore",
]
