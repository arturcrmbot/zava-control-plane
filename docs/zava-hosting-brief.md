# Run the Zava reference

Zava is a single-replica reference implementation with synthetic operating data,
not a packaged production platform. Use an existing vertical; composing another
one is not an installation prerequisite.

## Choose the right mode

| Mode | What runs | Access |
|---|---|---|
| Local live | FastAPI, Functions, synthetic adapters and the selected model runtime | Loopback only |
| Private Azure live | One Container App containing API and Functions, using Azure model/storage identity | Internal ingress initially; Entra authentication must be configured before approved external exposure |
| Public replay | Recorded workflow state and events; no Functions or live agents | Public, read-only, source/proof gated |

Use separate azd environments for private live and public replay. Do not turn an
existing writable environment into an anonymous demo by changing one flag.

## Local development

Follow the root [quickstart](../README.md#quickstart). Python 3.11 is the
reference worker version; the project supports Python below 3.13.

Select `ZAVA_VERTICAL=agency` for Aurora. The Agency bootstrap supplies the
synthetic budget context; it does not fabricate a completed Aurora workflow.
Set a shared `DURABLE_EVENT_SECRET` for API/Functions callbacks. A live model run
requires the selected provider's access and consumes that provider's allowance.

For a quiet Aurora walkthrough, disable unrelated generation with
`SIMULATOR_RAMP_ENABLED=0`, `PORTAL_SEED_REQS=0`, `INSIGHT_LOOP_ENABLED=0` and
`BLUEPRINT_AUTOSTART_STREAM=0`. The operator-only CFO gate remains open even
when ordinary synthetic personae auto-close their own gates.

The local launch helpers bind the API, Functions, emulator and UI to loopback.
Functions needs `Kestrel__Endpoints__Local__Url=http://127.0.0.1:7071`;
Core Tools' printed `localhost` URLs alone do not prove a loopback listener.

## Azure resources and inputs

The existing Bicep creates the workload resource group, user-assigned managed
identity, Storage account, ACA environment/logging workspace, Container App and
registry-pull role assignment. Azure Files is optional.

Supply these approved inputs; do not put credentials in source control:

| Input | Purpose |
|---|---|
| Selected tenant/subscription and region | Workload ownership; verify the actual tenant before any mutation |
| `AZURE_ACR_LOGIN_SERVER`, `AZURE_ACR_NAME`, `AZURE_ACR_RESOURCE_GROUP` | Existing image registry |
| `ZAVA_MODE`, `ZAVA_VERTICAL` | Explicit boot mode and installed pack |
| `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT` | Azure-compatible model endpoint and actual deployment name for live mode |
| `AZURE_OPENAI_FLEET_MANAGER_DEPLOYMENT` | Optional separate supervisor deployment; empty uses the workflow deployment |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Optional supplied Application Insights resource; empty means that export is not configured |
| `DURABLE_EVENT_SECRET` | Shared internal callback secret, required for live work |
| `AUTH_TENANT_ID`, `AUTH_CLIENT_ID` | Approved single-tenant Entra app registration for private live |
| `AUTH_CLIENT_SECRET` | Optional registration secret when required by the chosen sign-in configuration |
| `PERSIST_DATA` | Explicit choice of the optional Azure Files mount |

Grant the workload identity the model/storage permissions required by those
resources. Direct Azure OpenAI inference uses `Cognitive Services OpenAI User`;
an APIM gateway must support the expected API routes and identity policy.
The template does not provision a model account, deployment or shared ACR.

## Private Azure live

Reuse a valid Azure sign-in rather than starting repeated device-code flows.
Set `AZURE_CONFIG_DIR` and `AZD_CONFIG_DIR` to the approved tenant's isolated
profiles first, then verify the tenant/subscription with `az account show`.
`azd config set auth.useAzCliAuth true` lets azd reuse that Azure CLI identity;
`azd auth login --check-status` checks it without prompting for another login.
Do not change the shared global subscription or weaken authentication to get
past a failed sign-in.

1. Obtain approval for the tenant, subscription, resources and expected costs.
2. Create/select a dedicated azd environment and set `ZAVA_MODE=live`,
   `ZAVA_VERTICAL=agency`, `LLM_RUNTIME=azure` and the required inputs above.
3. Configure the Entra registration's redirect URI as
   `https://APP_FQDN/.auth/login/aad/callback`, replacing `APP_FQDN` with the
   actual app host. Restrict assignment to intended demo users.
4. Define/assign app roles as required: `Zava.CFO`, `Zava.Executive`,
   `Zava.Operator`, `Zava.Viewer`, optionally `Zava.GC`.
   The application maps only trusted assigned roles; `X-Actor-*` headers are
   ignored in `READ_ROUTE_AUTH=platform` mode.
5. Run the approved `azd up`. Live ingress remains internal. The template
   configures native ACA authentication when the registration inputs are present.
6. Verify the actual auth configuration, tenant/audience, HTTPS, role assignment,
   required hardening switches and the root README's public-binding gate.
   Do not remove `.poc-safety` merely to pass a check.
7. Only after that gate and explicit approval, enable external authenticated
   ingress if the chosen topology needs it. Internal-only environments instead
   need an approved network access path.

The inspection/exposure commands use the actual values returned by azd:

```bash
APP="$(azd env get-value AZURE_CONTAINER_APP_NAME)"
RG="$(azd env get-value AZURE_RESOURCE_GROUP)"
az containerapp auth show --name "$APP" --resource-group "$RG"
# Only after the authentication/hardening gate and exposure approval:
az containerapp ingress enable --name "$APP" --resource-group "$RG" \
  --type external --target-port 80 --transport auto --allow-insecure false
```

Reprovisioning restores the safe internal-ingress default. Recheck authentication
before deliberately reopening external access. Legacy `READ_ROUTE_AUTH=enforce`
checks caller-supplied local headers; it is not an alternative to platform auth.

## Registry-hosted image build

The Dockerfile uses BuildKit cache mounts. For an ACR-hosted build, use the
supplied task rather than plain `az acr build`, whose default builder may reject
`RUN --mount`. Run from the approved isolated Azure profile and a clean checkout:

```bash
SOURCE_COMMIT="$(git rev-parse HEAD)"
az acr run --registry "$AZURE_ACR_NAME" --file deploy/acr-build.yaml \
  --set imageRepository=zava-control-plane imageTag="$SOURCE_COMMIT" \
        sourceCommit="$SOURCE_COMMIT" \
  --timeout 900 .
```

This builds and pushes an image; it does not deploy or approve a release.

## Public replay

Prepare an approved recording and the existing proof/seller-review manifests.
Then use `scripts/deploy-blueprint.sh`, the proof-gated wrapper around `azd up`.
It verifies source/tape identity and the expected Azure tenant before deployment.
No live model configuration is needed for playback.

Read the actual recording date, selected pack and mode from `/api/replay/meta`.
Historical or dirty-development recordings must not be presented as evidence
for the current release.

## Operation and limits

- `/healthz` reports process liveness. `/readyz` reports initialized playback or
  the live supervisor/callback configuration and responding Functions worker.
  It does not spend model tokens per probe or certify business correctness.
- The Functions worker's internal readiness route is `/api/zava-ready`.
- Memory domains come from the selected pack, not a deployment-wide allowlist.
- With the optional mount, API data is under `/data/<vertical>`; otherwise it is
  under ephemeral `/app/data/runtime/<vertical>`. Functions uses a separate root.
  A mounted share is not proof of safe database recovery.
- In-memory workflow/approval state is not a universal restart-recovery system.
  Do not claim failover, exactly-once external effects or production readiness.
- Current sizing is **2 vCPU, 4 GiB, min/max one replica**. There is no
  scale-to-zero claim. Budget compute, registry, Storage, logging and model use
  using the chosen region/SKUs and dated prices; no generic monthly quote is
  asserted here.
- Preserve the prior approved replay/image for rollback. Clean up only the
  explicitly owned evaluation resources after approval.

See [development and release gates](DEVELOPMENT.md) and the
[seller guide](presales/seller-guide.md). Optional composition skills live in
[zava-constellation](https://github.com/aiappsgbb/zava-constellation); they do not
replace these deployment prerequisites.
