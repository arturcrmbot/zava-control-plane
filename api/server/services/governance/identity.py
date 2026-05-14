"""Ed25519 agent identity store — Phase 5 TASK-037.

Per plan/feature-agent-governance-toolkit-1.md, every machine agent in
:data:`api.shared.agents.AGENTS` has an Ed25519 keypair. Audit ledger
entries that carry an ``agent_id`` are signed with the corresponding
private key into ``actor_jws``; the verify route + Evidence chip use
the public key to validate.

Two modes:

- **Dev** (default, ``AGT_DEV_KEYS=1`` or unset): generate keypairs at
  boot, persist to ``azurite-data/agt-keys/<agent_id>.{pem,pub}``.
  Idempotent — second boot loads the existing keys.
- **Prod**: load public keys from ``data/governance/agent-pubkeys/<agent_id>.pub``
  (committed to the repo so they're auditable); private keys come from
  Azure Key Vault secret ``agt-{agent_id}-key`` via ``DefaultAzureCredential``.

Pure stdlib + ``cryptography`` for the primitives. The kernel
(:mod:`api.server.services.governance.kernel`) re-exports the
sign/verify helpers; this module is the only place that touches private
key material.
"""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Iterable

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


log = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Filesystem layout
# --------------------------------------------------------------------------


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError(
        "repo root not found; cannot locate azurite-data / data dirs"
    )


def _dev_keys_dir() -> Path:
    return _repo_root() / "azurite-data" / "agt-keys"


def _prod_pubkeys_dir() -> Path:
    return _repo_root() / "data" / "governance" / "agent-pubkeys"


def _is_prod_mode() -> bool:
    """``AGT_DEV_KEYS`` truthy (or unset) → dev. Anything else → prod."""
    raw = os.environ.get("AGT_DEV_KEYS", "1").strip().lower()
    return raw not in ("1", "true", "yes")


# --------------------------------------------------------------------------
# Store
# --------------------------------------------------------------------------


class AgentIdentityStore:
    """Per-process keystore. Construct once at boot via :class:`GovernanceKernel`.

    Holds two parallel maps:

      - ``_private``: ``agent_id -> Ed25519PrivateKey`` (dev only;
        in prod we never hold private keys in memory — the Key Vault
        round-trip happens lazily inside :meth:`sign`).
      - ``_public``: ``agent_id -> Ed25519PublicKey`` (always).

    Thread-safe: the lock guards mutation. Reads are racy-OK since the
    map only ever grows and we never overwrite a populated entry.
    """

    def __init__(self, agent_ids: Iterable[str]) -> None:
        self._private: dict[str, Ed25519PrivateKey] = {}
        self._public: dict[str, Ed25519PublicKey] = {}
        self._lock = threading.Lock()
        self._prod = _is_prod_mode()
        if self._prod:
            self._load_pubkeys_from_disk(agent_ids)
        else:
            self._ensure_dev_keypairs(agent_ids)

    # --- Dev mode -----------------------------------------------------------

    def _ensure_dev_keypairs(self, agent_ids: Iterable[str]) -> None:
        """Generate (or load) Ed25519 keypairs for every agent_id.

        Persists each pair to ``azurite-data/agt-keys/<agent_id>.{pem,pub}``.
        Re-running is idempotent — existing files are loaded as-is.
        """
        keys_dir = _dev_keys_dir()
        keys_dir.mkdir(parents=True, exist_ok=True)
        for aid in agent_ids:
            with self._lock:
                if aid in self._public:
                    continue
                pem_path = keys_dir / f"{aid}.pem"
                pub_path = keys_dir / f"{aid}.pub"
                if pem_path.is_file() and pub_path.is_file():
                    priv = serialization.load_pem_private_key(
                        pem_path.read_bytes(), password=None
                    )
                    if not isinstance(priv, Ed25519PrivateKey):
                        raise RuntimeError(
                            f"identity: {pem_path} is not an Ed25519 key"
                        )
                else:
                    priv = Ed25519PrivateKey.generate()
                    pem_path.write_bytes(
                        priv.private_bytes(
                            encoding=serialization.Encoding.PEM,
                            format=serialization.PrivateFormat.PKCS8,
                            encryption_algorithm=serialization.NoEncryption(),
                        )
                    )
                    pub_path.write_bytes(
                        priv.public_key().public_bytes(
                            encoding=serialization.Encoding.PEM,
                            format=serialization.PublicFormat.SubjectPublicKeyInfo,
                        )
                    )
                self._private[aid] = priv
                self._public[aid] = priv.public_key()
        log.info(
            "identity: dev keystore ready for %d agent(s) at %s",
            len(self._public), keys_dir,
        )

    # --- Prod mode ----------------------------------------------------------

    def _load_pubkeys_from_disk(self, agent_ids: Iterable[str]) -> None:
        """Load committed public keys from ``data/governance/agent-pubkeys/``.

        Private keys are not loaded eagerly in prod — :meth:`sign`
        fetches from Key Vault on demand (cached per process).
        """
        pubkeys_dir = _prod_pubkeys_dir()
        if not pubkeys_dir.is_dir():
            raise RuntimeError(
                f"identity: prod pubkeys dir not found at {pubkeys_dir}; "
                f"see data/governance/README.md for setup"
            )
        for aid in agent_ids:
            pub_path = pubkeys_dir / f"{aid}.pub"
            if not pub_path.is_file():
                # Don't fail boot on a missing pubkey — some agents may
                # not be active in this deploy. Log and skip.
                log.warning(
                    "identity: prod pubkey missing for agent_id=%s at %s",
                    aid, pub_path,
                )
                continue
            pub = serialization.load_pem_public_key(pub_path.read_bytes())
            if not isinstance(pub, Ed25519PublicKey):
                raise RuntimeError(
                    f"identity: {pub_path} is not an Ed25519 public key"
                )
            self._public[aid] = pub
        log.info(
            "identity: prod keystore loaded %d pubkey(s) from %s",
            len(self._public), pubkeys_dir,
        )

    def _load_private_from_keyvault(self, agent_id: str) -> Ed25519PrivateKey:
        """Lazy fetch of a private key from Key Vault. Cached per process.

        Secret name convention: ``agt-{agent_id}-key`` (PEM-encoded
        Ed25519 private key, PKCS8). Vault URL via env
        ``AGT_KEY_VAULT_URL``. Auth via :class:`DefaultAzureCredential`.
        """
        cached = self._private.get(agent_id)
        if cached is not None:
            return cached
        vault_url = os.environ.get("AGT_KEY_VAULT_URL")
        if not vault_url:
            raise RuntimeError(
                "identity: AGT_KEY_VAULT_URL not set; cannot load private "
                f"key for agent_id={agent_id} in prod mode"
            )
        # Local imports keep azure-keyvault-secrets out of the dev hot
        # path — most tests never exercise the prod branch.
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient

        cred = DefaultAzureCredential(
            exclude_interactive_browser_credential=True
        )
        client = SecretClient(vault_url=vault_url, credential=cred)
        secret = client.get_secret(f"agt-{agent_id}-key")
        priv = serialization.load_pem_private_key(
            secret.value.encode("utf-8") if isinstance(secret.value, str) else secret.value,
            password=None,
        )
        if not isinstance(priv, Ed25519PrivateKey):
            raise RuntimeError(
                f"identity: KV secret agt-{agent_id}-key is not an Ed25519 key"
            )
        with self._lock:
            self._private[agent_id] = priv
        return priv

    # --- Public surface ----------------------------------------------------

    def known_agents(self) -> tuple[str, ...]:
        """Sorted tuple of agent_ids the store has a key (or pubkey) for."""
        return tuple(sorted(self._public.keys()))

    def has(self, agent_id: str) -> bool:
        return agent_id in self._public

    def public_key(self, agent_id: str) -> Ed25519PublicKey:
        try:
            return self._public[agent_id]
        except KeyError as ex:
            raise KeyError(
                f"identity: no public key for agent_id={agent_id!r}; "
                f"add an entry to api.shared.agents.AGENTS"
            ) from ex

    def sign(self, agent_id: str, payload: bytes) -> bytes:
        """Sign ``payload`` with the agent's Ed25519 private key.

        Returns the raw 64-byte signature. The JWS framing is done by
        :meth:`GovernanceKernel.sign_action` (TASK-038); this method is
        the lowest-level signing primitive.
        """
        priv = self._private.get(agent_id)
        if priv is None:
            if self._prod:
                priv = self._load_private_from_keyvault(agent_id)
            else:
                raise KeyError(
                    f"identity: no private key for agent_id={agent_id!r}"
                )
        return priv.sign(payload)

    def verify(self, agent_id: str, payload: bytes, signature: bytes) -> bool:
        """Verify ``signature`` over ``payload`` with the agent's pubkey.

        Returns True on a valid signature, False on any verification
        failure (wrong key, tampered payload, malformed signature).
        Pure read of the in-memory pubkey map; no network round-trip.
        """
        pub = self._public.get(agent_id)
        if pub is None:
            return False
        try:
            pub.verify(signature, payload)
            return True
        except Exception:
            return False
