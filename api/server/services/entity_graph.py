"""Embedded KuzuDB-backed entity graph (Plane 1 of the Agentic Org Blueprint).

This module is the persistence + query layer for the org's *nouns* — Person,
Organisation, Asset, Money, Decision, Place, Period, Workflow — and their
relationships. Future phases bind to the public API on :class:`EntityGraph`:

* Phase 1 ``EntityReflector`` (a bus subscriber) calls ``upsert`` / ``link`` /
  ``record_decision`` from a per-domain projection function.
* Phase 3 wraps the Cypher passthrough helpers (:meth:`EntityGraph.query`,
  :meth:`EntityGraph.query_one`) as MCP tools (``query_entity``,
  ``find_entities`` via :mod:`api.server.services.find_patterns`,
  ``query_recent_decisions``).
* Phase 4 traverses ``Decision`` nodes via the same passthrough helpers
  (``query_precedents``).

Schema is bootstrapped via ``CREATE … IF NOT EXISTS`` on first construction
and matches the blueprint §2 Plane 1 schema block at
``docs/archive/agentic-org-blueprint.md`` lines ~180–236, plus the §3 ``Workflow``
self-relation added in Phase 1 per REQ-001 to give the Phase 4 meta-workflow
projection a place to write to without a schema migration.

This file lands the *shell* (TASK-002 in
``plan/feature-agentic-org-phase-1-entity-graph.md``):

* Frozen dataclasses :class:`EntityWrite`, :class:`RelWrite`,
  :class:`DecisionWrite` that projection functions return.
* The :func:`_ulid` helper used by :meth:`EntityGraph.record_decision` to
  mint Decision ids (PAT-001 — monotonic-suffixed under a module lock so the
  same-ms ordering is deterministic).
* The :class:`EntityGraph` constructor that opens the database, runs the
  schema DDL idempotently, and exposes three Cypher passthrough helpers
  (REQ-002).

The remaining behavioural method (``record_decision``) lands in TASK-007.
"""
from __future__ import annotations

import json
import logging
import os
import re
import secrets
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import kuzu

from api.shared.events import FleetEvent


log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Kuzu DDL idempotency helpers
# ---------------------------------------------------------------------------
#
# Kuzu 0.6.1 does not ship typed DDL exceptions — every bind/parse error
# surfaces as a plain :class:`RuntimeError` whose message starts with
# ``"Binder exception: "``. The substrings below are stable across the
# 0.6.x line (verified at 0.6.1 against ``CREATE NODE TABLE`` /
# ``ALTER TABLE ADD`` / ``MATCH … RETURN n.<missing>``) and let us
# narrow the bootstrap & upsert "swallow if already-applied" paths to
# the specific re-application errors instead of the prior bare
# ``except Exception: pass`` (which masked half-upgrades and unrelated
# Kuzu failures).

_KUZU_ALREADY_EXISTS_MARKERS: tuple[str, ...] = (
    "already exists in catalog",   # CREATE NODE/REL TABLE
    "already has property",         # ALTER TABLE ADD <existing column>
)
_KUZU_MISSING_PROPERTY_MARKER = "Cannot find property"


def _is_kuzu_already_exists(exc: BaseException) -> bool:
    """Return True iff ``exc`` is the Kuzu "object already exists" DDL error."""
    if not isinstance(exc, RuntimeError):
        return False
    msg = str(exc)
    return any(marker in msg for marker in _KUZU_ALREADY_EXISTS_MARKERS)


def _is_kuzu_missing_property(exc: BaseException) -> bool:
    """Return True iff ``exc`` is the Kuzu "no such property on node" error.

    Used by :meth:`EntityGraph.upsert` to tolerate reading
    ``first_seen_at`` on a kind whose timestamp-column migration has not
    yet landed on this database.
    """
    if not isinstance(exc, RuntimeError):
        return False
    return _KUZU_MISSING_PROPERTY_MARKER in str(exc)


# ---------------------------------------------------------------------------
# ULID helper (PAT-001)
# ---------------------------------------------------------------------------

# Crockford base32 — no I, L, O, U so ids are unambiguous when read aloud or
# hand-typed.
_CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

# Module-level monotonic state. The reflector dispatches synchronously
# today, but the lock is cheap insurance for future async dispatch.
_ULID_LOCK = threading.Lock()
_ULID_LAST_MS: int = 0
_ULID_LAST_RANDOM: int = 0  # 80-bit integer of the random suffix

# Regex for validating entity attribute keys. Keys must be valid identifiers
# (alphanumeric + underscore, not starting with a digit).
_VALID_ATTR_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Attribute keys reserved for projection metadata (PAT-002): callers may
# stash these in ``EntityWrite.attrs`` so the ``entity.upserted`` event +
# audit entry can carry workflow provenance, but they are NOT columns on
# any Plane 1 node table (except Decision, where workflow_id and source_event
# are real columns) and must be excluded from the Cypher SET clause.
_ATTR_METADATA_KEYS: frozenset[str] = frozenset({"workflow_id", "source_event"})


def _encode_crockford(value: int, length: int) -> str:
    """Encode ``value`` as exactly ``length`` Crockford-base32 characters."""
    chars = []
    for _ in range(length):
        chars.append(_CROCKFORD_ALPHABET[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))


def _ulid() -> str:
    """Mint a 26-character Crockford-base32 ULID.

    Layout: 10 chars (48 bits) of millisecond timestamp + 16 chars (80 bits)
    of randomness. Within the same millisecond the random suffix is
    incremented under :data:`_ULID_LOCK` so a tight loop produces strictly
    increasing values (PAT-001 monotonic guarantee).
    """
    global _ULID_LAST_MS, _ULID_LAST_RANDOM
    with _ULID_LOCK:
        now_ms = int(time.time() * 1000)
        if now_ms <= _ULID_LAST_MS:
            # Same (or backwards-clocked) ms → bump the previous random
            # suffix by one to preserve lexicographic ordering.
            now_ms = _ULID_LAST_MS
            random_int = (_ULID_LAST_RANDOM + 1) & ((1 << 80) - 1)
            if random_int == 0:
                # Astronomical case: 80-bit overflow inside one ms → spill
                # into the next ms to keep monotonicity intact.
                now_ms += 1
                random_int = int.from_bytes(secrets.token_bytes(10), "big")
        else:
            random_int = int.from_bytes(secrets.token_bytes(10), "big")
        _ULID_LAST_MS = now_ms
        _ULID_LAST_RANDOM = random_int
    return _encode_crockford(now_ms, 10) + _encode_crockford(random_int, 16)


# ---------------------------------------------------------------------------
# Projection-op records (PAT-002)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EntityWrite:
    """A single node upsert emitted by a projection function."""

    kind: str
    id: str
    attrs: dict[str, Any]
    source_workflows: tuple[str, ...] = ()


@dataclass(frozen=True)
class RelWrite:
    """A single relationship insert emitted by a projection function."""

    src_id: str
    rel: str
    dst_id: str
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DecisionWrite:
    """A first-class Decision node + its DECIDED_ON edges (PAT-006)."""

    workflow_id: str
    phase: str
    persona_role: str
    verdict: str
    reason: str
    decided_at: str  # ISO-8601 timestamp; reflector handles parsing
    source_event: str
    attributes: dict[str, Any] = field(default_factory=dict)
    decided_on: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Schema (blueprint §2 Plane 1 + §3 Workflow self-relation)
# ---------------------------------------------------------------------------

# NOTE on PRIMARY KEY syntax: Kuzu 0.6.1's parser does not accept the inline
# ``id STRING PRIMARY KEY`` form shown in the blueprint Cypher block — it
# requires the trailing ``PRIMARY KEY (id)`` clause. Column definitions are
# otherwise verbatim from the blueprint.
_NODE_TABLES: tuple[tuple[str, str], ...] = (
    (
        "Person",
        """
        CREATE NODE TABLE IF NOT EXISTS Person (
            id STRING,
            name STRING, email STRING, role STRING, market STRING, department STRING,
            employed_from DATE, employed_to DATE,
            source_workflows STRING[],
            attributes STRING,
            PRIMARY KEY (id)
        )
        """,
    ),
    (
        "Organisation",
        """
        CREATE NODE TABLE IF NOT EXISTS Organisation (
            id STRING,
            name STRING, kind STRING,
            country STRING, jurisdiction STRING, risk_band STRING,
            source_workflows STRING[],
            attributes STRING,
            PRIMARY KEY (id)
        )
        """,
    ),
    (
        "Asset",
        """
        CREATE NODE TABLE IF NOT EXISTS Asset (
            id STRING,
            kind STRING,
            identifier STRING, status STRING,
            acquired_at DATE, retired_at DATE,
            source_workflows STRING[],
            attributes STRING,
            PRIMARY KEY (id)
        )
        """,
    ),
    (
        "Money",
        """
        CREATE NODE TABLE IF NOT EXISTS Money (
            id STRING,
            amount DOUBLE, currency STRING,
            kind STRING,
            period STRING,
            source_workflows STRING[],
            attributes STRING,
            PRIMARY KEY (id)
        )
        """,
    ),
    (
        "Decision",
        """
        CREATE NODE TABLE IF NOT EXISTS Decision (
            id STRING,
            workflow_id STRING, phase STRING, persona_role STRING,
            verdict STRING, reason STRING, decided_at TIMESTAMP,
            source_event STRING,
            amount_gbp DOUBLE, currency_pair STRING, notional_gbp DOUBLE,
            vendor_id STRING, client_brand STRING,
            attributes STRING,
            PRIMARY KEY (id)
        )
        """,
    ),
    (
        "Place",
        """
        CREATE NODE TABLE IF NOT EXISTS Place (
            id STRING,
            kind STRING, name STRING, parent_id STRING,
            attributes STRING,
            PRIMARY KEY (id)
        )
        """,
    ),
    (
        "Period",
        # NOTE: ``starts`` and ``ends`` are Kuzu 0.6.1 reserved words —
        # backtick-quoted to keep the blueprint column names verbatim.
        """
        CREATE NODE TABLE IF NOT EXISTS Period (
            id STRING,
            kind STRING, `starts` TIMESTAMP, `ends` TIMESTAMP, label STRING,
            PRIMARY KEY (id)
        )
        """,
    ),
    (
        "Workflow",
        """
        CREATE NODE TABLE IF NOT EXISTS Workflow (
            id STRING,
            workflow_type STRING, status STRING,
            started_at TIMESTAMP, completed_at TIMESTAMP,
            attributes STRING,
            PRIMARY KEY (id)
        )
        """,
    ),
    # ----- pitch-e1: agency-domain node kinds --------------------------
    (
        "Brand",
        """
        CREATE NODE TABLE IF NOT EXISTS Brand (
            id STRING,
            name STRING,
            market_segment STRING,
            annual_budget_gbp DOUBLE,
            budget_remaining_gbp DOUBLE,
            source_workflows STRING[],
            attributes STRING,
            PRIMARY KEY (id)
        )
        """,
    ),
    (
        "Campaign",
        """
        CREATE NODE TABLE IF NOT EXISTS Campaign (
            id STRING,
            name STRING,
            status STRING,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            source_workflows STRING[],
            attributes STRING,
            PRIMARY KEY (id)
        )
        """,
    ),
    (
        "Pitch",
        """
        CREATE NODE TABLE IF NOT EXISTS Pitch (
            id STRING,
            name STRING,
            status STRING,
            value_gbp DOUBLE,
            decided_at TIMESTAMP,
            source_workflows STRING[],
            attributes STRING,
            PRIMARY KEY (id)
        )
        """,
    ),
    (
        "MediaPlan",
        """
        CREATE NODE TABLE IF NOT EXISTS MediaPlan (
            id STRING,
            name STRING,
            status STRING,
            total_gbp DOUBLE,
            period STRING,
            source_workflows STRING[],
            attributes STRING,
            PRIMARY KEY (id)
        )
        """,
    ),
    (
        "Subsidiary",
        """
        CREATE NODE TABLE IF NOT EXISTS Subsidiary (
            id STRING,
            name STRING,
            country STRING,
            headcount INT64,
            source_workflows STRING[],
            attributes STRING,
            PRIMARY KEY (id)
        )
        """,
    ),
    (
        "Account",
        """
        CREATE NODE TABLE IF NOT EXISTS Account (
            id STRING,
            code STRING, name STRING, type STRING, currency STRING,
            source_workflows STRING[],
            attributes STRING,
            PRIMARY KEY (id)
        )
        """,
    ),
    (
        "CostCentre",
        """
        CREATE NODE TABLE IF NOT EXISTS CostCentre (
            id STRING,
            name STRING, subsidiary_id STRING, owner_role STRING,
            source_workflows STRING[],
            attributes STRING,
            PRIMARY KEY (id)
        )
        """,
    ),
    (
        "Insight",
        """
        CREATE NODE TABLE IF NOT EXISTS Insight (
            id STRING,
            role STRING,
            scope STRING,
            decided_at TIMESTAMP,
            headline STRING,
            body STRING,
            kpis STRING,
            proposed_actions STRING,
            fingerprint STRING,
            source_workflows STRING[],
            attributes STRING,
            PRIMARY KEY (id)
        )
        """,
    ),
    (
        "Lesson",
        """
        CREATE NODE TABLE IF NOT EXISTS Lesson (
            id STRING,
            body STRING,
            domain STRING,
            persona_role STRING,
            market STRING,
            status STRING,
            proposed_by STRING,
            rubric_score_delta DOUBLE,
            experiment_n INT64,
            promoted_at TIMESTAMP,
            supersedes STRING,
            prune_reason STRING,
            PRIMARY KEY (id)
        )
        """,
    ),
    (
        "DreamPass",
        """
        CREATE NODE TABLE IF NOT EXISTS DreamPass (
            id STRING,
            domain STRING,
            skill_version STRING,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            status STRING,
            candidates_proposed INT64,
            candidates_promoted INT64,
            PRIMARY KEY (id)
        )
        """,
    ),
    (
        "Experiment",
        """
        CREATE NODE TABLE IF NOT EXISTS Experiment (
            id STRING,
            dream_pass_id STRING,
            candidate_lesson_id STRING,
            control_score DOUBLE,
            treatment_score DOUBLE,
            delta DOUBLE,
            n_samples INT64,
            verdict STRING,
            run_at TIMESTAMP,
            PRIMARY KEY (id)
        )
        """,
    ),
)

_REL_TABLES: tuple[tuple[str, str], ...] = (
    ("EMPLOYED_BY", "CREATE REL TABLE IF NOT EXISTS EMPLOYED_BY (FROM Person TO Organisation, role STRING, since DATE, decided_at TIMESTAMP)"),
    ("MANAGES", "CREATE REL TABLE IF NOT EXISTS MANAGES (FROM Person TO Person, since DATE, decided_at TIMESTAMP)"),
    ("OWNS", "CREATE REL TABLE IF NOT EXISTS OWNS (FROM Person TO Asset, decided_at TIMESTAMP)"),
    ("TRANSACTS", "CREATE REL TABLE IF NOT EXISTS TRANSACTS (FROM Person TO Money, role STRING, decided_at TIMESTAMP)"),
    ("BELONGS_TO", "CREATE REL TABLE IF NOT EXISTS BELONGS_TO (FROM Money TO Period, decided_at TIMESTAMP)"),
    ("LOCATED_IN", "CREATE REL TABLE IF NOT EXISTS LOCATED_IN (FROM Person TO Place, decided_at TIMESTAMP)"),
    # DECIDED_<KIND> per target kind: Kuzu 0.6.1 doesn't support multi-pair
    # rel tables (one (FROM,TO) per table), so we shard the old DECIDED_ON
    # table by target kind. ``record_decision`` looks up each target id's
    # node label and writes to the matching DECIDED_<KIND> table. The old
    # DECIDED_ON table stays for backward compatibility on existing graph
    # files (no data migration; rebuild wipes the file).
    ("DECIDED_ON", "CREATE REL TABLE IF NOT EXISTS DECIDED_ON (FROM Decision TO Person, decided_at TIMESTAMP)"),
    ("DECIDED_PERSON", "CREATE REL TABLE IF NOT EXISTS DECIDED_PERSON (FROM Decision TO Person, decided_at TIMESTAMP)"),
    ("DECIDED_MONEY", "CREATE REL TABLE IF NOT EXISTS DECIDED_MONEY (FROM Decision TO Money, decided_at TIMESTAMP)"),
    ("DECIDED_ASSET", "CREATE REL TABLE IF NOT EXISTS DECIDED_ASSET (FROM Decision TO Asset, decided_at TIMESTAMP)"),
    ("DECIDED_ORG", "CREATE REL TABLE IF NOT EXISTS DECIDED_ORG (FROM Decision TO Organisation, decided_at TIMESTAMP)"),
    ("DECIDED_PERIOD", "CREATE REL TABLE IF NOT EXISTS DECIDED_PERIOD (FROM Decision TO Period, decided_at TIMESTAMP)"),
    ("DECIDED_PLACE", "CREATE REL TABLE IF NOT EXISTS DECIDED_PLACE (FROM Decision TO Place, decided_at TIMESTAMP)"),
    ("PRECEDENT_OF", "CREATE REL TABLE IF NOT EXISTS PRECEDENT_OF (FROM Decision TO Decision, decided_at TIMESTAMP)"),
    ("TOUCHED", "CREATE REL TABLE IF NOT EXISTS TOUCHED (FROM Person TO Decision, role STRING, decided_at TIMESTAMP)"),
    ("SUB_WORKFLOW_OF", "CREATE REL TABLE IF NOT EXISTS SUB_WORKFLOW_OF (FROM Workflow TO Workflow, spawned_at TIMESTAMP, decided_at TIMESTAMP)"),
    ("WORKFLOW_IN_PERIOD", "CREATE REL TABLE IF NOT EXISTS WORKFLOW_IN_PERIOD (FROM Workflow TO Period, decided_at TIMESTAMP)"),
    # ----- pitch-e1: agency-domain rel tables --------------------------
    ("BRAND_OF", "CREATE REL TABLE IF NOT EXISTS BRAND_OF (FROM Brand TO Organisation, decided_at TIMESTAMP)"),
    ("CAMPAIGN_FOR", "CREATE REL TABLE IF NOT EXISTS CAMPAIGN_FOR (FROM Campaign TO Brand, decided_at TIMESTAMP)"),
    ("EXECUTED_BY", "CREATE REL TABLE IF NOT EXISTS EXECUTED_BY (FROM Campaign TO Subsidiary, decided_at TIMESTAMP)"),
    ("SUPPLIED_BY", "CREATE REL TABLE IF NOT EXISTS SUPPLIED_BY (FROM Campaign TO Organisation, decided_at TIMESTAMP)"),
    ("PITCH_FOR", "CREATE REL TABLE IF NOT EXISTS PITCH_FOR (FROM Pitch TO Organisation, decided_at TIMESTAMP)"),
    ("RESULTED_IN", "CREATE REL TABLE IF NOT EXISTS RESULTED_IN (FROM Pitch TO Campaign, decided_at TIMESTAMP)"),
    ("PART_OF", "CREATE REL TABLE IF NOT EXISTS PART_OF (FROM Subsidiary TO Organisation, decided_at TIMESTAMP)"),
    # ----- pitch-e1: DECIDED_<kind> shards for new node kinds ----------
    ("DECIDED_BRAND", "CREATE REL TABLE IF NOT EXISTS DECIDED_BRAND (FROM Decision TO Brand, decided_at TIMESTAMP)"),
    ("DECIDED_CAMPAIGN", "CREATE REL TABLE IF NOT EXISTS DECIDED_CAMPAIGN (FROM Decision TO Campaign, decided_at TIMESTAMP)"),
    ("DECIDED_PITCH", "CREATE REL TABLE IF NOT EXISTS DECIDED_PITCH (FROM Decision TO Pitch, decided_at TIMESTAMP)"),
    ("DECIDED_MEDIAPLAN", "CREATE REL TABLE IF NOT EXISTS DECIDED_MEDIAPLAN (FROM Decision TO MediaPlan, decided_at TIMESTAMP)"),
    ("DECIDED_SUBSIDIARY", "CREATE REL TABLE IF NOT EXISTS DECIDED_SUBSIDIARY (FROM Decision TO Subsidiary, decided_at TIMESTAMP)"),
    ("PAYS", "CREATE REL TABLE IF NOT EXISTS PAYS (FROM Money TO Organisation, posted_at TIMESTAMP, decided_at TIMESTAMP)"),
    ("OWED_BY", "CREATE REL TABLE IF NOT EXISTS OWED_BY (FROM Money TO Organisation, posted_at TIMESTAMP, decided_at TIMESTAMP)"),
    ("BOOKED_AGAINST", "CREATE REL TABLE IF NOT EXISTS BOOKED_AGAINST (FROM Money TO Account, posted_at TIMESTAMP, decided_at TIMESTAMP)"),
    ("BOOKED_AGAINST_CC", "CREATE REL TABLE IF NOT EXISTS BOOKED_AGAINST_CC (FROM Money TO CostCentre, posted_at TIMESTAMP, decided_at TIMESTAMP)"),
    ("COSTED_TO", "CREATE REL TABLE IF NOT EXISTS COSTED_TO (FROM Money TO CostCentre, posted_at TIMESTAMP, decided_at TIMESTAMP)"),
    ("COSTED_TO_BRAND", "CREATE REL TABLE IF NOT EXISTS COSTED_TO_BRAND (FROM Money TO Brand, posted_at TIMESTAMP, decided_at TIMESTAMP)"),
    # Note: COSTED_TO targets CostCentre. A separate Money→Brand cost rel
    # is added in Phase 3 (Task 3.5) once Brand nodes exist.
    # ----- lesson-store: dream-pass provenance edges -------------------
    ("LESSON_FROM_RUN", "CREATE REL TABLE IF NOT EXISTS LESSON_FROM_RUN (FROM Lesson TO Workflow, recorded_at TIMESTAMP)"),
    ("LESSON_ABOUT_PERSONA", "CREATE REL TABLE IF NOT EXISTS LESSON_ABOUT_PERSONA (FROM Lesson TO Person, recorded_at TIMESTAMP)"),
    ("LESSON_SUPERSEDES", "CREATE REL TABLE IF NOT EXISTS LESSON_SUPERSEDES (FROM Lesson TO Lesson, recorded_at TIMESTAMP)"),
    ("EXPERIMENT_FOR_LESSON", "CREATE REL TABLE IF NOT EXISTS EXPERIMENT_FOR_LESSON (FROM Experiment TO Lesson, recorded_at TIMESTAMP)"),
    ("EXPERIMENT_USED_PERSONA", "CREATE REL TABLE IF NOT EXISTS EXPERIMENT_USED_PERSONA (FROM Experiment TO Person, arm STRING, recorded_at TIMESTAMP)"),
)

# Decision target kind → rel-table name. Keys must match :data:`_VALID_KINDS`
# values that ``record_decision`` may resolve at link-time.
_DECIDED_REL_BY_KIND: dict[str, str] = {
    "Person": "DECIDED_PERSON",
    "Money": "DECIDED_MONEY",
    "Asset": "DECIDED_ASSET",
    "Organisation": "DECIDED_ORG",
    "Period": "DECIDED_PERIOD",
    "Place": "DECIDED_PLACE",
    "Brand": "DECIDED_BRAND",
    "Campaign": "DECIDED_CAMPAIGN",
    "Pitch": "DECIDED_PITCH",
    "MediaPlan": "DECIDED_MEDIAPLAN",
    "Subsidiary": "DECIDED_SUBSIDIARY",
}

# Public canonical list of every rel-table name that represents a
# Decision→target edge. Readers that need to aggregate across all DECIDED
# shards (e.g. the generic precedent query, the KnowledgePulse activity
# strip) import this so they stay in sync with the writer when new shards
# are added. Includes the legacy ``DECIDED_ON`` table for backward
# compatibility on existing graph files (no rows are written there post-
# Phase 1.5, but it remains a valid rel-type label).
DECIDED_REL_NAMES: tuple[str, ...] = (
    "DECIDED_ON",
    *sorted(set(_DECIDED_REL_BY_KIND.values())),
)

# Valid entity kinds extracted from _NODE_TABLES schema (defense-in-depth +
# better error messages than opaque Kuzu parser exceptions).
_VALID_KINDS = frozenset(name for name, _ in _NODE_TABLES)

# Valid relationship type names extracted from _REL_TABLES (uppercase, schema
# canonical form). Mirrors _VALID_KINDS — used by ``link`` to reject unknown
# rels with a clean ValueError before Cypher parsing.
_VALID_RELS = frozenset(name for name, _ in _REL_TABLES)

# Columns added post-Phase-1 to support EntityView age display + ?order=recent.
# `_bootstrap_schema` runs ALTER TABLE ... ADD ... per kind, swallowing the
# "column already exists" error so the migration is idempotent.
_TIMESTAMP_COLUMNS: tuple[str, ...] = ("first_seen_at", "last_seen_at")
_TIMESTAMP_KINDS: tuple[str, ...] = (
    "Person", "Organisation", "Asset", "Money",
    "Decision", "Place", "Period", "Workflow",
    # pitch-e1
    "Brand", "Campaign", "Pitch", "MediaPlan", "Subsidiary",
    # Phase 2: accounts substrate
    "Account", "CostCentre",
    "Insight",
)

# In-process recent-activity counter, keyed by entity kind. 5-minute window.
# Reset on process restart — single-laptop scale, no persistence needed.
_ACTIVITY_WINDOW_SECONDS = 300
_activity_lock = threading.Lock()
_activity_events: dict[str, list[float]] = {}


def _record_activity(kind: str | None) -> None:
    if not kind:
        return
    with _activity_lock:
        bucket = _activity_events.setdefault(kind, [])
        bucket.append(time.time())


def _activity_per_min(kind: str) -> float:
    cutoff = time.time() - _ACTIVITY_WINDOW_SECONDS
    with _activity_lock:
        bucket = _activity_events.get(kind, [])
        # Lazy compaction.
        while bucket and bucket[0] < cutoff:
            bucket.pop(0)
        n = len(bucket)
    return (n / _ACTIVITY_WINDOW_SECONDS) * 60.0

# Bootstrap whitelists: fixture fields matching these column names land as
# top-level node attributes; everything else is JSON-encoded into the
# ``attributes`` blob. Promoted to module-level constants because they are
# the schema contract (mirror of _NODE_TABLES Person / Organisation columns).
_PERSON_COLUMNS = frozenset({
    "name", "email", "role", "market", "department",
    "employed_from", "employed_to",
})
_ORG_COLUMNS = frozenset({"name", "kind", "country", "jurisdiction", "risk_band"})


# ---------------------------------------------------------------------------
# SET-clause builder (shared by upsert / link / record_decision)
# ---------------------------------------------------------------------------


def _build_set_clauses(
    attrs: Mapping[str, Any],
    *,
    prefix: str,
    kind: str | None = None,
    skip_empty: bool = False,
) -> tuple[list[str], dict[str, Any]]:
    """Build per-attr SET-clause fragments and parameter dict for Cypher.

    See module docstring. ``skip_empty=True`` (set by :meth:`EntityGraph.upsert`)
    drops keys whose value is None / "" / [] so a later projection-time upsert
    can NOT blank a field that an earlier seed-time upsert populated. ``link``
    callers leave it False because rel attrs are usually written intentionally
    and the empty-string case is rare there.

    Raises:
        ValueError: if any key fails the :data:`_VALID_ATTR_KEY` regex.
    """
    clauses: list[str] = []
    params: dict[str, Any] = {}
    for i, (key, value) in enumerate(attrs.items()):
        if kind != "Decision" and key in _ATTR_METADATA_KEYS:
            continue
        if skip_empty and (value is None or value == "" or value == []):
            continue
        if not _VALID_ATTR_KEY.match(key):
            raise ValueError(
                f"invalid attr key: {key!r} "
                f"(must match {_VALID_ATTR_KEY.pattern})"
            )
        placeholder = f"attr_{i}"
        clauses.append(f"{prefix}.`{key}` = ${placeholder}")
        params[placeholder] = value
    return clauses, params


# ---------------------------------------------------------------------------
# EntityGraph
# ---------------------------------------------------------------------------


# Phase 4 Task 4.3: known JSON attribute keys promoted to first-class typed
# columns on Decision. Cypher can now query them directly (e.g.
# WHERE d.amount_gbp > 10000) instead of JSON-parsing in Python. Untyped keys
# in the attributes dict still land in the JSON ``attributes`` blob.
KNOWN_DECISION_COLUMN_KEYS: tuple[str, ...] = (
    "amount_gbp",
    "currency_pair",
    "notional_gbp",
    "vendor_id",
    "client_brand",
)


class EntityGraph:
    """Embedded KuzuDB graph for the org's entities + relationships.

    Construction is idempotent — the schema is created with
    ``CREATE … IF NOT EXISTS`` so re-opening an existing graph file is a
    no-op. Optional refs to ``bus`` / ``audit`` / ``governance`` are wired
    via :meth:`attach` after construction so the test harness can pass mocks
    in any order (and so unit tests can construct an :class:`EntityGraph`
    without having to stand up the rest of the substrate).

    All ``Connection.execute`` calls go through ``self._conn_lock`` — Kuzu
    0.6.1 connections are not documented as concurrent-safe, so we serialize
    access when the bus's projection-dispatch path calls from worker threads.

    Atomicity contract: one ``EntityGraph`` instance per ``.kuzu`` file.
    The ``_conn_lock`` serialises read-modify-write within a single instance,
    but two instances pointing at the same file would race. Kuzu 0.6.1
    enforces a single-writer file lock at the OS level, but tests that create
    short-lived instances against the same path must call ``close()`` between
    them (see
    ``test_entity_graph_schema.test_reconstructing_on_same_path_is_idempotent``).
    """

    def __init__(self, db_path: str | os.PathLike[str]) -> None:
        self._path = str(db_path)
        # Kuzu creates a directory at ``db_path`` (the "database file" is
        # actually a small directory tree). Make sure the parent exists.
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self.db = kuzu.Database(self._path)
        self.conn = kuzu.Connection(self.db)
        self._conn_lock = threading.Lock()
        self.bus: Any | None = None
        self.audit: Any | None = None
        self.governance: Any | None = None
        # Per-(workflow_id, phase) locks for record_decision dedupe race
        # protection (PAT-001). The outer map_lock is held only briefly to
        # mutate the dict; the per-key lock is held across the
        # check-then-mint sequence inside record_decision.
        # TODO(Phase 4): on `workflow.completed` events, evict
        # `_decision_lock_map` entries keyed `(workflow_id, _)` — once a
        # workflow is closed, no more decisions can be recorded against
        # it, so the per-`(wf, phase)` locks for that workflow are no
        # longer needed. Until then, the map grows monotonically
        # (negligible at fleet scale: 1000 workflows × 5 phases = 5k
        # Locks ≈ ~600 KB).
        self._decision_lock_map: dict[tuple[str, str], threading.Lock] = {}
        self._decision_lock_map_lock = threading.Lock()
        self._bootstrap_schema()

    # -- lifecycle -------------------------------------------------------

    def close(self) -> None:
        """Release the Kuzu single-writer lock and clean up resources.

        Safe to call multiple times (idempotent). After close(), the graph
        is not usable; a new EntityGraph must be constructed to re-open.
        """
        if self.conn is not None:
            self.conn.close()
            self.conn = None
        if self.db is not None:
            self.db.close()
            self.db = None

    def __enter__(self) -> EntityGraph:
        """Enter context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager, releasing resources."""
        self.close()

    # -- wiring ----------------------------------------------------------

    def attach(self, bus: Any | None = None, audit: Any | None = None, governance: Any | None = None) -> None:
        """Wire optional substrate refs after construction.

        Each ref is applied only if non-None so callers can attach them in
        independent steps (e.g. tests that exercise audit but not bus).
        """
        if bus is not None:
            self.bus = bus
        if audit is not None:
            self.audit = audit
        if governance is not None:
            self.governance = governance

    # -- schema ----------------------------------------------------------

    def _bootstrap_schema(self) -> None:
        """Run the eight node + ten rel ``CREATE … IF NOT EXISTS`` DDL."""
        for _, ddl in _NODE_TABLES:
            with self._conn_lock:
                self.conn.execute(ddl)
        for _, ddl in _REL_TABLES:
            with self._conn_lock:
                self.conn.execute(ddl)
        # Idempotent timestamp-column migration. Kuzu 0.6.1 raises
        # ``RuntimeError("Binder exception: <table> table already has
        # property <col>.")`` when re-adding an existing column; we
        # swallow only that specific shape so a half-upgrade or other
        # DDL failure surfaces loudly instead of being masked.
        for kind in _TIMESTAMP_KINDS:
            for col in _TIMESTAMP_COLUMNS:
                ddl = f"ALTER TABLE {kind} ADD {col} TIMESTAMP"
                try:
                    with self._conn_lock:
                        self.conn.execute(ddl)
                except RuntimeError as exc:
                    if _is_kuzu_already_exists(exc):
                        continue
                    log.warning(
                        "entity_graph bootstrap: unexpected %s on %r: %s",
                        type(exc).__name__, ddl, exc,
                    )
                    raise

    # -- Cypher passthrough (REQ-002) ------------------------------------

    def query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Execute ``cypher`` and return every row as a column-name → value dict."""
        with self._conn_lock:
            result = self.conn.execute(cypher, params or {})
            columns = result.get_column_names()
            rows: list[dict[str, Any]] = []
            while result.has_next():
                row = result.get_next()
                rows.append({col: row[idx] for idx, col in enumerate(columns)})
            return rows

    def query_one(self, cypher: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Execute ``cypher`` and return the first row, or None if empty."""
        with self._conn_lock:
            result = self.conn.execute(cypher, params or {})
            columns = result.get_column_names()
            if not result.has_next():
                return None
            row = result.get_next()
            return {col: row[idx] for idx, col in enumerate(columns)}

    # -- writes (PAT-002) ------------------------------------------------

    def upsert(self, entity: EntityWrite) -> None:
        """Idempotently upsert ``entity`` and emit ``entity.upserted``.

        Cypher MERGE creates the node if it doesn't exist and matches it
        otherwise; the SET clause then assigns attrs + the deduped union
        of ``source_workflows`` (PAT-004 — insertion order preserved,
        existing workflows kept on subsequent upserts so we accumulate
        provenance over an entity's lifetime).

        We compute the union in Python under ``self._conn_lock`` rather
        than in Cypher so the merge semantics stay obvious and easy to
        unit-test. The whole read-then-write cycle holds the single
        connection lock, so two threads upserting the same id can't
        clobber each other's source_workflows additions.

        Bus + audit emissions are guarded by :meth:`attach` having been
        called — when wiring is None this is a pure write with no
        downstream side effects (lets unit tests construct a bare graph).
        """
        # Validate entity kind against known schema.
        if entity.kind not in _VALID_KINDS:
            raise ValueError(
                f"unknown entity kind: {entity.kind!r} "
                f"(expected one of {sorted(_VALID_KINDS)})"
            )

        with self._conn_lock:
            # Only attempt to read/merge source_workflows for kinds that have it.
            has_source_workflows = entity.kind in {
                "Person", "Organisation", "Asset", "Money"
            }

            params: dict[str, Any] = {
                "id": entity.id,
            }
            set_clauses: list[str] = []

            if has_source_workflows:
                existing_result = self.conn.execute(
                    f"MATCH (n:{entity.kind}) WHERE n.id = $id "
                    "RETURN n.source_workflows AS sw",
                    {"id": entity.id},
                )
                existing_sw: list[str] = []
                if existing_result.has_next():
                    row = existing_result.get_next()
                    if row[0] is not None:
                        existing_sw = list(row[0])

                merged_sw = list(existing_sw)
                # O(n*m) — both n (existing) and m (incoming) stay small (<~50 workflows
                # per entity at demo scale); upgrade to OrderedDict if a hot entity ever
                # accumulates hundreds of source_workflows.
                for sw in entity.source_workflows:
                    if sw not in merged_sw:
                        merged_sw.append(sw)

                params["sw"] = merged_sw
                set_clauses.append("n.source_workflows = $sw")

            # Kuzu 0.6.1 does NOT support the ``SET n += $map`` map-merge
            # form (parser rejects it). The shared :func:`_build_set_clauses`
            # helper binds each attr to its own ``$attr_<i>`` placeholder
            # and emits one ``n.`<key>` = $attr_<i>`` clause per entry,
            # while skipping the ``workflow_id`` / ``source_event``
            # projection-metadata keys for non-Decision kinds (where they
            # aren't real columns).
            attr_clauses, attr_params = _build_set_clauses(
                entity.attrs, prefix="n", kind=entity.kind, skip_empty=True,
            )
            set_clauses.extend(attr_clauses)
            params.update(attr_params)

            # first/last_seen_at: write last_seen_at on every upsert; only
            # write first_seen_at when currently NULL (i.e. on create).
            # Kuzu 0.6.1 has no COALESCE-on-MERGE so we read the existing
            # value and conditionally include the SET clause.
            now_ts = datetime.utcnow()
            params["last_seen_at"] = now_ts
            set_clauses.append("n.last_seen_at = $last_seen_at")
            try:
                existing = self.conn.execute(
                    f"MATCH (n:{entity.kind}) WHERE n.id = $id "
                    "RETURN n.first_seen_at AS fs",
                    {"id": entity.id},
                )
                first_existing = None
                if existing.has_next():
                    first_existing = existing.get_next()[0]
                if first_existing is None:
                    params["first_seen_at"] = now_ts
                    set_clauses.append("n.first_seen_at = $first_seen_at")
            except RuntimeError as exc:
                # Tolerate the specific case where ``first_seen_at`` has
                # not yet been added to this kind's node table (the
                # migration runs in :meth:`_bootstrap_schema` but a
                # caller may have constructed the EntityGraph against
                # a pre-migration db file). Anything else is a real
                # failure and must surface.
                if not _is_kuzu_missing_property(exc):
                    log.warning(
                        "entity_graph upsert: unexpected %s reading "
                        "first_seen_at on kind=%r: %s",
                        type(exc).__name__, entity.kind, exc,
                    )
                    raise

            self.conn.execute(
                f"MERGE (n:{entity.kind} {{id: $id}}) SET "
                + ", ".join(set_clauses),
                params,
            )

        # Side-effects outside the conn lock: the bus / audit have their
        # own locks and we don't want to invert the lock order.
        if self.bus is not None:
            self.bus.emit(
                FleetEvent(
                    type="entity.upserted",
                    workflow_id=entity.attrs.get("workflow_id"),
                    entity_id=entity.id,
                    kind=entity.kind,
                )
            )
        _record_activity(entity.kind)
        if self.audit is not None:
            self.audit.log(
                "entity.upserted",
                {
                    "id": entity.id,
                    "kind": entity.kind,
                    "workflow_id": entity.attrs.get("workflow_id"),
                    "source_workflows": list(entity.source_workflows),
                },
            )

    def link(self, src_id: str, rel: str, dst_id: str, **attrs: Any) -> None:
        """Idempotently MERGE a relationship ``(src_id)-[rel]->(dst_id)``.

        ``rel`` may be passed in either case — it is normalised to the
        uppercase schema form (``"employed_by"`` and ``"EMPLOYED_BY"`` both
        resolve to the ``EMPLOYED_BY`` rel table) and validated against
        :data:`_VALID_RELS` before any Cypher is built. Unknown rels raise
        a clean :class:`ValueError` mirroring the ``upsert`` kind whitelist.

        ``**attrs`` lands as named properties on the rel record, with the
        same key validation as :meth:`upsert` (each key must match
        :data:`_VALID_ATTR_KEY`). Kuzu 0.6.1 does NOT support the
        ``SET r += $map`` map-merge form (parser rejects it) so each attr
        is bound to its own ``$attr_<i>`` placeholder and emitted as a
        per-key ``r.`<key>` = $attr_<i>`` clause.

        The MATCH→MERGE pattern uses untyped node patterns
        (``MATCH (a), (b) WHERE a.id = $src AND b.id = $dst``) — the rel
        type on the MERGE side constrains acceptable (a, b) pairs through
        the schema's ``FROM …  TO …`` declaration. If either id is missing
        the MATCH returns no rows and MERGE silently no-ops; we treat that
        as caller responsibility (PAT-002 projections always upsert nodes
        before they link them, so a missing-id link would mask a projection
        bug somewhere upstream — but raising here would force every test
        to seed both endpoints first, which the bus-emission tests don't
        need to). Re-running the same ``(src_id, rel, dst_id)`` triple is
        idempotent: MERGE matches the existing rel and SET updates attrs.

        Bus + audit emissions are guarded by :meth:`attach` having been
        called and run OUTSIDE the connection lock, mirroring
        :meth:`upsert`. The emitted FleetEvent and audit details carry the
        normalised uppercase ``rel`` so downstream consumers see a single
        canonical form regardless of how the caller spelled it.
        """
        rel_upper = rel.upper()
        if rel_upper not in _VALID_RELS:
            raise ValueError(
                f"unknown rel: {rel!r} "
                f"(expected one of {sorted(_VALID_RELS)})"
            )

        if "decided_at" not in attrs:
            attrs["decided_at"] = datetime.utcnow()

        params: dict[str, Any] = {"src": src_id, "dst": dst_id}
        set_clauses, attr_params = _build_set_clauses(attrs, prefix="r", kind=None)
        params.update(attr_params)

        cypher = (
            f"MATCH (a), (b) WHERE a.id = $src AND b.id = $dst "
            f"MERGE (a)-[r:{rel_upper}]->(b)"
        )
        if set_clauses:
            cypher += " SET " + ", ".join(set_clauses)

        with self._conn_lock:
            self.conn.execute(cypher, params)

        # Side-effects outside the conn lock: the bus / audit have their
        # own locks and we don't want to invert the lock order.
        if self.bus is not None:
            self.bus.emit(
                FleetEvent(
                    type="entity.linked",
                    src_id=src_id,
                    dst_id=dst_id,
                    rel=rel_upper,
                )
            )
        _record_activity(rel_upper)
        if self.audit is not None:
            self.audit.log(
                "entity.linked",
                {
                    "src_id": src_id,
                    "dst_id": dst_id,
                    "rel": rel_upper,
                },
            )

    # -- decisions (TASK-007 / PAT-001) ----------------------------------

    def record_decision(
        self,
        workflow_id: str,
        phase: str,
        persona_role: str,
        verdict: str,
        reason: str,
        decided_at: datetime,
        source_event: str,
        attributes: dict[str, Any],
        decided_on: tuple[str, ...] = (),
    ) -> str:
        """Mint (or dedupe) a Decision node, returning its canonical ULID.

        PAT-001 contract: the natural triple ``(workflow_id, phase,
        persona_role)`` is the dedupe key. Two calls with the same triple
        return the SAME ULID; the second call is a silent no-op on the
        graph (first writer wins, no overwrite of attrs) and emits only a
        ``decision.deduped`` audit entry — the bus already saw the
        original ``decision.recorded`` event when the row was first
        minted, so emitting a second bus event would be misleading.

        Race protection: a per-``(workflow_id, phase)`` :class:`threading.Lock`
        serialises the check-then-mint window so two threads racing on the
        same triple converge on a single ULID. The lock map is mutated
        under a separate ``_decision_lock_map_lock`` (held only briefly).
        Lock order is always: per-key decision lock FIRST, then
        ``self._conn_lock`` SECOND inside the Cypher calls.

        On mint: writes the Decision node with a CREATE (we just confirmed
        no row exists, so MERGE's match arm is dead weight), then for each
        ``did`` in ``decided_on`` writes a ``DECIDED_ON`` rel via
        :meth:`link` (which silently no-ops if the target id is missing —
        consistent with the upsert/link contract that callers seed nodes
        first). Both the bus ``decision.recorded`` event and the audit
        entry are emitted OUTSIDE both locks.

        Event ordering: ``decision.recorded`` is emitted IMMEDIATELY after
        the Decision node CREATE succeeds, BEFORE any ``decided_on`` rels
        are written. If a subsequent :meth:`link` call raises (e.g. for an
        unknown ``decided_on`` id), the Decision row + the
        ``decision.recorded`` event are still consistent — consumers can
        re-query the graph to discover which rels landed. This ordering
        avoids the failure mode where a partial-link failure permanently
        masks the mint event from the bus (since a retry would hit the
        dedupe path which is bus-silent).

        ``attributes`` is JSON-encoded into the ``Decision.attributes``
        STRING column (it's the "everything else" blob; the fixed columns
        — ``workflow_id``, ``phase``, ``persona_role``, ``verdict``,
        ``reason``, ``decided_at``, ``source_event`` — are written
        explicitly). ``json.dumps`` is called with ``default=str`` so
        non-JSON-native values (notably ``datetime``) are coerced to a
        string rather than raising ``TypeError`` — fleet domain
        projections will routinely carry timestamps in ``attributes``.
        """
        key = (workflow_id, phase)
        with self._decision_lock_map_lock:
            decision_lock = self._decision_lock_map.setdefault(key, threading.Lock())

        with decision_lock:
            existing = self.query_one(
                "MATCH (d:Decision) WHERE d.workflow_id = $wf "
                "AND d.phase = $ph AND d.persona_role = $pr "
                "RETURN d.id AS id",
                {"wf": workflow_id, "ph": phase, "pr": persona_role},
            )

            if existing is not None:
                decision_id = existing["id"]
                minted = False
            else:
                decision_id = _ulid()
                minted = True
                # Phase 4 Task 4.3: promote known JSON attribute keys onto
                # first-class typed columns. Untyped keys still land in the
                # JSON ``attributes`` blob below. Skip empty/None values:
                # Kuzu strict-types DOUBLE columns reject '' and STRING
                # columns rejecting None when the column is non-nullable
                # would surface here, so guard explicitly.
                attrs_dict = attributes or {}
                extra_cols: list[str] = []
                extra_params: dict[str, Any] = {}
                for key in KNOWN_DECISION_COLUMN_KEYS:
                    val = attrs_dict.get(key)
                    if val is None or val == "":
                        continue
                    extra_cols.append(f"{key}: ${key}")
                    extra_params[key] = val
                extra_clause = (", " + ", ".join(extra_cols)) if extra_cols else ""
                with self._conn_lock:
                    self.conn.execute(
                        "CREATE (d:Decision {"
                        "id: $id, workflow_id: $wf, phase: $ph, "
                        "persona_role: $pr, verdict: $verdict, reason: $reason, "
                        "decided_at: $decided_at, source_event: $source_event, "
                        "attributes: $attributes"
                        f"{extra_clause}"
                        "})",
                        {
                            "id": decision_id,
                            "wf": workflow_id,
                            "ph": phase,
                            "pr": persona_role,
                            "verdict": verdict,
                            "reason": reason,
                            "decided_at": decided_at,
                            "source_event": source_event,
                            "attributes": json.dumps(attrs_dict, default=str),
                            **extra_params,
                        },
                    )

        # Side-effects outside both locks (mirrors upsert/link).
        if minted:
            # TOUCHED: link the deciding persona's Person node (if
            # ``persona_role`` IS a Person id) to the Decision. Forward-
            # compatible with the d2 authority matrix (which will map
            # persona_role → person id); for now only direct ``PERSON-…``
            # ids land an edge. ``link()`` silently no-ops if the Person
            # node doesn't exist, so this is safe under stress.
            if persona_role.startswith("PERSON-"):
                try:
                    self.link(persona_role, "TOUCHED", decision_id, role=persona_role)
                except Exception:  # pragma: no cover — defensive
                    log.exception(
                        "record_decision: TOUCHED link failed "
                        "(persona_role=%s decision_id=%s)",
                        persona_role, decision_id,
                    )
            else:
                log.debug(
                    "record_decision: skipping TOUCHED edge "
                    "(persona_role=%r is not a Person id)",
                    persona_role,
                )
            # Emit decision.recorded BEFORE writing decided_on rels: if a
            # link() call raises, the Decision row is already committed
            # but a retry would hit the bus-silent dedupe path and the
            # mint event would be permanently lost. Emitting first means
            # consumers can re-query the graph to reconcile any missing
            # rels.
            if self.bus is not None:
                self.bus.emit(
                    FleetEvent(
                        type="decision.recorded",
                        workflow_id=workflow_id,
                        decision_id=decision_id,
                        phase=phase,
                        persona_role=persona_role,
                        verdict=verdict,
                        decided_at=str(decided_at),
                    )
                )
            if self.audit is not None:
                self.audit.log(
                    "decision.recorded",
                    {
                        "decision_id": decision_id,
                        "workflow_id": workflow_id,
                        "phase": phase,
                        "persona_role": persona_role,
                        "verdict": verdict,
                    },
                )

            for did in decided_on:
                # Look up the target's node kind via Kuzu's label-less
                # match (supported in 0.6.1) so we can route to the right
                # DECIDED_<KIND> rel table. ``_label`` is Kuzu's synthetic
                # label column. If the node doesn't exist (yet), or its
                # kind isn't in the DECIDED routing table, log + skip —
                # ``link()``'s old silent-no-op behaviour was masking
                # missing rels and made decisions look story-less.
                target_kind: str | None = None
                try:
                    row = self.query_one(
                        "MATCH (n {id: $id}) RETURN label(n) AS k LIMIT 1",
                        {"id": did},
                    )
                    if row is not None:
                        target_kind = row.get("k")
                except Exception:  # pragma: no cover — defensive
                    log.exception(
                        "record_decision: kind lookup failed for decided_on id=%s",
                        did,
                    )
                    continue
                rel_name = _DECIDED_REL_BY_KIND.get(target_kind or "")
                if rel_name is None:
                    log.debug(
                        "record_decision: skipping decided_on id=%s "
                        "(target kind=%r has no DECIDED_<KIND> mapping)",
                        did, target_kind,
                    )
                    continue
                # link() handles validation, locking, and silent no-op on
                # missing endpoints; it also emits its own entity.linked
                # bus + audit pair, which is consistent with the standard
                # rel-write contract.
                self.link(decision_id, rel_name, did)
        else:
            # Dedupe hit: audit only, no bus emission (bus already saw
            # the original mint). Include the attempted-but-rejected
            # verdict/reason/source_event so an operator debugging "why
            # didn't my second submission stick?" can see the diff
            # against the existing decision.
            if self.audit is not None:
                self.audit.log(
                    "decision.deduped",
                    {
                        "decision_id": decision_id,
                        "workflow_id": workflow_id,
                        "phase": phase,
                        "persona_role": persona_role,
                        "attempted_verdict": verdict,
                        "attempted_reason": reason,
                        "attempted_source_event": source_event,
                    },
                )

        return decision_id

    # -- reads (TASK-006) ------------------------------------------------

    def get(self, id: str) -> dict[str, Any] | None:
        """Fetch a single node by ``id`` across all node kinds.

        Kuzu 0.6.1 supports label-less ``MATCH ({id: $id})`` so a single
        query suffices — the returned node dict carries a ``_label`` field
        indicating its kind. Returns ``None`` if no node has that id.

        If id collisions across kinds occur (a contract violation — ids are
        per-kind prefixed by convention, e.g. ``PERSON-EMP-0001``,
        ``ORG-vendor-acme``), returns whichever row Kuzu picks first; this
        method does not detect or warn.
        """
        row = self.query_one(
            "MATCH (n {id: $id}) RETURN n LIMIT 1",
            {"id": id},
        )
        if row is None:
            return None
        result = row["n"]
        if self.bus is not None and result is not None:
            try:
                from api.shared.events import FleetEvent
                self.bus.emit(FleetEvent(
                    type="entity.read",
                    entity_id=id,
                    kind=result.get("kind") if isinstance(result, dict) else None,
                ))
            except Exception:
                pass
        if isinstance(result, dict):
            _record_activity(result.get("_label"))
        return result

    def by_type(self, kind: str, **filters: Any) -> list[dict[str, Any]]:
        """Return every node of ``kind``, optionally narrowed by ``**filters``.

        Each filter key is validated against :data:`_VALID_ATTR_KEY` so the
        WHERE clause built by string interpolation can never carry an
        attacker-controlled identifier (defense-in-depth — projection
        callers already build EntityWrites with safe keys, but this method
        is also called from MCP tools where the key origin is less obvious).
        """
        if kind not in _VALID_KINDS:
            raise ValueError(
                f"unknown entity kind: {kind!r} "
                f"(expected one of {sorted(_VALID_KINDS)})"
            )

        where_clauses: list[str] = []
        params: dict[str, Any] = {}
        for idx, (key, value) in enumerate(filters.items()):
            if not _VALID_ATTR_KEY.match(key):
                raise ValueError(
                    f"invalid filter key: {key!r} "
                    f"(must match {_VALID_ATTR_KEY.pattern})"
                )
            placeholder = f"f_{idx}"
            where_clauses.append(f"n.`{key}` = ${placeholder}")
            params[placeholder] = value

        cypher = f"MATCH (n:{kind})"
        if where_clauses:
            cypher += " WHERE " + " AND ".join(where_clauses)
        cypher += " RETURN n"
        if self.bus is not None:
            try:
                from api.shared.events import FleetEvent
                self.bus.emit(FleetEvent(
                    type="entity.read",
                    kind=kind,
                ))
            except Exception:
                pass
        _record_activity(kind)
        return [row["n"] for row in self.query(cypher, params)]

    def linked(
        self,
        id: str,
        rel: str | None = None,
        *,
        direction: str = "out",
    ) -> list[dict[str, Any]]:
        """Return neighbours of ``id``, optionally filtered by ``rel``.

        Each result row is a dict ``{"node": <neighbour-dict>, "rel":
        "<REL_TYPE>", "direction": "out|in"}`` — ``rel`` is the canonical
        uppercase rel-table name as reported by Kuzu's ``label(r)`` function
        (Kuzu 0.6.1 does not provide a ``type(r)``; ``label(r)`` is the
        documented equivalent for rel records).

        ``rel`` is normalised to uppercase (mirroring :meth:`link`) and
        validated against :data:`_VALID_RELS` when given. ``rel=None``
        returns rels of any type via Kuzu's label-less rel pattern.

        ``direction`` controls which edges are followed:
        - ``"out"`` (default): outgoing edges from ``id``.
        - ``"in"``: incoming edges (other nodes pointing at ``id``).
        - ``"both"``: union of outgoing and incoming.

        The default is ``"out"`` for backward compatibility, but most UI
        traversals want ``"both"`` because the entity-graph schema is
        directional and many useful kinds (Period, Place, Money,
        Organisation) only have incoming edges.
        """
        direction = direction.lower()
        if direction not in {"out", "in", "both"}:
            raise ValueError(
                f"unknown direction: {direction!r} "
                "(expected 'out', 'in', or 'both')"
            )

        params: dict[str, Any] = {"id": id}
        if rel is not None:
            rel_upper = rel.upper()
            if rel_upper not in _VALID_RELS:
                raise ValueError(
                    f"unknown rel: {rel!r} "
                    f"(expected one of {sorted(_VALID_RELS)})"
                )
            rel_label = f":{rel_upper}"
        else:
            rel_label = ""

        rows: list[dict[str, Any]] = []
        if direction in {"out", "both"}:
            cypher_out = (
                f"MATCH ({{id: $id}})-[r{rel_label}]->(n) "
                "RETURN n, label(r) AS rel"
            )
            for row in self.query(cypher_out, params):
                rows.append({
                    "node": row["n"],
                    "rel": row["rel"],
                    "direction": "out",
                })
        if direction in {"in", "both"}:
            cypher_in = (
                f"MATCH ({{id: $id}})<-[r{rel_label}]-(n) "
                "RETURN n, label(r) AS rel"
            )
            for row in self.query(cypher_in, params):
                rows.append({
                    "node": row["n"],
                    "rel": row["rel"],
                    "direction": "in",
                })
        return rows

    def count_by_kind(self) -> dict[str, int]:
        """Return per-kind node counts as a dict keyed by kind name."""
        out: dict[str, int] = {}
        for kind in _VALID_KINDS:
            try:
                rows = self.query(f"MATCH (n:{kind}) RETURN count(*) AS c")
                out[kind] = int(rows[0]["c"]) if rows else 0
            except Exception:
                out[kind] = 0
        return out

    def rel_counts(self) -> list[dict[str, Any]]:
        """Return live counts per (src_kind, rel, dst_kind) triple.

        Uses ``_REL_TABLES`` to know what tuples exist; runs one count
        Cypher per rel. Cheap at demo scale (10 rels × <1ms each).
        """
        out: list[dict[str, Any]] = []
        for rel_name, ddl in _REL_TABLES:
            try:
                from_idx = ddl.index("FROM ") + len("FROM ")
                to_idx = ddl.index(" TO ", from_idx)
                src_kind = ddl[from_idx:to_idx].strip()
                tail = ddl[to_idx + len(" TO "):]
                end_tokens = [tail.find(c) for c in (",", ")", "\n") if tail.find(c) >= 0]
                end_idx = min(end_tokens) if end_tokens else len(tail)
                dst_kind = tail[:end_idx].strip()
            except Exception:
                continue
            try:
                rows = self.query(
                    f"MATCH (a:{src_kind})-[r:{rel_name}]->(b:{dst_kind}) "
                    f"RETURN count(*) AS c"
                )
                cnt = int(rows[0]["c"]) if rows else 0
            except Exception:
                cnt = 0
            out.append({
                "rel": rel_name,
                "from_kind": src_kind,
                "to_kind": dst_kind,
                "count": cnt,
            })
        return out

    def recent_activity_per_min(self, kind: str) -> float:
        """Return the rolling 5-minute activity rate for ``kind``."""
        return _activity_per_min(kind)

    def cross_domain_top(self, limit: int = 5) -> list[dict[str, Any]]:
        """Top entities by distinct workflow-type count derived from source_workflows.

        Streams the kinds that declare ``source_workflows`` (Person /
        Organisation / Asset / Money) and computes distinct workflow-type
        counts in Python — Kuzu 0.6.1 lacks the list-comprehension
        primitives needed to do this in a single Cypher query. Cheap at
        demo scale (< few thousand rows).
        """
        candidates: list[dict[str, Any]] = []
        for kind in ("Person", "Organisation", "Asset", "Money"):
            try:
                rows = self.by_type(kind)
            except Exception:
                continue
            for row in rows:
                sw = row.get("source_workflows") or []
                if not sw:
                    continue
                types = {str(w).split("-")[0] for w in sw if isinstance(w, str)}
                candidates.append({
                    "id": row.get("id"),
                    "kind": kind,
                    "workflow_count": len(sw),
                    "workflow_types_count": len(types),
                })
        candidates.sort(
            key=lambda r: (r["workflow_types_count"], r["workflow_count"]),
            reverse=True,
        )
        return candidates[:limit]

    def touched_by(self, workflow_id: str) -> list[dict[str, Any]]:
        """Return every entity whose ``source_workflows`` contains ``workflow_id``.

        Uses Kuzu's label-less ``MATCH (n)`` plus ``$wid IN n.source_workflows``
        — the smoke tests confirmed Kuzu 0.6.1 silently skips kinds that
        don't declare a ``source_workflows`` column (Place/Period/Workflow/
        Decision), so this single query covers all eight kinds without
        having to UNION them by hand.

        Decisions are intentionally excluded — their workflow provenance
        lives on ``Decision.workflow_id`` (a scalar column), not on a
        ``source_workflows`` array. To find decisions related to a
        workflow, use ``by_type('Decision', workflow_id=...)``.
        """
        rows = self.query(
            "MATCH (n) WHERE $wid IN n.source_workflows RETURN n",
            {"wid": workflow_id},
        )
        return [row["n"] for row in rows]

    # -- bootstrap (TASK-008) -------------------------------------------

    def bootstrap_from_fixtures(
        self,
        employees_path: Path,
        vendors_path: Path,
        agencies_path: Path,
    ) -> dict[str, int]:
        """One-shot population of Persons + Organisations from JSON fixtures.

        Reads each file, maps every record to an :class:`EntityWrite`, and
        feeds it through :meth:`upsert` with ``source_workflows=("bootstrap",)``.
        Employees become ``Person`` nodes; vendors and agencies become
        ``Organisation`` nodes with ``kind="vendor"`` / ``kind="agency"``
        respectively (per blueprint §2 schema).

        Per-row id-prefix convention: bare fixture ids (``"EMP-0001"``,
        ``"V-001"``, ``"Ogilvy-US"``) are namespaced with ``PERSON-`` /
        ``ORG-`` to keep ids globally unique across kinds. Already-prefixed
        ids are passed through as-is.

        Schema fidelity: only fields that match a column on the target
        node table land as top-level ``attrs`` keys; the rest are
        JSON-encoded (``sort_keys=True, default=str`` — consistent with
        :meth:`record_decision`, so future fixtures with ``date`` /
        ``datetime`` / ``Decimal`` values won't crash bootstrap) into the
        ``attributes`` STRING column so no fixture information is dropped.

        Agency name repair (Option A): ``agencies.json`` rows ship without
        a ``name`` field — only ``{id, market, region}``. To prevent silent
        ``name=NULL`` fidelity loss, the bare fixture id is used as the
        default ``name`` whenever no explicit ``name`` is supplied. The bare
        id (e.g. ``"Ogilvy-US"``) is the human-readable identifier in the
        agency fixture's case.

        Returns ``{"persons": N, "organisations": M}`` where N and M count
        every ``upsert`` call (not "unique entities"). The method is
        idempotent because :meth:`upsert` MERGE-s and dedupes
        ``source_workflows``, so re-running it returns the same counts and
        leaves the graph unchanged. Documented consequence: a fixture
        containing duplicate ids inflates the returned count while
        ``by_type`` reports only the unique entities (last write wins).

        A single ``audit.log("entity.bootstrap.completed", {"counts": ...})``
        is emitted at the end (not per-record) to keep the audit log
        readable; ``upsert`` still emits its own ``entity.upserted`` event
        per row, which is the right granularity for downstream subscribers.

        Malformed fixture rows (missing required ``id`` field) raise
        ``KeyError``, halting the bootstrap mid-iteration. The graph is
        left in a partial state; re-running bootstrap from the corrected
        fixture is safe (upsert is idempotent).

        Raises:
            FileNotFoundError: if any of the three fixture paths is missing.
            KeyError: if any fixture row is missing the required ``id`` key.
        """
        employees = json.loads(Path(employees_path).read_text())
        vendors = json.loads(Path(vendors_path).read_text())
        agencies = json.loads(Path(agencies_path).read_text())

        persons_count = 0
        for row in employees:
            self.upsert(self._bootstrap_entity(
                row, kind="Person", prefix="PERSON-", columns=_PERSON_COLUMNS,
            ))
            persons_count += 1

        organisations_count = 0
        for row in vendors:
            self.upsert(self._bootstrap_entity(
                row, kind="Organisation", prefix="ORG-",
                columns=_ORG_COLUMNS, extra_attrs={"kind": "vendor"},
            ))
            organisations_count += 1
        for row in agencies:
            self.upsert(self._bootstrap_entity(
                row, kind="Organisation", prefix="ORG-",
                columns=_ORG_COLUMNS, extra_attrs={"kind": "agency"},
            ))
            organisations_count += 1

        counts = {"persons": persons_count, "organisations": organisations_count}
        if self.audit is not None:
            self.audit.log("entity.bootstrap.completed", {"counts": counts})
        return counts

    def _bootstrap_entity(
        self,
        row: dict[str, Any],
        *,
        kind: str,
        prefix: str,
        columns: frozenset[str],
        extra_attrs: dict[str, Any] | None = None,
    ) -> EntityWrite:
        """Build an :class:`EntityWrite` from a fixture row.

        - Whitelisted ``columns`` map to top-level ``attrs`` keys.
        - Residual fields are JSON-encoded into ``attrs["attributes"]``
          (``sort_keys=True, default=str``).
        - ``id`` gets ``prefix`` if not already prefixed.
        - ``extra_attrs`` are merged into ``attrs`` after column extraction
          (used by Org rows to inject ``{"kind": "vendor"|"agency"}``);
          they take precedence over any same-named fixture field.
        - If no ``name`` field is supplied (or it is falsy) and ``"name"``
          is in ``columns``, the bare fixture id is used as the default —
          locks the agency-name fidelity contract (agencies.json has no
          name field).

        Raises:
            KeyError: if ``row`` is missing the required ``"id"`` key.
        """
        raw_id = row["id"]
        eid = raw_id if raw_id.startswith(prefix) else f"{prefix}{raw_id}"
        attrs: dict[str, Any] = {}
        extra: dict[str, Any] = {}
        for k, v in row.items():
            if k == "id":
                continue
            if k in columns:
                attrs[k] = v
            else:
                extra[k] = v
        if extra_attrs:
            attrs.update(extra_attrs)
        if "name" in columns and not attrs.get("name"):
            attrs["name"] = raw_id
        if extra:
            attrs["attributes"] = json.dumps(extra, sort_keys=True, default=str)
        return EntityWrite(
            kind=kind, id=eid, attrs=attrs,
            source_workflows=("bootstrap",),
        )
