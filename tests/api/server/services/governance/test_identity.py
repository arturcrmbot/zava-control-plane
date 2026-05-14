"""Phase 5 TASK-043 — Ed25519 identity store + JWS round-trip tests.

Covers:

- Round-trip sign / verify against the kernel.
- Tampered payload detected (verify_jws returns False).
- Wrong key detected (sign with one agent, verify against another).
- Wrong agent_id in body (kid OK, iss mismatch -> False).
- Key persistence across boots (same files on disk reload identical
  pubkeys).
- Dev-mode keypair generation is idempotent (second boot loads existing
  pem/pub).
- Unknown agent_id gracefully returns False, not raises.
- The generated key files live under azurite-data/agt-keys/ (per the
  .gitignore'd dev path).
"""
from __future__ import annotations

import os
from pathlib import Path

# Same Azurite-probe short-circuit as the rest of the governance suite.
os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "")

import pytest

from api.server.services.governance import kernel
from api.server.services.governance.identity import (
    AgentIdentityStore,
    _dev_keys_dir,
)
from api.server.services.governance.kernel import _reset_for_tests


@pytest.fixture(autouse=True)
def _fresh_kernel():
    _reset_for_tests()
    yield
    _reset_for_tests()


# ---------------------------------------------------------------------------
# Sign / verify round-trip
# ---------------------------------------------------------------------------


def test_sign_verify_round_trip() -> None:
    k = kernel()
    payload = {"workflow_id": "WF-1", "verdict": "green"}
    jws = k.sign_action("rag-classifier", "verdict", payload)
    assert isinstance(jws, str) and jws.count(".") == 2  # JWS Compact
    assert k.verify_jws("rag-classifier", jws, payload) is True


def test_verify_rejects_tampered_payload() -> None:
    k = kernel()
    jws = k.sign_action("rag-classifier", "verdict", {"workflow_id": "WF-1", "verdict": "green"})
    # Same agent, different payload -> payload_hash mismatch.
    assert k.verify_jws("rag-classifier", jws, {"workflow_id": "WF-1", "verdict": "red"}) is False


def test_verify_rejects_wrong_agent_in_kid() -> None:
    """A JWS minted by rag-classifier and presented as arbitration's
    must fail (iss != expected, signature also doesn't validate against
    the wrong pubkey)."""
    k = kernel()
    payload = {"workflow_id": "WF-1", "verdict": "green"}
    jws = k.sign_action("rag-classifier", "verdict", payload)
    assert k.verify_jws("arbitration", jws, payload) is False


def test_verify_rejects_unknown_agent() -> None:
    """An unknown agent_id MUST return False, not raise."""
    k = kernel()
    payload = {"x": 1}
    jws = k.sign_action("rag-classifier", "verdict", payload)
    assert k.verify_jws("never-registered", jws, payload) is False


def test_verify_rejects_malformed_jws() -> None:
    k = kernel()
    payload = {"x": 1}
    assert k.verify_jws("rag-classifier", "not.a.jws", payload) is False
    assert k.verify_jws("rag-classifier", "only.two", payload) is False
    assert k.verify_jws("rag-classifier", "", payload) is False


# ---------------------------------------------------------------------------
# Persistence + idempotency (dev mode)
# ---------------------------------------------------------------------------


def test_dev_keys_persist_on_disk() -> None:
    """After kernel construction, every registered agent has both
    .pem (private) and .pub (public) under azurite-data/agt-keys/."""
    kernel()  # construct
    keys_dir = _dev_keys_dir()
    from api.shared.agents import all_agent_ids

    for aid in all_agent_ids():
        assert (keys_dir / f"{aid}.pem").is_file(), f"missing pem for {aid}"
        assert (keys_dir / f"{aid}.pub").is_file(), f"missing pub for {aid}"


def test_dev_keys_are_idempotent_across_boots() -> None:
    """Second boot must reuse the same private/public keys — a JWS
    signed in boot 1 must verify after boot 2."""
    k1 = kernel()
    payload = {"workflow_id": "WF-X", "i": 1}
    jws = k1.sign_action("rag-classifier", "verdict", payload)

    # Simulate process restart.
    _reset_for_tests()
    k2 = kernel()
    assert k1 is not k2

    # New kernel must verify the OLD JWS — proves keys reloaded from disk.
    assert k2.verify_jws("rag-classifier", jws, payload) is True


# ---------------------------------------------------------------------------
# Identity store unit tests (no kernel boot)
# ---------------------------------------------------------------------------


def test_identity_store_known_agents_sorted() -> None:
    store = AgentIdentityStore(["b-agent", "a-agent", "c-agent"])
    assert store.known_agents() == ("a-agent", "b-agent", "c-agent")
    assert store.has("a-agent")
    assert not store.has("missing")


def test_identity_store_signing_round_trip() -> None:
    store = AgentIdentityStore(["test-agent"])
    payload = b"hello world"
    sig = store.sign("test-agent", payload)
    assert len(sig) == 64  # Ed25519 signature size
    assert store.verify("test-agent", payload, sig) is True
    assert store.verify("test-agent", b"tampered", sig) is False


def test_identity_store_verify_unknown_returns_false() -> None:
    store = AgentIdentityStore(["a-agent"])
    assert store.verify("missing", b"x", b"\0" * 64) is False


def test_identity_store_public_key_raises_on_unknown() -> None:
    store = AgentIdentityStore(["a-agent"])
    with pytest.raises(KeyError):
        store.public_key("missing")


# ---------------------------------------------------------------------------
# AuditLogger end-to-end: signed entries surface in verify_chain
# ---------------------------------------------------------------------------


def test_audit_log_signs_entry_when_agent_id_present() -> None:
    from api.server.services.audit_logger import AuditLogger

    log = AuditLogger()
    log.log("verdict", {"workflow_id": "WF-AUDIT", "agent_id": "rag-classifier", "verdict": "green"})
    chain = log.entries_for("WF-AUDIT")
    assert len(chain) == 1
    assert chain[0]["actor_jws"]
    report = log.verify_chain("WF-AUDIT")
    assert report.chain_intact is True
    assert report.signatures_valid is True
    assert report.bad_signatures_at is None


def test_audit_log_skips_signing_for_human_entries() -> None:
    from api.server.services.audit_logger import AuditLogger

    log = AuditLogger()
    log.log("hitl", {"workflow_id": "WF-HUMAN", "human": True, "note": "approved"})
    chain = log.entries_for("WF-HUMAN")
    assert chain[0].get("actor_jws") is None
    report = log.verify_chain("WF-HUMAN")
    assert report.chain_intact is True
    assert report.signatures_valid is True


def test_audit_log_skips_signing_for_unknown_agent_id() -> None:
    """An agent_id not in the registry produces an unsigned entry but
    does NOT fail the chain — TASK-036's CI catches the registry drift,
    not the runtime signer."""
    from api.server.services.audit_logger import AuditLogger

    log = AuditLogger()
    log.log("verdict", {"workflow_id": "WF-U", "agent_id": "ghost-agent", "x": 1})
    chain = log.entries_for("WF-U")
    assert chain[0].get("actor_jws") is None
    report = log.verify_chain("WF-U")
    assert report.chain_intact is True
    assert report.signatures_valid is True


def test_verify_chain_flags_missing_signature_when_required() -> None:
    """If a known agent_id appears on an entry whose actor_jws is
    missing, verify_chain MUST flip signatures_valid to False and
    record the index in bad_signatures_at."""
    from api.server.services.audit_logger import AuditLogger

    log = AuditLogger()
    # First write a valid signed entry.
    log.log("verdict", {"workflow_id": "WF-SIG", "agent_id": "rag-classifier", "verdict": "green"})
    # Now add a "fake" entry directly (bypassing log()) with a known
    # agent_id but no actor_jws. We use the chain bookkeeping internals
    # to keep the prev_hash/entry_hash legitimate.
    from api.server.services.audit_logger import _canonical_entry_hash

    entry = {
        "action": "verdict",
        "details": {"workflow_id": "WF-SIG", "agent_id": "rag-classifier", "i": 2},
        "timestamp": 0.0,
        "prev_hash": log.entries_for("WF-SIG")[-1]["entry_hash"],
        # actor_jws deliberately missing
    }
    entry["entry_hash"] = _canonical_entry_hash(entry)
    log._entries.append(entry)
    log._tail_hashes["WF-SIG"] = entry["entry_hash"]

    report = log.verify_chain("WF-SIG")
    assert report.chain_intact is True  # chain hashes still line up
    assert report.signatures_valid is False
    assert report.bad_signatures_at == [1]
