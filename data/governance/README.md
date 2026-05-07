# `data/governance/`

Governance-bundle artefacts that are committed to the repo so they're
auditor-reviewable. Per
[`plan/feature-agent-governance-toolkit-1.md`](../../plan/feature-agent-governance-toolkit-1.md)
TASK-044 (Phase 5).

## `agent-pubkeys/`

Per-agent **Ed25519 public keys** in PEM format
(`SubjectPublicKeyInfo`), one file per registered agent — name matches
`api/shared/agents.py::AGENTS` keys exactly:

```
data/governance/agent-pubkeys/rag-classifier.pub
data/governance/agent-pubkeys/arbitration.pub
data/governance/agent-pubkeys/cv_crystalliser.pub
…
```

These are the keys the **prod** governance kernel
(`AGT_DEV_KEYS=0`) loads via
`api/server/services/governance/identity.py::AgentIdentityStore`. The
matching private keys live in **Azure Key Vault**, never in the repo:

| Vault secret name              | Holds                                |
|--------------------------------|--------------------------------------|
| `agt-{agent_id}-key`           | Ed25519 PEM (PKCS8) private key      |

The KV URL is read from `AGT_KEY_VAULT_URL`. Auth is
`DefaultAzureCredential` (managed identity in prod, az-cli locally).

## Dev mode

Dev runs (`AGT_DEV_KEYS=1` or unset) generate keypairs at boot and
persist BOTH halves under
`azurite-data/agt-keys/` (`.gitignore`'d). That directory holds the
matched `<agent_id>.pem` (private) + `<agent_id>.pub` (public) files
for every entry in `AGENTS`.

You almost never need to look at the prod path locally; the
[parity test](../../tests/api/server/services/governance/test_identity.py)
exercises both branches.

## Key rotation runbook (prod)

1. Generate a new keypair:

   ```bash
   uv run python -c "
   from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
   from cryptography.hazmat.primitives import serialization
   p = Ed25519PrivateKey.generate()
   open('NEW.pem', 'wb').write(p.private_bytes(
     encoding=serialization.Encoding.PEM,
     format=serialization.PrivateFormat.PKCS8,
     encryption_algorithm=serialization.NoEncryption()))
   open('NEW.pub', 'wb').write(p.public_key().public_bytes(
     encoding=serialization.Encoding.PEM,
     format=serialization.PublicFormat.SubjectPublicKeyInfo))
   "
   ```

2. Upload the private half to Key Vault (replaces the existing secret;
   KV keeps the old version automatically):

   ```bash
   az keyvault secret set --vault-name <vault> \
     --name "agt-<agent_id>-key" --file NEW.pem
   ```

3. Replace the committed public key:

   ```bash
   mv NEW.pub data/governance/agent-pubkeys/<agent_id>.pub
   git add data/governance/agent-pubkeys/<agent_id>.pub
   ```

4. Bump the rotation annotation in `api/shared/agents.py` so reviewers
   can see the rotation in the git history. Conventional comment:

   ```python
   # rotated 2026-08-01 (kv version <id>)
   "rag-classifier": AgentRegistryEntry(...)
   ```

5. **Redeploy the substrate**. The kernel re-reads `agent-pubkeys/`
   and re-fetches the private key from KV at boot.

6. Verify: hit `GET /api/governance/verify/{any_workflow_id}` — the
   chain stays intact (entry hashes don't depend on which key signed
   them) but `signatures_valid` will be `false` for any historical
   entries signed under the old key. That's correct: rotation means
   the old signatures are no longer attributable.

   To preserve verifiability of historical entries, retain the old
   public key as `<agent_id>-rot-<YYYYMMDD>.pub` under this directory
   and extend `verify_jws` to try the historical fallback. Out of
   scope for the WPP review.

## Why public keys are committed

So a reviewer with `git clone` access can verify any signature in any
audit blob without needing Key Vault credentials. That's the point of
the asymmetric design.
