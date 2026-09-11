# Azure Reference Deployment Implementation Plan

> **For agentic workers:** Use `executing-plans` after implementation approval. Follow the [master plan](2026-09-10-presales-release-readiness.md). Configuration work does not authorise provisioning or changes to tenant access.

**Goal:** Provide a reproducible private Azure reference and a separately gated public replay, without developer-local credentials or undocumented setup.

**Architecture:** Keep one ACA replica, one Uvicorn worker and the supervised Functions child in live mode. Use managed identity, existing Azure Storage, explicit provider configuration and mode-specific readiness. Provision closed ingress first; establish tenant authentication before any authorised external exposure.

**Tech Stack:** Bicep, azd, Azure Container Apps, Entra authentication, existing Azure Storage/model resources, Python and existing deployment tests.

**Status:** Superseded by [master plan v2](2026-09-10-presales-release-readiness.md). Reference only; preserve deployment safety, but do not execute the broader platform design as a requirement.

---

## Deployment contract

| Target | Runtime | Access | Durable operational state | Required model/provider |
|---|---|---|---|---|
| `local-live` | FastAPI plus Functions | Loopback; local development actor mechanism only | File backend for restart exercises; memory only for offline tests | Explicit fake, GitHub or Azure mode |
| `private-live` | One ACA replica, one API worker, supervised Functions | Tenant-authenticated access; no anonymous writable ingress | Phase 1 Azure Blob repository and writer lease | Azure runtime including Fleet Manager |
| `public-replay` | API/player, no Functions or live producers | Public read-only | Immutable recording/details; no live writer | No live model calls or supervisor |

`private-live` means access-restricted, not automatically private-IP networking.
The baseline can use Entra-protected external HTTPS only after the existing
public-binding hardening gate and explicit exposure approval. An organisation
requiring private-IP/VNet access needs an approved network route; this plan does
not invent or silently provision that topology.

### Resource ownership

| Resource/configuration | Installation responsibility |
|---|---|
| Workload resource group, ACA environment/app, workload managed identity, operational Storage and logging workspace | Existing Bicep, with parameter and RBAC corrections |
| Container registry and access to the released image | Explicit selected registry/image; document the current supplied-resource requirement |
| Azure model endpoint and deployment names | Operator-supplied approved resources, validated before use |
| Application Insights connection/resource | Explicitly supplied or linked through existing infrastructure; never imply it is created when it is not |
| Tenant app registration and application-role assignments | Approved tenant owner supplies/configures them; no automatic account or permission creation |
| Runtime state container and least-privilege storage/model access | Bicep/deployment step within the approved scope |
| Azure Files | Optional exports/artifacts or explicitly qualified legacy use; not proof of database or HITL persistence |
| Real enterprise MCPs and customer records | Outside this synthetic reference release |

## Task 3.1: Validate resolved configuration before provisioning

**Files**

- Create: `api/shared/deployment_config.py`
- Create: `tools/deployment_preflight.py`
- Create: `tests/api/shared/test_deployment_config.py`
- Create: `tests/tools/test_deployment_preflight.py`
- Modify: `scripts/deploy-blueprint.sh`
- Create: `scripts/deploy-private-reference.sh`
- Modify: `azure.yaml`

- [ ] Define a pure `validate_deployment_config(env, target)` returning a typed resolved configuration or explicit validation errors. The target is one of the three values above; it is never inferred from a missing mode.
- [ ] Reuse `build_runtime()`, `resolve_data_root()` and `configured_memory_domains()`. Validate vertical, optional world/scale, memory domains, runtime, paths, replica/worker count and persona policy against the actual selected pack.
- [ ] For private-live require Azure provider/deployments, persistent state settings, callback secret, tenant/subscription expectation, tenant-auth configuration and enforced governance/read access. Disallow fake runtime and volatile operational state.
- [ ] Validate `AZURE_OPENAI_FLEET_MANAGER_DEPLOYMENT` separately from the GitHub model name, using the explicit Phase 1 fallback when absent. Forward it through Bicep. Require an explicit value for the Aurora synthetic-approval flag in proof configurations; the normal private reference keeps it off.
- [ ] For replay require source-bound tape/proof inputs and forbid live workers, writer leases and business mutations. Do not require live provider credentials to read a recording.
- [ ] Define operator inputs by environment names, not example credentials: `EXPECTED_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_LOCATION`, `AZURE_ENV_NAME`, `ZAVA_VERTICAL`, `ZAVA_MODE`, model endpoint/deployment values and the chosen image. Missing values stop preflight; never guess a subscription or reuse whichever tenant happens to be logged in.
- [ ] Make the CLI print a redacted resolved resource/configuration plan. No credentials, tokens, connection-string secrets or signing material appear in output.
- [ ] Both deployment wrappers call this same validator before Azure mutation. Keep the existing public provenance/tenant gates; do not create a lower-level bypass path.

**Example of the pure validation interface**

```python
from collections.abc import Mapping
from typing import Literal

DeploymentTarget = Literal["local-live", "private-live", "public-replay"]

def validate_deployment_config(
    env: Mapping[str, str], target: DeploymentTarget,
) -> "DeploymentConfig":
    """Return resolved, pack-validated configuration; raise on invalid input."""
```

`DeploymentConfig` is defined in the same module and contains the resolved target,
runtime/pack identity, API and Functions paths, storage backend, provider
deployment names and access/probe settings. It contains secret references, not
secret values in its printable representation.

**Acceptance:** invalid configuration fails before provisioning. Tests cover absent mode, wrong tenant, unknown pack, incompatible memory list, missing live persistence/secret/auth and replay with live producers enabled.

## Task 3.2: Correct Bicep environment and process isolation

**Files**

- Modify: `infra/main.bicep`
- Modify: `infra/main.parameters.json`
- Modify: `infra/modules/aca-app.bicep`
- Modify: `deploy/entrypoint.sh`
- Modify: `api/server/state.py`
- Modify: `api/shared/vertical_loader.py` only for explicit cache-path support
- Modify: `tests/api/shared/test_vertical_loader.py`
- Modify: `tests/api/server/test_state_vertical_runtime.py`
- Modify: `tests/tools/test_public_story_deployment.py`
- Modify: `tests/tools/test_container_entrypoint.py`

- [ ] Pass `ZAVA_VERTICAL`, optional world/scale and explicit simulator/profile settings through parameters to the emitted environment.
- [ ] Remove the hard-coded five-domain `MEMORY_DOMAINS` value. Blank derives the permitted pack domains through the existing helper; an explicit override is validated. Do not invent a second memory allowlist in Bicep.
- [ ] Set the declared data root explicitly. If a `/data` share is selected, `ZAVA_DATA_DIR=/data` must refer to it rather than an unrelated working-directory path.
- [ ] Add `resolve_cache_root(environment)` beside `resolve_data_root()`: use trimmed `ZAVA_CACHE_DIR` when supplied and the existing data root otherwise, preserving path case. Keep `VerticalRuntime.data_dir` semantics unchanged. In `AppState`, locate native graph/KPI caches beneath the resolved cache root and pack name. The Azure reference uses `/tmp/zava-cache/api` and Phase 1 Blob state as the durable authority. Do not run native SQLite/Kuzu writers on the share by accident.
- [ ] Set **both** data/cache roots explicitly for the Functions child, using `/tmp/zava-cache/functions`; do not rely on `PORTAL_DATA_DIR` while inherited `ZAVA_DATA_DIR` overrides it. The API and child must not open the same embedded DB file.
- [ ] Wire the Phase 1 state endpoint/container/backend and managed identity. Ensure role assignments cover actual blob read/write/list and the existing Durable storage requirements; no shared-key workaround.
- [ ] For the flagship, set the existing insight loop off as required by Phase 2 and make approval behaviour explicit. Keep other profiles unchanged.
- [ ] Extend contract tests to validate the environment actually emitted by compiled Bicep, not a hand-selected Docker `-e` list. Exercise all installed packs, absent/explicit memory settings, mixed-case paths and API/Functions isolation.

**Acceptance:** default Agency environment is valid; unknown configuration fails clearly; each process has its own native cache; container replacement restores authoritative state. Merely seeing `/data` mounted does not pass this gate.

## Task 3.3: Establish real tenant authentication

**Files**

- Modify: `infra/modules/aca-app.bicep`
- Modify: `scripts/deploy-private-reference.sh`
- Modify: `api/server/services/read_route_auth.py`
- Modify: `api/shared/deployment_config.py`
- Modify: `tests/api/server/routes/test_read_route_auth.py`
- Add access cases to `tests/tools/test_deployment_preflight.py`

- [ ] Provision the app with external ingress disabled. Configure the approved Entra application, issuer/tenant, audience and role mapping before the wrapper permits external HTTPS.
- [ ] Keep the existing `.poc-safety`/public-binding gate. If external exposure is requested, complete all listed hardening requirements before enabling ingress; authentication alone does not waive them. Internal-only deployment must document how the reviewer reaches it.
- [ ] Make `require_actor()` consume validated platform identity under the configured ACA-auth trust boundary. Plain `X-Actor-*` values cannot authenticate or elevate a cloud caller. Retain the developer header mechanism only in explicit loopback/local mode.
- [ ] Map tenant-approved application roles to viewer/operator/finance approval capabilities. An ordinary operator is not automatically the CFO. Check the real authority resolver at the decision boundary.
- [ ] Preserve separate HMAC authentication for internal Durable callbacks; never put callback credentials in browser configuration.
- [ ] Add anonymous, wrong-tenant, wrong-audience, forged-role and insufficient-role cases, plus an authorised read and CFO decision. Add a replay case proving no user role makes public business writes available.
- [ ] Make exposure a final explicit step of the guarded wrapper, after auth and readiness are established. If any prior step fails, ingress remains closed.

**Acceptance:** there is no period of anonymous writable public access during installation. The documented browser path matches the actual selected network/auth topology.

## Task 3.4: Separate readiness from process liveness

**Files**

- Modify: `api/server/main.py`
- Modify: `api/functions/kernel_registration.py`
- Modify: `infra/modules/aca-app.bicep`
- Modify: `tests/api/server/routes/test_health_and_authority_health.py`
- Create: `tests/api/functions/test_runtime_health.py`
- Extend: `tests/tools/test_container_entrypoint.py`

- [ ] Keep `/healthz` as cheap process liveness. Add `/readyz`, returning HTTP 200 only when the selected mode's required components have initialized.
- [ ] Live readiness requires restored operational state, the writer lease, required graph projections, the selected supervisor and a responding Functions host. Surface stable failure codes without secrets.
- [ ] Add a read-only Functions readiness route through common kernel registration, reachable on the container-internal Functions port, with no business state or secrets in its response. The public API must not proxy/expose this internal port.
- [ ] Replay readiness requires loaded/validated tape metadata, details and initialized playback. It must not probe/start Functions, acquire a writer lease or call a model.
- [ ] Use cached initialization/failure state and bounded internal HTTP timeouts. Do not make billable model calls every time ACA probes readiness.
- [ ] Point ACA readiness/startup probes at `/readyz`; retain liveness at `/healthz`. Use separate failure messages for invalid configuration, dependency initialization and dependency loss.
- [ ] Cover Functions unavailable/non-running, state failure, supervisor failure, replay without live dependencies and graceful shutdown.

**Acceptance:** "process alive" no longer implies "can perform governed work". A missing required dependency cannot appear as healthy private-live operation.

## Task 3.5: Write and exercise the actual installation recipe

**Files**

- Create: `docs/reference-deployment.md`
- Modify: `docs/zava-hosting-brief.md`
- Modify: `docs/DEVELOPMENT.md`
- Modify: `docs/runtime-providers.md`
- Modify: `README.md`

- [ ] Document exact prerequisites and the resource ownership table above, including Python/Functions image requirements, registry access, approved Azure deployments and tenant app ownership.
- [ ] Provide resolved-configuration/preflight, private deployment and replay-publication commands through the wrappers. Explain which values are mandatory, which have explicit defaults and where credentials are supplied securely.
- [ ] Explain identity flow from browser to actor/authority, and workload identity to model/storage. Document actual GitHub versus Azure provider differences, including supervisor behaviour.
- [ ] Document operational state versus native caches, pending-approval recovery, scaling restrictions, update/rollback and cleanup of only run-owned resources.
- [ ] Add a cost worksheet with chosen region, SKU/replica assumptions, storage/telemetry usage, model token rates and pricing-source date. Do not invent a monthly price or claim supplied resources/licences are free.
- [ ] Exercise a clean approved reference installation using the **same compiled parameters** covered by tests. Start Aurora, observe a real model/tool result, restart during CFO approval and resume it. Record actual deficiencies rather than editing the guide to imply success.
- [ ] Leave live cloud execution pending until tenant/resource/cost permission exists. Offline validation alone cannot mark Phase 3 accepted.

## Phase gate and rollback

- [ ] GATE-C: private-live installation, authenticated access, real provider execution and restart recovery complete.
- [ ] Public replay boots without live credentials/dependencies.
- [ ] Another colleague can identify every mandatory resource/input from the guide.

Rollback keeps ingress closed until the previous compatible image/configuration
is ready. Preserve operational state and the prior approved public replay.
Never recover availability by disabling authentication or selecting volatile state.
