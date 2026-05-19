# `web/client/` — Feed of Work runbook

> Operator-facing control plane (port 5273). For the parent-level summary of
> what `web/client/` is and where it's hosted from, see `web/README.md`.
> This file is the **operational** runbook: how to bring it up, what the
> moving parts are, what to watch out for, and what's still open.

## 1. Local bring-up (full stack)

Four processes need to be running:

| Port  | Process                                  | Start command |
| ----- | ---------------------------------------- | ------------- |
| 10000 | Azurite (blob/queue/table emulator)      | `azurite --silent --location ~/.azurite &` |
| 7071  | Azure Functions host                     | `cd api/functions && func start` |
| 3101  | FastAPI (`api.server.main`)              | see below — env vars matter |
| 5273  | Vite dev server                          | `npm run dev:client` |

Verify with: `lsof -i :3101 -i :5273 -i :7071 -i :10000 -P -n | grep LISTEN`.

### 1.1 FastAPI — **PERSONA_AUTO_CLOSE matters**

The most-important runtime env var is `PERSONA_AUTO_CLOSE`. It governs which
persona roles are allowed to auto-resolve HITL gates (see
`api/server/services/persona_responder.py:_auto_close_set`):

| Value          | Effect                                                              |
| -------------- | ------------------------------------------------------------------- |
| _unset_ or `*` | **All** personae auto-close — feed will look empty (HITL drained)   |
| `none` / `off` | **No** personae auto-close — feed buries the operator in HITL items |
| CSV list       | Only the listed roles auto-close                                    |

For a balanced demo, use the curated list below. It contains 60 of the 79
loaded personae: every IC / mid-management role auto-closes, while the 19
senior roles (controller / cfo / cpo / dpo / gc / treasurer plus CEO,
directors, heads-of, and chief-level roles such as `creative_director`,
`hr_director`, `chief_data_officer`) are omitted so their escalations
land in HITL:

```bash
export PERSONA_AUTO_CLOSE="account_coordinator,account_director,account_executive,account_manager,ad_ops_specialist,analyst,analytics_engineer,ap_clerk,bp_pod_lead,candidate,casting_assistant,casting_director,category_manager,change_manager,claim_submitter,comp_ben_analyst,contract_finance_bp,contract_line_manager,contracts_counsel,cs_account_director,cs_manager,cs_specialist,data_engineer,data_lead,data_scientist,delivery_lead,finance_bp,finance_controller,fpa_analyst,global_account_director,hr_bp,it_access_it_admin,it_access_line_manager,junior_creative,line_manager,media_buyer,media_planner,mid_creative,onboarding_it_admin,perf_review_hr_bp,perf_review_line_manager,planner,producer,production_coordinator,program_manager,project_manager,recruiter,regional_account_director,regional_account_lead,regional_controller_emea,regional_controller_us,regional_hr_lead,senior_artworker,senior_copywriter,sourcing_lead,ssc_reviewer,strategy_director,support_engineer,talent_coordinator,vendor_kyc_finance_bp"
```

Then start the server:

```bash
SECRET=$(cat /tmp/durable-secret.txt) \
DURABLE_EVENT_SECRET=$SECRET \
PERSONA_AUTO_CLOSE="$PERSONA_AUTO_CLOSE" \
SIMULATOR_RAMP_AVG_INTERVAL_SECONDS=8 \
uv run uvicorn api.server.main:app --port 3101
```

Other useful env:

- `SIMULATOR_RAMP_AVG_INTERVAL_SECONDS` — controls workflow spawn rate (8 = lively, 30 = calm)
- `DURABLE_EVENT_SECRET` — HMAC secret for `/internal/durable-event`; must match the same value in `api/functions/local.settings.json`

Confirm auto-close on startup — the log will print:

```
[persona_responder] loaded 79 personae (…); AUTO_CLOSE=[…]
```

## 2. Architecture cheat sheet

### 2.1 Component tree (operator-facing)

```
FleetControlShell                 (web/client/components/feed/FleetControlShell.tsx)
├── ToastProvider / ResolutionProvider
├── Header                        (Brand · Search · Clock · TodayChip · RoleSwitcher)
├── LeftRail                      (Saved views · Dashboard link · More ▾)
└── <Routes>
    ├── "/"             Feed      (FilterBar · NewItemsPill · CardList · EmptyFeed)
    ├── "/dashboard"    Dashboard (KPIs + 12-bucket arrivals + recent decisions)
    ├── "/workflows/:id" FeedWithDrawer
    └── "/{analytics|evals|economics|policy}"
```

### 2.2 Card pipeline

`useFeedItems(role, filter)` composes the feed:

1. **Pull raw data** — `useWorkflows`, `useExceptions`, `useFleetManagerStream`, `useOrchestrationStream`, `usePolicyEvents`, `useResolutionStore`.
2. **Dedup HITL ⇄ Exception** — if a workflow has an open Exception, its
   HITL card is dropped (Exception is richer). Tests must respect this:
   `useFeedItems.test.tsx` uses separate workflows (`W-A` for HITL,
   `W-C` for the Exception) to avoid the dedup swallowing the assertion.
3. **All-activity mode** — additionally appends `MilestoneItem`,
   `PolicyItem`, `AgentEventItem`.
4. **Overlay resolutions** — every item present in the live stream that has
   a matching entry in `useResolutionStore` is replaced **in chronological
   slot** with a `ResolvedItem`.
5. **Orphan resolutions** — for resolutions whose original is no longer in
   the stream (server closed the exception → SSE removed it), we materialise
   a free-standing `ResolvedItem` with `origin: undefined` and
   `originId: <original id>` so `ResolvedCard` can still drive Undo.
   Without this step, "All my decisions today" empties the moment the
   server confirms the action.
6. **Role-scope filter** — `role.visibleCardTypes` gates which card types
   the role is allowed to see.
7. **Active filter** — `mine` (resolved cards in last 24h), `domains`,
   `severity`, `search`, then `matchesView` for cross-cut predicates.

### 2.3 Saved views — the dataflow that bit us

Saved views are **declarative filters** defined in `web/shared/roles.ts`
under each `RolePreset.defaultSavedViews`. Each view has `{filter, domains,
severity?, mine?, search?}`.

Click flow:

```
LeftRail button click
  → FleetControlShell.onSelectView(view)
  → builds URL params: filter / severity / mine / domains / search
  → navigate("/?…")
  → Feed picks up URL change via useSearchParams + useEffect
  → setFilterRaw + setPersisted(filter)
  → useFeedItems re-runs
```

**Three subtle invariants** to preserve when changing this code:

1. `onSelectView` must forward **all** SavedView dimensions to the URL —
   regressions here are silent (button highlights, nothing filters).
2. `Feed.tsx` re-syncs state from URL via a `useEffect([params])` block
   guarded by `lastSyncedRef` to avoid an infinite write-loop with the
   `setParams` call inside `setFilter`.
3. Saved-view defaults live in code (`roles.ts`), user-saved views live in
   `localStorage[fleetctl.savedViews.<roleId>]`.

### 2.4 Persistence (client-side)

| Key                                         | Purpose                                          | TTL          |
| ------------------------------------------- | ------------------------------------------------ | ------------ |
| `fleetctl.role`                             | Active `RoleId`                                  | indefinite   |
| `fleetctl.filter.<roleId>`                  | Last applied filter state per role               | indefinite   |
| `fleetctl.savedViews.<roleId>`              | User-created SavedViews                          | indefinite   |
| `fleetctl.notif.<roleId>`                   | Header bell dismissal state (`{seen, clearedAt}`) | indefinite (reset on Clear all) |
| `fleetctl.resolutions.<YYYY-MM-DD>`         | Optimistic resolutions for "All my decisions today" | day-scoped (self-prunes — yesterday's slot is never read) |
| `fleetctl.density`                          | `cosy` / `compact`                               | indefinite   |
| `fleetctl.dark`                             | dark-mode override                               | indefinite   |

### 2.5 Server-side gotchas

- **SSE multiplexer**: `useSSE.ts` uses a module-level `SHARED` map on
  `globalThis.__sseShared` to share one EventSource per URL across all React
  consumers. Chrome's HTTP/1.1 per-domain 6-connection limit was the root
  cause of a previous "feed never updates" bug — do not regress this.
- **Drawer**: rendered as `<aside aria-label="Workflow detail drawer">`
  rather than `role="dialog"`. Esc-close is bound in
  `FleetControlShell.FeedWithDrawer`, **not** in the drawer itself.

## 3. Test posture

- **Vitest** runs from repo root: `npm test` or
  `cd web && npx vitest run client/components/feed client/hooks`.
- Known pre-existing failures (13 at time of writing, not introduced by
  the feed-QoL work): Header / Feed / integration tests that depend on
  fetch-mock plumbing not in this changeset.
- The useFeedItems suite is the canonical regression net for the saved-view
  / resolution / persistence machinery — keep it green.

## 4. Known issues / next up

- **Role switcher**: clicking a different role in `RoleSwitcher` was
  observed to not always update `localStorage[fleetctl.role]` from a
  playwright session. Repro is flaky; likely a focus / outside-click
  timing issue. Live to look at.
- **100-item display cap** is the `PAGE` constant in
  `web/client/components/feed/CardList.tsx`. There **is** a "Show 100 older"
  button at the bottom of the list — surface it more prominently if the
  audit team raises this again.
- **Resolution sync**: optimistic resolutions live in browser localStorage
  only. They are **not** backfilled from the server's decision ledger on
  fresh page load — meaning "All my decisions today" only shows decisions
  made in browsers that still have the localStorage entry. A future
  enhancement could read `/api/workflows?resolvedBy=me&since=today` and
  hydrate from there.

## 5. Quick playwright-cli probes

```bash
# fresh session against the feed, force a clean localStorage
playwright-cli -s=fleet open --browser=chromium http://localhost:5273/
playwright-cli -s=fleet --raw eval "(() => { localStorage.clear(); location.href = location.href; })()"

# saved-view click
playwright-cli -s=fleet click "getByRole('button', { name: 'Critical · needs you' })"
playwright-cli -s=fleet --raw eval "(() => JSON.stringify({url:location.search, items: document.querySelectorAll('article.card-fade-in').length, sev: document.querySelector('select[aria-label=\\\"Severity\\\"]')?.value}))()"

# inspect persisted state
playwright-cli -s=fleet --raw eval "(() => Object.fromEntries(Object.keys(localStorage).filter(k => k.startsWith('fleetctl.')).map(k => [k, localStorage.getItem(k)])))()"
```
