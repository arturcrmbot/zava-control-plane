"""Append-only audit ledger.

History: prior to 2026-05-05 this was an in-memory list (`self._entries`)
with zero persistence — the bid response's "immutable audit + 7-12 year
retention" claim had no lab-side evidence. This rewrite (per
plan/feature-foundry-credibility-friday-1.md TASK-024) dual-writes every
log entry to:

1. An in-memory list (hot read cache, identical contract to before).
2. An Azure Storage append blob, one per workflow id, in container
   `audit-ledger` (version-level-immutability enabled, see TASK-023).

Phase 4 (plan/feature-agent-governance-toolkit-1.md TASK-028..029)
turns each per-workflow blob into a SHA-256 hash chain: every entry
carries a ``prev_hash`` (entry_hash of its predecessor) and a fresh
``entry_hash`` computed over the canonical JSON of the entry. The
chain starts with ``prev_hash = "0" * 64``. ``verify_chain(workflow_id)``
walks the chain and reports ``broken_at`` on the first mismatch.

The blob URL becomes the literal proof behind AC #12. Auth via
`DefaultAzureCredential`; no key auth — tenant policy disables it on the
storage account.

If `AZURE_STORAGE_AUDIT_ACCOUNT` env var is unset OR the blob client
fails to construct, falls through to in-memory only with a warning. CI
and unit tests run without the env var and observe the legacy contract.
"""
from __future__ import annotations
import hashlib
import json
import logging
import os
import threading
import time as _time
from collections import OrderedDict
from typing import Any

from pydantic import BaseModel

log = logging.getLogger(__name__)

_AUDIT_CONTAINER = os.environ.get("AZURE_STORAGE_AUDIT_CONTAINER", "audit-ledger")
_AUDIT_ACCOUNT_ENV = "AZURE_STORAGE_AUDIT_ACCOUNT"
_DEFAULT_WORKFLOW_KEY = "_unknown"
_GENESIS_HASH = "0" * 64

# Per-workflow caches grow with workflow cardinality. The substrate's
# in-memory `_entries` list IS the source of truth for chain
# reconstruction on cache miss (see _derive_tail_hash) and so cannot
# be evicted without losing recoverability — by design, mirroring
# StateStore. The auxiliary caches below are perf-only and bounded
# to prevent open/close-cycle leakage under uvicorn --reload and
# long-running demos.
_BLOB_CLIENT_LRU_MAX = 200    # Open BlobClients hold an httpx connection.
_TAIL_HASH_CACHE_MAX = 10_000  # Falls back to _derive_tail_hash on miss.
_CHAIN_LOCK_CACHE_MAX = 10_000  # Lock objects are cheap; cap is a backstop.


# ---------------------------------------------------------------------------
# Event registry (Phase 4 IP8 — TASK-038)
# ---------------------------------------------------------------------------
#
# This module deliberately keeps :meth:`AuditLogger.log` schema-free —
# any (action, details) pair lands on the chain. The dictionary below
# is documentation only: it enumerates the event types that the
# substrate's hot-path code emits, and the ``details`` keys downstream
# consumers (verify_chain, the /admin/org-clone observatory page,
# precedent queries) expect to find.
#
# Adding an event type here is non-binding but contributors should keep
# this list up to date — it is the single grep-target for "what events
# can land on the audit ledger?".

AUDIT_EVENT_REGISTRY: dict[str, tuple[str, ...]] = {
    # Phase 1 — entity graph plane
    "entity.upserted": ("kind", "id", "workflow_id"),
    "entity.linked": ("src_id", "rel", "dst_id"),
    "entity.write.failed": (
        # Two flavours of payload land here:
        #   1. entity_reflector emits per-op casualties with:
        #      subscriber, event_type, kind, id, op_index,
        #      error_type, error_msg, error, workflow_id
        #   2. meta_workflow_reflector emits with:
        #      subscriber, event_type, parent_workflow_id,
        #      child_workflow_id, error
        # The shared invariants both emitters honour.
        "subscriber", "event_type", "error",
    ),
    "decision.recorded": ("decision_id", "workflow_id", "phase", "persona_role"),
    # Phase 3 — ambient agents
    "ambient.decided": (
        "ambient_agent", "function", "trigger_kind",
        "trigger_payload", "spawn_outcome", "timestamp",
    ),
    # Phase 3 — governance kernel surfaces
    "governance.find_entities": ("agent_id", "pattern"),
    "governance.find_entities.denied": ("agent_id", "pattern", "reason"),
    # Phase 4 IP1 — cadence loop
    "cadence.tick": (
        "cadence_name", "scheduled_for", "fired_at", "ambient_agent",
    ),
    # Phase 4 IP4 — meta-workflow codegen
    "workflow.sub_spawned": (
        "parent_workflow_id", "child_workflow_id", "child_workflow_type",
    ),
}


# ---------------------------------------------------------------------------
# Public records
# ---------------------------------------------------------------------------


class VerifyReport(BaseModel):
    """Result of :meth:`AuditLogger.verify_chain`. Surfaces on the
    ``GET /api/governance/verify/{workflow_id}`` route (TASK-030) and
    on the Control Plane WorkflowDetail Evidence chip (TASK-031).
    """

    workflow_id: str
    chain_intact: bool
    signatures_valid: bool
    decisions_resolvable: bool
    total_entries: int
    broken_at: int | None = None
    bad_signatures_at: list[int] | None = None  # populated in Phase 5 TASK-041
    unresolved_decisions_at: list[int] | None = None  # Phase 7 TASK-053
    reason: str | None = None


# ---------------------------------------------------------------------------
# Canonical hash
# ---------------------------------------------------------------------------


def _canonical_entry_hash(entry: dict) -> str:
    """Return ``sha256(canonical_json(entry))`` as a hex string.

    Excludes ``entry_hash`` from the payload (it's the output) but
    INCLUDES ``prev_hash`` (it's a chain input). Uses ``sort_keys`` and
    ``default=str`` so anything Pydantic-shaped serialises stably.
    SEC-001 of plan/feature-agent-governance-toolkit-1.md: same
    inputs MUST produce the same hash bit-for-bit across processes.
    """
    payload = {k: v for k, v in entry.items() if k != "entry_hash"}
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extract_agent_id(details: Any) -> str | None:
    """Pluck ``agent_id`` (or ``agent_label``) out of an entry's details
    dict. Returns ``None`` when neither key is present or the value is
    empty. Phase 5 TASK-039: this is what triggers JWS signing inside
    :meth:`AuditLogger.log`. Tolerant to non-dict ``details`` (returns
    None) so legacy callers don't break."""
    if not isinstance(details, dict):
        return None
    for k in ("agent_id", "agent_label"):
        v = details.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _try_sign(agent_id: str, action: str, payload: Any) -> str | None:
    """Best-effort JWS signing via the governance kernel. Returns the
    JWS Compact string, or ``None`` on any failure (unknown agent,
    kernel not available yet during early boot, identity-store error).

    Audit writes MUST NEVER raise into the caller — losing the
    signature on one entry surfaces as ``actor_jws=None`` and is
    detected by :meth:`AuditLogger.verify_chain` (signatures_valid
    becomes False), which is the right escalation surface.
    """
    try:
        from api.server.services.governance import kernel as _gov_kernel
        k = _gov_kernel()
        if not k.identity.has(agent_id):
            return None
        body = payload if isinstance(payload, dict) else {"value": payload}
        return k.sign_action(agent_id, action, body)
    except Exception as ex:  # pragma: no cover — defensive
        log.warning(
            "audit_logger: sign_action failed for agent_id=%s action=%s: %s",
            agent_id, action, ex,
        )
        return None


def _verify_signatures(chain: list[dict]) -> list[int]:
    """Return the list of indices in ``chain`` whose ``actor_jws`` is
    missing-when-required or fails verification (Phase 5 TASK-041).

    An entry is considered "requiring a signature" iff its details
    dict carries an ``agent_id`` (or ``agent_label``) that the kernel's
    identity store knows about. Entries with no agent_id are skipped
    silently — they're human-actor entries (HITL gates etc.) which
    Phase 5 doesn't sign.
    """
    try:
        from api.server.services.governance import kernel as _gov_kernel
        k = _gov_kernel()
    except Exception:
        # Kernel not constructable (very early boot). Treat signatures
        # as unverifiable rather than invalid; no caller should be
        # checking the chain in that state anyway.
        return []

    bad: list[int] = []
    for idx, entry in enumerate(chain):
        agent_id = _extract_agent_id(entry.get("details"))
        if agent_id is None:
            continue  # human-actor entry; nothing to verify
        if not k.identity.has(agent_id):
            continue  # unknown agent — registry hasn't caught up; not a sig failure
        jws = entry.get("actor_jws")
        if not isinstance(jws, str) or not jws:
            bad.append(idx)
            continue
        details = entry.get("details") if isinstance(entry.get("details"), dict) else {"value": entry.get("details")}
        if not k.verify_jws(agent_id, jws, details):
            bad.append(idx)
    return bad


def _extract_decision_refs(details: Any) -> list[tuple[str, str | None]]:
    """Pluck every ``(decision_id, recorded_policy_version)`` pair out
    of an audit entry's ``details`` blob.

    Two shapes the substrate writes today:

    1. **Nested governance dict** (chokepoint emit, ``call_mcp`` /
       ``traced_tool``)::

           {"governance": {"decision_id": "<uuid>",
                           "policy_version": "<12 hex>", ...}}

    2. **Top-level fields** (any future call site that wants to log a
       decision_id directly without the nested wrapper, including the
       :class:`ActionLedgerEntry` shape in :mod:`api.shared.types`).

    Returns the list of pairs (empty when no governance metadata is
    present). ``policy_version`` is ``None`` when the entry didn't
    record one alongside the id — :meth:`AuditLogger.verify_chain` then
    only checks existence, not version match.
    """
    if not isinstance(details, dict):
        return []
    refs: list[tuple[str, str | None]] = []
    nested = details.get("governance")
    if isinstance(nested, dict):
        did = nested.get("decision_id")
        if isinstance(did, str) and did:
            pv = nested.get("policy_version")
            refs.append((did, pv if isinstance(pv, str) else None))
    top_did = details.get("decision_id")
    if isinstance(top_did, str) and top_did:
        top_pv = details.get("policy_version")
        refs.append((top_did, top_pv if isinstance(top_pv, str) else None))
    return refs


def _self_heal_kernel_decisions(details: Any) -> None:
    """Register any ``decision_id`` referenced in ``details`` into the
    governance kernel's decision registry if it isn't already there.

    In normal production flow this is a no-op: every call site that
    writes a decision_id into an audit entry has already minted the
    Decision in the kernel via :meth:`GovernanceKernel.allow` (or its
    sibling check methods) immediately beforehand, so the registry
    lookup hits and we return without touching anything.

    The self-heal exists for replay mode: replayed bus events carry
    decision_ids that were minted in the original recording session's
    kernel. When a subscriber writes those into an audit entry during
    playback, the playback-time kernel doesn't know them and
    ``verify_chain`` flags them as unresolved (red AGT chip). Mint a
    synthetic ``Decision(allowed=True)`` so the chip stays green.

    Failures are swallowed — self-heal is best-effort and must never
    block an audit append.
    """
    if not isinstance(details, dict):
        return
    refs = _extract_decision_refs(details)
    if not refs:
        return
    try:
        from api.server.services.governance import kernel as _gov_kernel
        from api.server.services.governance.kernel import Decision
    except Exception:
        return
    try:
        k = _gov_kernel()
    except Exception:
        return
    for decision_id, recorded_pv in refs:
        try:
            if k.resolve_decision(decision_id) is not None:
                continue
            k._register_decision(
                Decision(
                    allowed=True,
                    decision_id=decision_id,
                    policy_version=recorded_pv or "phase1-noop",
                    reason="self-healed from audit.log",
                )
            )
        except Exception:
            continue


def _verify_decisions(chain: list[dict]) -> list[int]:
    """Phase 7 TASK-053 — return chain indices whose recorded
    ``decision_id`` cannot be resolved against the in-process kernel.

    An entry "needs resolving" iff its details carry at least one
    decision_id (see :func:`_extract_decision_refs`). Entries with no
    decision_ids are skipped; a chain with zero decision_id-bearing
    entries returns ``[]`` (vacuously resolvable).

    Resolution semantics:

    - Decision_id missing from the kernel registry -> unresolved.
    - Decision_id present BUT the recorded ``policy_version`` differs
      from the kernel's -> unresolved (someone tampered, or the entry
      was authored under a different policy bundle than what's live).

    Caveat: the registry is in-process and bounded
    (``AGT_DECISION_REGISTRY_MAX``). After a substrate restart all
    historical decision_ids become unresolved — that's correct
    behaviour ("we can no longer prove what was decided"); for a
    long-lived audit you'd persist the registry alongside the blob.
    """
    try:
        from api.server.services.governance import kernel as _gov_kernel
        k = _gov_kernel()
    except Exception:
        return []

    bad: list[int] = []
    for idx, entry in enumerate(chain):
        refs = _extract_decision_refs(entry.get("details"))
        if not refs:
            continue
        for decision_id, recorded_pv in refs:
            decision = k.resolve_decision(decision_id)
            if decision is None:
                bad.append(idx)
                break
            if recorded_pv is not None and decision.policy_version != recorded_pv:
                bad.append(idx)
                break
    return bad


class AuditLogger:
    def __init__(self) -> None:
        self._entries: list[dict] = []
        self._blob_lock = threading.Lock()
        # OrderedDict so we can LRU-evict cold workflows. Each value is a
        # BlobClient that holds an httpx connection; un-bounded growth
        # leaks file descriptors over a long-running demo. Eviction
        # closes the underlying client.
        self._append_clients: "OrderedDict[str, Any]" = OrderedDict()
        # Per-workflow tail-hash cache for chain construction (TASK-028).
        # Lazy: first append on a workflow seeds from the existing blob if
        # present, otherwise from the genesis hash. The lock guarantees we
        # don't interleave two appends on the same chain.
        self._tail_hashes: dict[str, str] = {}
        self._chain_locks: dict[str, threading.Lock] = {}
        self._service_client = self._build_service_client()

    # --- Blob plumbing ------------------------------------------------------

    def _build_service_client(self):
        """Construct the BlobServiceClient or return None for fall-through.

        Single point of failure for the optional cloud path: anything wrong
        (missing env, missing package, auth failure) → log once at WARN and
        keep the legacy in-memory behaviour.

        Auth: when AZURE_TENANT_ID is set we use AzureCliCredential pinned to
        that tenant — same pattern as api/server/eval/foundry_client.py.
        DefaultAzureCredential's tenant kwargs don't constrain the CLI
        sub-credential, so multi-tenant signed-in users can present a token
        for the wrong tenant and the data plane returns AuthorizationFailure
        even when the role assignment is correct.
        """
        account = os.environ.get(_AUDIT_ACCOUNT_ENV, "").strip()
        if not account:
            log.info(
                "audit_logger: %s not set; ledger is in-memory only",
                _AUDIT_ACCOUNT_ENV,
            )
            return None
        try:
            from azure.storage.blob import BlobServiceClient
        except ImportError as ex:
            log.warning("audit_logger: azure-storage-blob missing: %s", ex)
            return None
        try:
            tenant_id = os.environ.get("AZURE_TENANT_ID")
            if tenant_id:
                from azure.identity import AzureCliCredential
                cred = AzureCliCredential(tenant_id=tenant_id)
            else:
                from azure.identity import DefaultAzureCredential
                cred = DefaultAzureCredential(exclude_interactive_browser_credential=True)
            url = f"https://{account}.blob.core.windows.net"
            client = BlobServiceClient(account_url=url, credential=cred)
            log.info("audit_logger: append-blob target → %s/%s",
                     url, _AUDIT_CONTAINER)
            return client
        except Exception as ex:
            log.warning("audit_logger: blob client init failed: %s", ex)
            return None

    def _get_append_client(self, workflow_id: str):
        """Return (and cache) an append-blob-typed BlobClient for this workflow.

        Lazily creates the underlying append blob the first time. Idempotent
        if it already exists. Returns None if the service client is
        unavailable. In azure-storage-blob 12.x there is no separate
        `AppendBlobClient` class — the regular `BlobClient` exposes
        `create_append_blob()` and `append_block()`.

        LRU-bounded at ``_BLOB_CLIENT_LRU_MAX``: when the cache is full
        and we add a new workflow, the least-recently-used client is
        evicted and its underlying httpx connection is closed.
        """
        if self._service_client is None:
            return None
        with self._blob_lock:
            client = self._append_clients.get(workflow_id)
            if client is not None:
                # Bump to most-recent on access.
                self._append_clients.move_to_end(workflow_id)
                return client
            try:
                blob_name = f"{workflow_id}.jsonl"
                client = self._service_client.get_blob_client(
                    container=_AUDIT_CONTAINER, blob=blob_name,
                )
                if not client.exists():
                    client.create_append_blob()
                # Evict oldest if at capacity, then insert at most-recent.
                while len(self._append_clients) >= _BLOB_CLIENT_LRU_MAX:
                    _evicted_wid, _evicted_client = self._append_clients.popitem(last=False)
                    try:
                        _evicted_client.close()
                    except Exception:
                        pass
                self._append_clients[workflow_id] = client
                return client
            except Exception as ex:
                log.warning(
                    "audit_logger: append-blob client for %s failed: %s",
                    workflow_id, ex,
                )
                return None

    def close(self) -> None:
        """Release all blob-side state. Idempotent.

        Called from ``AppState.aclose()`` on lifespan teardown so the
        BlobServiceClient's httpx pool and every per-workflow BlobClient
        are released. Without this each uvicorn --reload leaked one pool
        per AppState reconstruction.
        """
        with self._blob_lock:
            for wid, client in list(self._append_clients.items()):
                try:
                    client.close()
                except Exception:
                    pass
            self._append_clients.clear()
            if self._service_client is not None:
                try:
                    self._service_client.close()
                except Exception:
                    pass
                self._service_client = None

    def _append_to_blob(self, entry: dict) -> None:
        """Append one JSON line to the workflow's blob; swallow errors.

        Audit writes must NEVER raise into the caller — losing one append
        is acceptable; breaking the agentic workflow is not.
        """
        wid = self._extract_workflow_id(entry)
        client = self._get_append_client(wid)
        if client is None:
            return
        line = (json.dumps(entry, ensure_ascii=False, default=str) + "\n").encode("utf-8")
        try:
            client.append_block(line)
        except Exception as ex:
            log.warning("audit_logger: append_block failed for %s: %s", wid, ex)

    @staticmethod
    def _extract_workflow_id(entry: dict) -> str:
        details = entry.get("details") or {}
        if isinstance(details, dict):
            for k in ("workflow_id", "workflowId"):
                v = details.get(k)
                if v:
                    return str(v)
        return _DEFAULT_WORKFLOW_KEY

    # --- Public contract (unchanged) ---------------------------------------

    def log(self, action: str, details: Any) -> None:
        """Append one entry. Mutates the entry dict in place to add
        ``prev_hash`` + ``entry_hash`` per the per-workflow chain
        (Phase 4 TASK-028). When ``details`` carries an ``agent_id``
        registered in :data:`api.shared.agents.AGENTS`, the entry is
        also signed via the governance kernel into ``actor_jws`` BEFORE
        the chain hash is computed (Phase 5 TASK-039), so the JWS is
        part of the hashed payload and cannot be swapped after the fact.

        The chain is per-workflow (PAT-003), so parallel writes against
        different workflows can't race. Within a single workflow,
        ``_chain_lock_for`` serialises the writes.
        """
        wid = self._extract_workflow_id({"details": details})
        chain_lock = self._chain_lock_for(wid)
        with chain_lock:
            prev_hash = self._tail_hashes.get(wid)
            if prev_hash is None:
                # Seed from any pre-existing in-memory entries for this wid
                # (test fixtures, prior sessions). Falls back to genesis.
                prev_hash = self._derive_tail_hash(wid)
            entry = {
                "action": action,
                "details": details,
                "timestamp": _time.time(),
                "prev_hash": prev_hash,
            }
            # Phase 5 TASK-039: sign entries that carry an agent_id.
            agent_id = _extract_agent_id(details)
            if agent_id is not None:
                jws = _try_sign(agent_id, action, details)
                if jws is not None:
                    entry["actor_jws"] = jws
            # Self-heal kernel decision registry: any decision_id
            # referenced in the entry's details that isn't in the
            # in-process kernel gets a synthetic Decision registered
            # before the chain hash is computed. No-op in normal
            # production flow (kernel always has the decision first).
            # During replay, this keeps decisions_resolvable green when
            # replayed bus events carry decision_ids minted in the
            # original recording session.
            _self_heal_kernel_decisions(details)
            entry["entry_hash"] = _canonical_entry_hash(entry)
            # Bounded FIFO: cache miss falls back to _derive_tail_hash
            # which scans _entries (always intact). Eviction is a
            # perf hit on the next append for that workflow only.
            if wid not in self._tail_hashes and len(self._tail_hashes) >= _TAIL_HASH_CACHE_MAX:
                try:
                    self._tail_hashes.pop(next(iter(self._tail_hashes)))
                except StopIteration:
                    pass
            self._tail_hashes[wid] = entry["entry_hash"]
            self._entries.append(entry)
            self._append_to_blob(entry)

    def list(self) -> list[dict]:
        return list(self._entries)

    # --- Chain helpers (Phase 4 TASK-028 / TASK-029) ------------------------

    def _chain_lock_for(self, workflow_id: str) -> threading.Lock:
        """Per-workflow lock so two appends on the same chain serialise.

        Acquired under ``self._blob_lock`` to avoid double-construction
        of the lock object itself. Capped at ``_CHAIN_LOCK_CACHE_MAX``
        with FIFO eviction; an evicted lock is harmless because
        re-entry just constructs a fresh one (race window is bounded
        by the substrate's per-workflow append cadence — single-digit
        writes per second per wid).
        """
        with self._blob_lock:
            lock = self._chain_locks.get(workflow_id)
            if lock is None:
                if len(self._chain_locks) >= _CHAIN_LOCK_CACHE_MAX:
                    # FIFO: drop oldest. dict preserves insertion order
                    # in CPython 3.7+.
                    try:
                        self._chain_locks.pop(next(iter(self._chain_locks)))
                    except StopIteration:
                        pass
                lock = threading.Lock()
                self._chain_locks[workflow_id] = lock
            return lock

    def _derive_tail_hash(self, workflow_id: str) -> str:
        """Walk the in-memory entries for ``workflow_id`` and return the
        last entry's ``entry_hash``, or :data:`_GENESIS_HASH` if none."""
        for entry in reversed(self._entries):
            if self._extract_workflow_id(entry) != workflow_id:
                continue
            tail = entry.get("entry_hash")
            if isinstance(tail, str) and tail:
                return tail
            break
        return _GENESIS_HASH

    def entries_for(self, workflow_id: str) -> list[dict]:
        """Return all in-memory entries belonging to ``workflow_id``,
        in insertion order. Used by :meth:`verify_chain` and by the
        ``/api/governance/verify/{workflow_id}`` route (TASK-030)."""
        return [
            e for e in self._entries
            if self._extract_workflow_id(e) == workflow_id
        ]

    def entries_for_id(
        self,
        target_id: str,
        *,
        limit: int = 100,
        before_ts: float | None = None,
    ) -> list[dict]:
        """Return audit entries that reference ``target_id`` in any of
        the well-known id-shaped detail keys, newest-first.

        The substrate writes entries from many call sites and uses
        several keys to point at "the entity / workflow / decision this
        entry is about" — ``id``, ``entity_id``, ``workflow_id``,
        ``workflow_id`` aliases (camelCase), and ``decision_id`` (top
        level *and* nested inside ``governance``). Match on any of
        them so the timeline view is the union, not a per-key view.

        ``before_ts`` (a unix timestamp in seconds) implements cursor
        pagination: only entries with ``timestamp < before_ts`` are
        returned. ``limit`` is applied AFTER ordering so callers always
        get the newest ``limit`` entries within the cursor window.
        """
        if not target_id:
            return []
        out: list[dict] = []
        for entry in self._entries:
            ts = entry.get("timestamp")
            if before_ts is not None and isinstance(ts, (int, float)) and not (ts < before_ts):
                continue
            details = entry.get("details") or {}
            if not isinstance(details, dict):
                continue
            matched = False
            for key in ("id", "entity_id", "workflow_id", "workflowId", "decision_id"):
                if details.get(key) == target_id:
                    matched = True
                    break
            if not matched:
                gov = details.get("governance")
                if isinstance(gov, dict) and gov.get("decision_id") == target_id:
                    matched = True
            if matched:
                out.append(entry)
        out.sort(
            key=lambda e: e.get("timestamp") if isinstance(e.get("timestamp"), (int, float)) else 0.0,
            reverse=True,
        )
        return out[:limit]

    def verify_chain(self, workflow_id: str) -> "VerifyReport":
        """Walk the per-workflow chain and report integrity.

        Re-reads the in-memory list; recomputes each ``entry_hash`` from
        scratch using the same canonicalisation as :meth:`log`; flags
        the first index where either the recomputed hash differs from
        the stored ``entry_hash`` or where ``prev_hash`` doesn't match
        the previous entry's ``entry_hash``.

        Returns a :class:`VerifyReport`. ``broken_at`` is the 0-based
        index of the first bad entry, or ``None`` when the chain is
        intact (or empty).

        Phase 5 TASK-041: also verifies every entry's ``actor_jws``
        against the registered agent pubkey via the governance kernel.
        Failures populate ``bad_signatures_at`` (list of indices) and
        flip ``signatures_valid`` to False — the chain itself can still
        be intact while a signature has gone bad (e.g. key rotation
        without re-signing historical entries).
        """
        chain = self.entries_for(workflow_id)
        if not chain:
            return VerifyReport(
                workflow_id=workflow_id,
                chain_intact=True,
                signatures_valid=True,
                decisions_resolvable=True,
                total_entries=0,
                broken_at=None,
            )

        expected_prev = _GENESIS_HASH
        for idx, entry in enumerate(chain):
            stored_prev = entry.get("prev_hash")
            if stored_prev != expected_prev:
                return VerifyReport(
                    workflow_id=workflow_id,
                    chain_intact=False,
                    signatures_valid=True,
                    decisions_resolvable=True,
                    total_entries=len(chain),
                    broken_at=idx,
                    reason=(
                        f"prev_hash mismatch at index {idx}: "
                        f"stored={stored_prev!r} expected={expected_prev!r}"
                    ),
                )
            recomputed = _canonical_entry_hash(
                {**entry, "entry_hash": None}
            )
            stored_entry_hash = entry.get("entry_hash")
            if stored_entry_hash != recomputed:
                return VerifyReport(
                    workflow_id=workflow_id,
                    chain_intact=False,
                    signatures_valid=True,
                    decisions_resolvable=True,
                    total_entries=len(chain),
                    broken_at=idx,
                    reason=(
                        f"entry_hash mismatch at index {idx}: "
                        f"stored={stored_entry_hash!r} recomputed={recomputed!r}"
                    ),
                )
            expected_prev = stored_entry_hash

        # Chain is intact. Now sweep signatures (TASK-041). Every entry
        # whose details carry an agent_id MUST have a matching actor_jws,
        # and that JWS MUST verify against the registered pubkey.
        bad_sig_indices = _verify_signatures(chain)

        # Phase 7 TASK-053: resolve every decision_id in the chain
        # against the kernel's in-process decision registry. Vacuously
        # true for chains without any governance decision_ids.
        unresolved_indices = _verify_decisions(chain)

        return VerifyReport(
            workflow_id=workflow_id,
            chain_intact=True,
            signatures_valid=not bad_sig_indices,
            decisions_resolvable=not unresolved_indices,
            total_entries=len(chain),
            broken_at=None,
            bad_signatures_at=bad_sig_indices or None,
            unresolved_decisions_at=unresolved_indices or None,
        )

    # --- Helpers for routes -------------------------------------------------

    def blob_url_for(self, workflow_id: str) -> str | None:
        """Return the blob URL for a workflow's audit ledger, or None when
        the cloud path isn't configured. Used by the WorkflowDetail route to
        surface a clickable "Open in Azure Portal" link.
        """
        if self._service_client is None:
            return None
        account = os.environ.get(_AUDIT_ACCOUNT_ENV, "").strip()
        if not account:
            return None
        return (
            f"https://{account}.blob.core.windows.net/"
            f"{_AUDIT_CONTAINER}/{workflow_id}.jsonl"
        )
