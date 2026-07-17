# Telco Process Profile Substrate - Design

**Date:** 2026-07-17
**Status:** Approved direction
**Scope:** Expand the Telco vertical from nine hero workflows to 37 executable
process handles without creating 37 bespoke implementations.

## 1. Decision

Build:

- 37 independently triggerable workflow types;
- 9 existing hero workflows with their current deep fidelity;
- 28 standard-fidelity process profiles;
- 6 shared Durable workflow engines;
- 8 reusable reasoning skills;
- 4 MCP capability packs;
- one visible, authoritative Telco actor world.

Standard fidelity is not a placeholder. Every process must have a real trigger,
workflow, skill invocation where judgement is required, MCP tool contract,
typed command, world-state mutation, terminal evaluation, process-library
surface, and replay evidence.

The standard profiles may share engines, skills, MCP tools, actors, generic UI,
and proof harnesses. They do not need bespoke visualisations, multiple
alternative outcomes, or deep cross-process coupling.

## 2. Boundaries

### World plane

The Telco actor world remains authoritative for:

- simulation time and seed;
- actors and resources;
- deterministic dynamics;
- injected scenarios;
- validated commands;
- causal journal and replay;
- outcome evaluation.

### MCP plane

MCP exposes system-shaped reads and actions. It does not own hidden simulation
state. Simulator-backed MCP results carry:

```json
{
  "source_mode": "simulated",
  "actor_ids": ["ACC-00002"],
  "event_ids": ["evt-00004544"],
  "trace_id": "retention-evt-00004805",
  "as_of_sim_time": 782.0
}
```

All material MCP actions return a typed command proposal. Only the world
command gateway may mutate authoritative state.

### Workflow plane

Each process profile chooses one shared engine, one or more skills, allowed MCP
tools, an optional HITL gate, a command type, and success/failure evidence.

## 3. Shared vocabulary

### 3.1 Workflow engines

| Code | Engine | Shape |
|---|---|---|
| DDA | Detect Diagnose Act | Detect -> diagnose -> choose action -> execute -> verify |
| FSP | Forecast Simulate Plan | Forecast -> compare scenarios -> approve -> publish/apply |
| CTR | Case Triage Resolve | Open case -> correlate evidence -> resolve -> confirm |
| OFV | Order Fulfil Verify | Validate -> reserve -> fulfil -> test/verify |
| RIG | Risk Investigate Govern | Score -> investigate -> approve/control -> verify |
| ARA | Assist Recommend Act | Understand -> recommend -> human/autonomous action -> record |

### 3.2 Reusable skills

| Code | Skill | Output responsibility |
|---|---|---|
| EC | `evidence-correlator` | Evidence groups, causal links, confidence |
| RIA | `risk-impact-assessor` | Risk tier, impact, affected actors, uncertainty |
| NBA | `next-best-action-planner` | Ranked allowed actions and rationale |
| RM | `resource-matcher` | Feasible resource assignments and constraints |
| PE | `policy-entitlement-evaluator` | Policy outcome, entitlement, approval requirement |
| ER | `exception-resolution-advisor` | Root cause, recovery steps, escalation |
| CD | `communication-drafter` | Governed customer/operator communication |
| SC | `scenario-comparator` | Scenario ranking, trade-offs, recommended option |

Skills receive process-specific evidence, policy, allowed actions, and output
schema. Detection, forecasting calculations, validation, and mutation remain
deterministic code.

### 3.3 MCP capability packs

| Pack | Responsibilities |
|---|---|
| `telco-network-mcp` | Telemetry, alarms, topology, capacity, configuration, bounded network actions |
| `telco-operations-mcp` | Tickets, knowledge, work orders, workforce, spares, change/release cases |
| `telco-commercial-mcp` | Customer 360, product/order, billing/payment, offers, notifications, devices, SIM/number, roaming |
| `telco-twin-mcp` | Forecasts, what-if simulations, GIS/RF abstractions, weather/grid and external benchmarks |

Customer deployments replace the simulator-backed adapters without changing
workflow or skill contracts.

## 4. Existing hero handles

These workflow types remain bespoke and map to one primary source process each.
Their implementation may also provide reusable machinery for related profiles.

| Source | Workflow type |
|---|---|
| OSS-01 | `predictive-site-maintenance` |
| OSS-02 | `network-incident` |
| OSS-04 | `capacity-optimization` |
| OSS-09 | `field-repair-dispatch` |
| OSS-15 | `service-ticket-resolution` |
| OSS-20 | `outage-risk-management` |
| BSS-03 | `proactive-customer-care` |
| BSS-04 | `retention-orchestration` |
| BSS-06 | `order-to-activate` |

## 5. Standard process profiles

Skill and MCP codes refer to Section 3.

### 5.1 OSS

| Source | Workflow type | Engine | Skills | MCP | Command -> success |
|---|---|---|---|---|---|
| OSS-03 | `ran-capacity-planning` | FSP | EC,RIA,SC,NBA | network,twin | `approve_capacity_plan` -> `capacity_plan.approved` |
| OSS-05 | `network-configuration-validation` | RIG | EC,RIA,SC,ER | network,operations,twin | `record_change_validation` -> `change.validation.completed` |
| OSS-06 | `rollout-site-planning` | FSP | SC,NBA,RM | twin,operations | `approve_rollout_plan` -> `rollout.plan.approved` |
| OSS-07 | `network-slice-assurance` | OFV | RIA,SC,NBA,RM | network,twin | `provision_network_slice` -> `network_slice.assured` |
| OSS-08 | `energy-optimization` | DDA | EC,RIA,NBA | network,twin | `apply_energy_action` -> `energy.target.met` |
| OSS-10 | `spares-inventory-optimization` | FSP | EC,RM,NBA | operations,commercial,twin | `transfer_spare_stock` -> `spare_stock.rebalanced` |
| OSS-11 | `site-asset-health-monitoring` | DDA | EC,RIA,NBA | network,operations | `prioritize_asset_work` -> `asset_health.reviewed` |
| OSS-12 | `backhaul-optimization` | DDA | EC,RIA,NBA | network,twin | `apply_backhaul_action` -> `backhaul.stable` |
| OSS-13 | `core-network-anomaly-management` | DDA | EC,RIA,ER | network,operations | `execute_core_runbook` -> `core_service.stable` |
| OSS-14 | `proactive-service-assurance` | DDA | EC,RIA,CD | network,commercial | `open_proactive_assurance` -> `assurance.case.opened` |
| OSS-16 | `network-change-release` | RIG | RIA,SC,ER | network,operations,twin | `advance_network_release` -> `release.verified` |
| OSS-17 | `spectrum-interference-management` | DDA | EC,RIA,NBA | network,twin | `apply_spectrum_action` -> `interference.reduced` |
| OSS-18 | `network-security-response` | RIG | EC,RIA,NBA | network,operations | `apply_security_mitigation` -> `threat.contained` |
| OSS-19 | `experience-benchmarking` | FSP | EC,SC,NBA | network,twin | `publish_benchmark_plan` -> `benchmark.plan.published` |

### 5.2 BSS

| Source | Workflow type | Engine | Skills | MCP | Command -> success |
|---|---|---|---|---|---|
| BSS-01 | `contact-centre-agent-assist` | ARA | EC,RIA,NBA,CD | commercial,operations,network | `publish_agent_guidance` -> `agent_guidance.accepted` |
| BSS-02 | `autonomous-self-service` | ARA | EC,PE,ER,CD | commercial,operations,network | `execute_self_service_resolution` -> `self_service.resolved` |
| BSS-05 | `next-best-action` | ARA | RIA,NBA,PE,CD | commercial,twin | `issue_next_best_action` -> `next_best_action.issued` |
| BSS-07 | `service-provisioning-activation` | OFV | RM,ER,RIA | commercial,network | `provision_service` -> `service.activated` |
| BSS-08 | `billing-dispute-resolution` | CTR | EC,PE,ER,CD | commercial,operations | `resolve_billing_dispute` -> `billing_dispute.resolved` |
| BSS-09 | `revenue-assurance` | RIG | EC,RIA,NBA | commercial,network | `apply_revenue_recovery` -> `revenue_leakage.recovered` |
| BSS-10 | `collections-dunning` | RIG | RIA,PE,NBA,CD | commercial | `apply_collections_plan` -> `collections.plan.applied` |
| BSS-11 | `fraud-prevention` | RIG | EC,RIA,NBA | commercial,operations | `apply_fraud_control` -> `fraud.case.controlled` |
| BSS-12 | `customer-onboarding-kyc` | RIG | EC,RIA,PE,ER | commercial,operations | `complete_customer_kyc` -> `customer.kyc.completed` |
| BSS-13 | `complaint-nps-closed-loop` | CTR | EC,RIA,ER,CD | commercial,operations,network | `resolve_customer_complaint` -> `complaint.closed` |
| BSS-14 | `device-lifecycle-upgrade` | OFV | PE,NBA,RM | commercial,operations | `fulfil_device_upgrade` -> `device_upgrade.completed` |
| BSS-15 | `roaming-experience-steering` | DDA | EC,RIA,NBA,CD | commercial,network | `apply_roaming_steer` -> `roaming.experience.stable` |
| BSS-16 | `number-sim-porting` | OFV | EC,PE,ER | commercial,operations | `complete_number_port` -> `number_port.completed` |
| BSS-17 | `customer-experience-twin` | FSP | EC,RIA,SC,NBA | commercial,network,twin | `publish_cx_experiment` -> `cx_experiment.published` |

## 6. Standard world model

The 28 profiles reuse one explicit standard-process actor:

```python
@dataclass(slots=True)
class TelcoProcessCase:
    id: str
    workflow_type: str
    subject_ids: tuple[str, ...]
    status: str
    facts: dict[str, object]
    allowed_actions: tuple[str, ...]
    outcome: dict[str, object] | None = None
```

Profiles choose one mutation family:

- `network`: update site, asset, service, capacity, spectrum, or threat state;
- `operations`: update ticket, work order, stock, or change state;
- `commercial`: update account, order, bill, payment, offer, device, or SIM state;
- `plan`: persist an approved plan/experiment and its evidence.

Each fixture contains recognisable process-specific facts. The actor is generic;
the workflow, skills, allowed tools, command type, validation, mutation family,
and success event remain process-specific.

## 7. Organisation assumption

Use four functions rather than reproducing every Telco organisation:

1. `network-operations`;
2. `service-operations`;
3. `customer-success`;
4. `commercial-risk`.

Use four approval roots:

1. `network_ops_director`;
2. `service_ops_manager`;
3. `cs_manager`;
4. `commercial_risk_director`.

Customer deployments remap ownership and authority without changing process
profiles.

## 8. UI and proof

Add a `process-library` lens showing all 37 processes with:

- source catalogue ID;
- function;
- maturity (`hero` or `standard`);
- engine;
- skills;
- MCP capability packs;
- current actor case;
- Run action.

The nine heroes retain bespoke lenses. Standard processes use one generic case
view backed by real actor and journal data.

Proof levels:

- contract proof for all 37 registrations, skills, tools, commands and evidence;
- deterministic execution proof for all 28 standard profiles;
- browser proof for one profile per shared engine;
- existing deep live/replay proof for the nine heroes.

## 9. Acceptance criteria

- exactly 37 non-stub Telco domains;
- 9 hero and 28 standard profiles;
- 6 indexed shared engines;
- 8 reusable skills with strict JSON contracts;
- 4 MCP capability modules with no unresolved tools;
- every standard profile opens a workflow from a real sensor event;
- every standard profile invokes at least one declared skill;
- every standard profile calls at least one allowed MCP read tool;
- every standard profile returns its declared typed command;
- every command mutates a real case or existing actor;
- every objective resolves from its declared success evidence;
- process library renders all 37 from the registry;
- world and MCP provenance remain visible;
- Agency remains the default vertical and passes regression.
