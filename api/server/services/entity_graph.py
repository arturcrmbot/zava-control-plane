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

The remaining behavioural method (``record_decision``) lands in TASK-007.
"""
from __future__ import annotations

import json
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

# Regex for detecting LIMIT clauses (word-boundary match to avoid false positives
# in identifiers like 'limited'). Precompiled for efficiency.
_LIMIT_PATTERN = re.compile(r"\blimit\b", re.IGNORECASE)

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

# Valid entity kinds extracted from _NODE_TABLES schema (defense-in-depth +
# better error messages than opaque Kuzu parser exceptions).
_VALID_KINDS = frozenset(name for name, _ in _NODE_TABLES)

# Valid relationship type names extracted from _REL_TABLES (uppercase, schema
# canonical form). Mirrors _VALID_KINDS — used by ``link`` to reject unknown
# rels with a clean ValueError before Cypher parsing.
_VALID_RELS = frozenset(name for name, _ in _REL_TABLES)


# ---------------------------------------------------------------------------
# SET-clause builder (shared by upsert / link / record_decision)
# ---------------------------------------------------------------------------


def _build_set_clauses(
    attrs: Mapping[str, Any],
    *,
    prefix: str,
    kind: str | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """Build per-attr SET-clause fragments and parameter dict for Cypher.

    - Validates every key against :data:`_VALID_ATTR_KEY` (raises
      :class:`ValueError` on failure).
    - When ``kind != "Decision"``, skips :data:`_ATTR_METADATA_KEYS` —
      ``workflow_id`` and ``source_event`` are real columns on
      :class:`Decision` but not on the other 7 node tables; this filter
      prevents Binder exceptions on Person/Organisation/etc.
    - Returns ``(clauses, params)`` tuple. Caller composes
      ``f"SET {', '.join(clauses)}"`` and merges ``params`` into the
      ``execute()`` parameter dict.

    Args:
        attrs: Map of attribute name → value.
        prefix: Cypher node/rel alias to qualify each key (e.g. ``"n"``,
            ``"r"``).
        kind: Optional kind for the Decision-aware metadata filter. Pass
            ``None`` for relationships (rel attrs never carry workflow
            metadata).

    Returns:
        ``(set_clause_fragments, params_dict)`` — both empty if ``attrs``
        is empty (or every key was filtered out as Decision metadata on a
        non-Decision kind).

    Raises:
        ValueError: if any key fails the :data:`_VALID_ATTR_KEY` regex.
    """
    clauses: list[str] = []
    params: dict[str, Any] = {}
    for i, (key, value) in enumerate(attrs.items()):
        if kind != "Decision" and key in _ATTR_METADATA_KEYS:
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
                entity.attrs, prefix="n", kind=entity.kind
            )
            set_clauses.extend(attr_clauses)
            params.update(attr_params)

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
                with self._conn_lock:
                    self.conn.execute(
                        "CREATE (d:Decision {"
                        "id: $id, workflow_id: $wf, phase: $ph, "
                        "persona_role: $pr, verdict: $verdict, reason: $reason, "
                        "decided_at: $decided_at, source_event: $source_event, "
                        "attributes: $attributes"
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
                            "attributes": json.dumps(attributes or {}, default=str),
                        },
                    )

        # Side-effects outside both locks (mirrors upsert/link).
        if minted:
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
                # link() handles validation, locking, and silent no-op on
                # missing endpoints; it also emits its own entity.linked
                # bus + audit pair, which is consistent with the standard
                # rel-write contract.
                self.link(decision_id, "DECIDED_ON", did)
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
        return row["n"]

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
        return [row["n"] for row in self.query(cypher, params)]

    def linked(self, id: str, rel: str | None = None) -> list[dict[str, Any]]:
        """Return outgoing neighbours of ``id``, optionally filtered by ``rel``.

        Each result row is a dict ``{"node": <neighbour-dict>, "rel":
        "<REL_TYPE>"}`` — ``rel`` is the canonical uppercase rel-table name
        as reported by Kuzu's ``label(r)`` function (Kuzu 0.6.1 does not
        provide a ``type(r)``; ``label(r)`` is the documented equivalent
        for rel records).

        ``rel`` is normalised to uppercase (mirroring :meth:`link`) and
        validated against :data:`_VALID_RELS` when given. ``rel=None``
        returns rels of any type via Kuzu's label-less rel pattern, which
        the smoke tests at the top of TASK-006 confirmed works in 0.6.1.

        Returns only OUTGOING edges from ``id``. The reverse direction
        (incoming edges) is not exposed by this method; use :meth:`query`
        with an explicit ``<-[r]-`` pattern when needed.
        """
        params: dict[str, Any] = {"id": id}
        if rel is None:
            cypher = (
                "MATCH ({id: $id})-[r]->(n) "
                "RETURN n, label(r) AS rel"
            )
        else:
            rel_upper = rel.upper()
            if rel_upper not in _VALID_RELS:
                raise ValueError(
                    f"unknown rel: {rel!r} "
                    f"(expected one of {sorted(_VALID_RELS)})"
                )
            cypher = (
                f"MATCH ({{id: $id}})-[r:{rel_upper}]->(n) "
                "RETURN n, label(r) AS rel"
            )
        return [{"node": row["n"], "rel": row["rel"]} for row in self.query(cypher, params)]

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

        The LIMIT detection uses a word-boundary regex to avoid false positives
        in identifiers or string literals (e.g. 'limited').
        """
        # Word-boundary scan to avoid false positives on identifier substrings.
        if _LIMIT_PATTERN.search(pattern) is None:
            pattern = f"{pattern.rstrip().rstrip(';')} LIMIT {int(limit)}"
        return self.query(pattern, params)
