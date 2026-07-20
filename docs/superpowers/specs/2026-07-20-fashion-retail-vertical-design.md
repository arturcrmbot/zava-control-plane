# Fashion Retail Vertical Design

**Date:** 2026-07-20  
**Status:** Approved for execution  
**Target:** Reusable UK/EU multi-brand department-store and marketplace vertical

## 1. Decision

Build `fashion` as an automatically discovered, self-contained Zava vertical
pack. The first shippable release is proof-first: one bespoke hero workflow and
seven executable supporting workflows. Every workflow must complete the live
and replay evidence contract in `docs/VERTICAL-PROOF.md`; the pack ships no
stubs.

The hero workflow is **Inventory Rebalancing**. It prevents localized stockouts
and excess end-of-season inventory by moving eligible owned stock between
stores and distribution centres. Low-risk transfers execute automatically.
High-value moves, safety-stock exceptions, partner commitments, cross-border
moves, and markdowns require an explicit human decision.

The primary outcome is higher full-price sell-through and fewer lost sales,
subject to transfer-cost, availability, partner, and allocation-fairness
guardrails.

## 2. Grounding in the Zava constellation

The vertical follows the deployed `compose-org` lifecycle:

1. **Research** records source-backed UK/EU retail anchors and labels facts,
   assumptions, and uncertainties. It does not copy a real retailer's records.
2. **Design** turns the selected operating model and business authority into a
   pack-owned process portfolio and synthetic actor-world contract.
3. **Build** creates `verticals/fashion/` without editing global business
   registries or importing another vertical's assets.
4. **Prove** runs the actor-world-to-evaluation chain, checks identity across
   every runtime surface, records each workflow, and repeats the result in
   replay mode.

Research informs distributions, seasonality, policy language, and operating
assumptions. All customers, sellers, products, orders, inventory positions,
commercial values, and events remain deterministic synthetic data.

## 3. Goals

1. Demonstrate a credible multi-brand department-store and marketplace
   operating model across owned, concession, and third-party inventory.
2. Make inventory imbalance observable, explainable, governable, and
   executable from one causal actor world.
3. Exercise bounded autonomy: automate reversible low-risk actions and route
   consequential actions to the correct persona.
4. Provide a coherent portfolio across merchandising, supply chain,
   marketplace operations, and returns rather than a single isolated demo.
5. Keep all business assets pack-scoped and make invalid or incomplete
   registrations fail at startup.
6. Produce repeatable live and replay evidence for every declared workflow.

## 4. Non-goals

- Reproduce a named retailer, its confidential data, or its proprietary
  allocation algorithms.
- Perform customer-level personalization, dynamic pricing, or autonomous
  markdown execution in the first release.
- Model tax, customs, and consumer law as a complete legal-compliance system.
- Build arbitrary optimization infrastructure when deterministic scoring and
  constrained ranking are sufficient for the acceptance scenarios.
- Create a 30-40 workflow catalogue before the first eight workflows are
  proven.

## 5. Pack architecture

The pack lives under `verticals/fashion/` and is discovered from
`verticals/fashion/manifest.py`. It owns:

```text
verticals/fashion/
  manifest.py
  domains.py
  functions.py
  agents.py
  personas.py
  authority.py
  durable.py
  worlds.py
  world.py
  lifecycle.py
  projections.py
  process_profiles.py
  reference_cases.py
  reference_actions.py
  ui.json
  policies/tools.yaml
  personae/*/SKILL.md
  skills/*/SKILL.md
  mcp_tools/*.py
  recordings/*.jsonl
```

`manifest.py` is the only pack composition root. It builds one immutable
`VerticalPack`, declares every owned root and module, and lazily loads Durable
registrations. The shared kernel continues to own workflow/event contracts,
state, governance enforcement, AG-UI, graph and memory infrastructure, and
reusable UI renderers.

No Fashion implementation may patch `api/shared/domains.py`,
`api/shared/functions.py`, `function_app.py`, Blueprint's global inventory, or
Agency/Telco content. Selecting `ZAVA_VERTICAL=fashion` imports only the Fashion
pack. An explicit unknown vertical, world, capability, persona, workflow, or
ownership reference is a startup error.

## 6. Organisation and process portfolio

### 6.1 Functions

| Function | Responsibility | Primary KPIs |
|---|---|---|
| `merchandising-planning` | Demand, allocation, promotions, and markdown governance | full-price sell-through, lost sales, weeks of supply, markdown exposure |
| `supply-chain-fulfilment` | Supplier recovery, DC/store movement, and order exceptions | on-time availability, transfer lead time, fulfilment success, cost to serve |
| `marketplace-operations` | Seller stock integrity and partner commitments | seller fulfilment rate, stock accuracy, partner response time |
| `customer-returns` | Returns triage, disposition, and recovery | refund cycle time, recovery value, waste avoided |

### 6.2 Workflows

| Workflow type | Kind | Owning function | Trigger and terminal outcome |
|---|---|---|---|
| `inventory-rebalancing` | Hero | merchandising-planning | Inventory imbalance sensor results in an approved or policy-safe stock action and measured post-action availability |
| `demand-spike-response` | Supporting | merchandising-planning | Regional demand anomaly results in a constrained allocation response |
| `promotion-readiness` | Supporting | merchandising-planning | Promotion window risk results in stock, content, and channel readiness decisions |
| `markdown-governance` | Supporting | merchandising-planning | Excess-stock risk results in a reviewed markdown recommendation; no autonomous price mutation |
| `supplier-delay-recovery` | Supporting | supply-chain-fulfilment | Supplier milestone delay results in a substitute, split, expedite, or replan action |
| `fulfilment-exception-resolution` | Supporting | supply-chain-fulfilment | Order allocation failure results in reroute, split fulfilment, or explicit cancellation |
| `marketplace-seller-exception` | Supporting | marketplace-operations | Seller stock or SLA breach results in correction, suppression, or partner escalation |
| `returns-disposition` | Supporting | customer-returns | Returned item inspection results in restock, refurbish, return-to-vendor, recycle, or reject disposition |

The hero gets bespoke orchestration, activities, projection, commands, and
world evaluation. Supporting workflows may share a small number of process
engines when their phase and command contracts genuinely match, but each keeps
its own workflow type, case family, typed command, projection, recording, and
proof evidence.

## 7. Actor world

### 7.1 Actors and entities

The Fashion world contains:

- customers and regional demand cohorts
- UK and EU stores, ecommerce channels, and distribution centres
- brands, suppliers, concession partners, and marketplace sellers
- products, styles, colour/size SKUs, seasons, and lifecycle status
- owned, concession, and third-party inventory positions
- orders, reservations, transfers, promotions, deliveries, and returns

Inventory ownership is explicit on every position. Owned stock can be moved by
an eligible `inventory.transfer` command. Concession stock requires a partner
commitment. Marketplace stock remains seller-controlled and can only receive a
request, offer suppression, or fulfilment-routing action.

### 7.2 Deterministic scale

The acceptance `demo` scale uses a compact but non-trivial world:

- 8 stores across the UK and EU
- 2 distribution centres
- 12 brands, including owned, concession, and marketplace relationships
- 24 styles and 192 colour/size SKUs
- 300 synthetic customers and 14 days of seeded demand history

Seeded randomness derives from a fixed world seed. Identical source state and
commands produce identical events and evaluations.

### 7.3 Golden causal scenario

The hero scenario creates a weather- and campaign-driven demand spike for one
style in a UK store cluster while an EU store cluster retains excess eligible
owned stock. The sensor emits `inventory.imbalance.detected` only after
availability, demand velocity, weeks-of-supply, presentation minimums,
reservation state, ownership, transfer lead time, and transfer cost have been
evaluated.

The plan must distinguish:

- a policy-safe owned-stock transfer that can execute automatically
- a high-value or safety-stock exception requiring approval
- concession or marketplace stock that cannot be moved as owned inventory
- a no-action case where transfer cost or fairness constraints outweigh
  expected full-price sales recovery

The post-command evaluation compares full-price demand served, projected lost
sales, source availability, transfer cost, and allocation fairness against the
unchanged baseline.

## 8. Hero workflow

`inventory-rebalancing` runs these phases:

1. **Detect Imbalance** (`deterministic`) validates the event and snapshots
   relevant inventory and demand versions.
2. **Assess Demand and Constraints** (`agent`) invokes
   `inventory-imbalance-analysis` over typed evidence.
3. **Plan Rebalance** (`agent`) invokes `inventory-rebalance-planner`, which
   returns ranked, explainable candidates rather than mutating state.
4. **Approve Exception** (`hitl`) is N/A for policy-safe owned transfers and is
   mandatory for high-value, safety-stock, cross-border, concession, or partner
   actions.
5. **Execute Stock Action** (`deterministic`) issues one typed, idempotent
   command through a Fashion MCP operation.
6. **Verify Outcome** (`deterministic`) evaluates the resulting world state and
   records the KPI delta.

The default synthetic policy allows an owned-stock transfer to auto-execute
only when all of these conditions hold:

- retail value is at most GBP 10,000
- quantity is at most 50 units
- source presentation and safety stock remain intact
- destination demand confidence meets the configured threshold
- no cross-border, concession, or marketplace commitment is created
- expected recovered margin exceeds transfer cost
- the fairness guardrail does not systematically deprioritize a seller, brand,
  or region

These values are explicit demo assumptions, not claims about industry policy.
Markdowns always require a merchandising decision in this release.

## 9. Personas, authority, skills, and tools

### 9.1 Personas and authority

- `merchandising_director` owns exceptional inventory and markdown authority.
- `inventory_allocation_manager` handles routine allocation review.
- `supply_chain_director` owns expedite and cross-border exceptions.
- `fulfilment_manager` handles order and transfer execution exceptions.
- `marketplace_operations_director` owns seller suppression and partner
  escalation.
- `returns_operations_manager` owns high-value or non-standard dispositions.

Authority rows name exact workflow events and command families. A persona may
not approve its own generated recommendation. Missing authority, stale
evidence, or an unknown command fails closed and is visible in the workflow.

### 9.2 Reasoning skills

The first release provides focused pack-local skills:

- `inventory-imbalance-analysis`
- `inventory-rebalance-planner`
- `promotion-readiness-assessor`
- `markdown-option-advisor`
- `supplier-recovery-planner`
- `fulfilment-resolution-advisor`
- `seller-exception-assessor`
- `returns-disposition-advisor`

Each skill declares only tools registered by the Fashion pack or explicit
kernel capabilities. Skill output is typed evidence or a proposed decision,
never an unvalidated world mutation.

### 9.3 Typed tool and command boundary

Fashion MCP modules expose read operations for demand, inventory, orders,
partners, policies, and returns plus narrowly scoped command operations. The
hero mutation is `inventory.transfer`, with:

- command ID and workflow ID
- source and destination location IDs
- SKU and quantity
- inventory ownership
- expected source and destination versions
- policy decision and approval reference when required
- reason code and evidence digest

The world rejects duplicate command IDs idempotently, stale versions,
ineligible ownership, insufficient available stock, missing approval, and
invalid source/destination combinations. Rejections are domain events, not
silent no-ops.

## 10. Data flow

```text
synthetic demand/inventory change
  -> Fashion world sensor
  -> inventory.imbalance.detected
  -> objective route
  -> InventoryRebalancingOrchestrator
  -> deterministic evidence snapshot
  -> pack-local analysis and planning skills
  -> policy and authority decision
  -> optional HITL event and persona response
  -> typed Fashion command
  -> idempotent world mutation
  -> workflow, graph, memory, AG-UI, and UI projections
  -> deterministic KPI evaluation
  -> curated recording and proof result
```

One workflow ID and one terminal outcome must remain consistent across the
world event log, workflow API, drawer, memory, knowledge graph, AG-UI stream,
graph projection, and Constellation view.

## 11. Failure handling

- Invalid pack references fail during `validate_pack`; the runtime never falls
  back to Agency or Telco.
- Invalid events and commands produce typed rejection reasons and preserve
  source state.
- Transient activity failures use the repository's bounded Durable retry
  policy. Business rejections are not retried.
- Commands use optimistic versions and idempotency keys so orchestration replay
  cannot duplicate transfers, refunds, suppressions, or dispositions.
- Missing or stale evidence blocks agent and HITL decisions.
- Unavailable skills, tools, worlds, or Functions surface an explicit failed or
  unavailable state; they do not emit success-shaped events.
- A no-action outcome is valid only when it records evaluated candidates,
  binding constraints, and the KPI comparison.

## 12. Validation and proof

### 12.1 Automated tests

The implementation adds:

- pack discovery, construction, isolation, and inventory tests
- unit tests for ownership, safety stock, transfer value, cost, fairness,
  version, and approval boundaries
- deterministic world and golden-scenario tests
- typed MCP command and idempotency tests
- one orchestration-path test per workflow
- persona, authority, skill, function ownership, projection, and recording
  registration tests
- API and UI manifest tests under `ZAVA_VERTICAL=fashion`

### 12.2 Permanent proof command

`make prove VERTICAL=fashion` is the permanent clean-checkout acceptance
command. It delegates to `tools/fashion_zava_e2e_proof.sh`, which must:

1. boot the Fashion API, Functions host, actor world, and web application
2. execute the hero golden scenario and one deterministic case for every
   supporting workflow
3. collect the required cross-surface identity evidence
4. satisfy applicable HITL gates and issue each workflow's typed command
5. verify world mutations and terminal evaluations
6. create one curated recording per workflow
7. run with Functions disabled and with the actor world disabled as required
8. assert zero browser errors, zero dropped workflow events, and clean teardown

The proof emits `proof/manifest.json`, tied to the source commit and selected
`fashion` pack, plus screenshots, recordings, logs, and before/after
snapshots beneath `proof/`. A shippable result requires all eight workflows to
pass both live and replay evidence. Deployment remains blocked until the
manifest reports PASS and matches the current source commit.

## 13. Completion criteria

The Fashion vertical is complete only when:

1. `ZAVA_VERTICAL=fashion` builds and validates a pack containing exactly the
   eight designed executable workflows.
2. The inactive Agency and Telco packs contribute no Fashion runtime assets,
   and Fashion contributes no assets when inactive.
3. Every workflow has a deterministic case, terminal projection, curated
   recording, and distinct proof evidence.
4. The hero demonstrates both policy-safe automation and a governed exception.
5. Live and replay proof pass `docs/VERTICAL-PROOF.md` with zero browser errors
   and clean teardown.
6. The proof manifest matches the source commit and permits a later
   `zava-workspace-deploy` invocation.
