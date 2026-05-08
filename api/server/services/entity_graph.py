"""Embedded KuzuDB-backed entity graph (Plane 1 of the Agentic Org Blueprint).

This module is the persistence + query layer for the org's *nouns* — Person,
Organisation, Asset, Money, Decision, Place, Period, Workflow — and their
relationships. Future phases bind to the public API on :class:`EntityGraph`:

* Phase 1 ``EntityReflector`` (a bus subscriber) calls ``upsert`` / ``link`` /
  ``record_decision`` from a per-domain projection function.
* Phase 3 wraps the Cypher passthrough helpers (:meth:`EntityGraph.query`,
  :meth:`EntityGraph.query_one`, :meth:`EntityGraph.find_by_pattern`) as MCP
  tools (``query_entity``, ``find_entities``, ``query_recent_decisions``).
* Phase 4 traverses ``Decision`` nodes via the same passthrough helpers
  (``query_precedents``).

Schema is bootstrapped via ``CREATE … IF NOT EXISTS`` on first construction
and matches the blueprint §2 Plane 1 schema block at
``docs/agentic-org-blueprint.md`` lines ~180–236, plus the §3 ``Workflow``
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

The behavioural methods (``upsert``, ``link``, ``get``, ``by_type``,
``linked``, ``touched_by``, ``record_decision``) land in TASK-004 and beyond.
"""
from __future__ import annotations

import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import kuzu

from api.server.state import _PORTAL_DATA_DIR  # noqa: F401  re-exported for convenience


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
)

_REL_TABLES: tuple[tuple[str, str], ...] = (
    ("EMPLOYED_BY", "CREATE REL TABLE IF NOT EXISTS EMPLOYED_BY (FROM Person TO Organisation, role STRING, since DATE)"),
    ("MANAGES", "CREATE REL TABLE IF NOT EXISTS MANAGES (FROM Person TO Person, since DATE)"),
    ("OWNS", "CREATE REL TABLE IF NOT EXISTS OWNS (FROM Person TO Asset)"),
    ("TRANSACTS", "CREATE REL TABLE IF NOT EXISTS TRANSACTS (FROM Person TO Money, role STRING)"),
    ("BELONGS_TO", "CREATE REL TABLE IF NOT EXISTS BELONGS_TO (FROM Money TO Period)"),
    ("LOCATED_IN", "CREATE REL TABLE IF NOT EXISTS LOCATED_IN (FROM Person TO Place)"),
    ("DECIDED_ON", "CREATE REL TABLE IF NOT EXISTS DECIDED_ON (FROM Decision TO Person)"),
    ("PRECEDENT_OF", "CREATE REL TABLE IF NOT EXISTS PRECEDENT_OF (FROM Decision TO Decision)"),
    ("TOUCHED", "CREATE REL TABLE IF NOT EXISTS TOUCHED (FROM Person TO Decision, role STRING)"),
    ("SUB_WORKFLOW_OF", "CREATE REL TABLE IF NOT EXISTS SUB_WORKFLOW_OF (FROM Workflow TO Workflow, spawned_at TIMESTAMP)"),
)


# ---------------------------------------------------------------------------
# EntityGraph
# ---------------------------------------------------------------------------


class EntityGraph:
    """Embedded KuzuDB graph for the org's entities + relationships.

    Construction is idempotent — the schema is created with
    ``CREATE … IF NOT EXISTS`` so re-opening an existing graph file is a
    no-op. Optional refs to ``bus`` / ``audit`` / ``governance`` are wired
    via :meth:`attach` after construction so the test harness can pass mocks
    in any order (and so unit tests can construct an :class:`EntityGraph`
    without having to stand up the rest of the substrate).
    """

    def __init__(self, db_path: str | os.PathLike[str]) -> None:
        self._path = str(db_path)
        # Kuzu creates a directory at ``db_path`` (the "database file" is
        # actually a small directory tree). Make sure the parent exists.
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self.db = kuzu.Database(self._path)
        self.conn = kuzu.Connection(self.db)
        self.bus: Any | None = None
        self.audit: Any | None = None
        self.governance: Any | None = None
        self._bootstrap_schema()

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
            self.conn.execute(ddl)
        for _, ddl in _REL_TABLES:
            self.conn.execute(ddl)

    # -- Cypher passthrough (REQ-002) ------------------------------------

    def query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Execute ``cypher`` and return every row as a column-name → value dict."""
        result = self.conn.execute(cypher, params or {})
        columns = result.get_column_names()
        rows: list[dict[str, Any]] = []
        while result.has_next():
            row = result.get_next()
            rows.append({col: row[idx] for idx, col in enumerate(columns)})
        return rows

    def query_one(self, cypher: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Execute ``cypher`` and return the first row, or None if empty."""
        result = self.conn.execute(cypher, params or {})
        columns = result.get_column_names()
        if not result.has_next():
            return None
        row = result.get_next()
        return {col: row[idx] for idx, col in enumerate(columns)}

    def find_by_pattern(
        self,
        pattern: str,
        params: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Run ``pattern`` as a Cypher query, appending ``LIMIT`` if missing.

        ``pattern`` is expected to be a complete ``MATCH … RETURN …``
        statement. If it does not already contain a ``LIMIT`` clause
        (case-insensitive), ``LIMIT <limit>`` is appended. The limit is
        inlined as an integer literal because Kuzu 0.6.1 does not accept
        parameter substitution inside ``LIMIT``.
        """
        # Cheap case-insensitive scan — good enough; projection-supplied
        # patterns are short. Tokenising the Cypher would be overkill.
        if "limit" not in pattern.lower():
            pattern = f"{pattern.rstrip().rstrip(';')} LIMIT {int(limit)}"
        return self.query(pattern, params)
