"""Phase 0.2 one-pass script:
  1. Repair the 4 known broken rows by hand-coded reconstruction
  2. Apply Phase 0.2 decision edits (#1, #2, #6)
  3. Write all affected CSVs back with proper quoting

Uses csv.reader / csv.writer (list-based, robust to mixed field counts).

Run once, review git diff, commit. Idempotent — safe to re-run: repair only fires
on rows with != 10 fields; edits are string-replacements that no-op if already applied.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path('response/questionnaire answers')
EXPECTED_HEADER = ["Ref", "Section", "Subsection", "Question", "MoSCoW",
                   "Status", "Response", "Key Technologies", "POC Demo", "Reference"]

# =============================================================================
# HAND-CODED REPAIRS for the 4 rows that have corrupted quoting.
# Keyed by (filename, ref). Value is the full 10-field row (all fields as strings).
# The Response values below are reconstructed by concatenating the broken fragments
# in the order they appeared in the corrupted CSV, preserving all content.
# =============================================================================

REPAIRS: dict[tuple[str, str], list[str]] = {

    ("01-platform-vendor.csv", "1.2"): [
        "1.2",
        "Platform & Vendor",
        "Scalability & Performance",
        "What are your high availability and disaster recovery capabilities? Provide multi-region DR details including RTO/RPO SLAs.",
        "Must",
        "Can do today",
        "HA/DR is provided by Azure's infrastructure across all three execution layers. Durable Functions uses Azure Storage for checkpoint persistence with geo-redundant storage (GRS) replication across paired regions. MAF workflow graph checkpoints are preserved across DF replay via the MAF Durable Task extension, so per-phase graph state survives region failover. Workflow state in Cosmos DB supports multi-region writes with automatic failover. Foundry Hosted Agents deploy across availability zones within a region. APIM AI Gateway supports multi-region deployment with Azure Traffic Manager for automatic failover. RTO target: <5 minutes via automated failover at the Azure platform level. RPO target: near-zero for workflow state (Cosmos DB continuous backup with point-in-time restore) and minimal step loss for in-flight GHCP SDK sessions inside agent executors (checkpointing at MAF executor + DF phase boundaries means at most the current executor replays). Audit logs in Azure Log Analytics support geo-redundant archive with 7-12 year retention (immutability via Azure Storage export with immutability policies). Region-pinned per jurisdiction — EU workflows never resolve US-region endpoints; residency is an enforced boundary via APIOps CI gate which rejects PRs that register cross-region backends. All components are backed by Azure's financially-backed SLAs.",
        "Azure Cosmos DB (multi-region), Azure Storage GRS, Azure Traffic Manager, Microsoft Agent Framework (MAF) Durable Task extension, Azure Log Analytics",
        "Demonstrate mid-workflow platform restart in POC1: kill the hosting environment, show workflow resumes from last checkpoint with no data loss.",
        "https://learn.microsoft.com/en-us/azure/cosmos-db/continuous-backup-restore-introduction | https://learn.microsoft.com/en-us/azure/cosmos-db/multi-region-writes | https://learn.microsoft.com/en-us/azure/azure-monitor/logs/data-retention-archive",
    ],

    ("05-governance-oversight.csv", "8.1"): [
        "8.1",
        "Governance & Oversight",
        "Model Registry",
        "Does the platform maintain a centralised catalogue of approved models? Describe the registry.",
        "Must",
        "Can do today",
        "Yes. Three complementary layers. (1) Azure API Center is the unified registry: model metadata (provider, version, training provenance, licensing, regions, parameter counts), lifecycle stages (Design → Preview → Production → Deprecated), version history with author/timestamp/rationale, and cross-cloud reach (Azure-hosted Foundry models plus models from GCP/AWS/on-prem registered alongside). GitHub Actions sync from Git keeps the registry consistent with infrastructure-as-code. (2) Foundry Control Plane provides the platform model catalog itself (1900+ models) and surfaces evaluation/usage metrics. (3) APIM AI Gateway is the runtime governance layer: model routing policies define which models are accessible, with load balancing, failover, spillover, token limits, semantic caching, and cost tracking per model. Jurisdiction-based routing — EU-only model endpoints for GDPR-tagged workflows, US endpoints restricted per jurisdiction policy; residency metadata tracked per model deployment and enforced via APIOps CI gate. Models are selectable per skill — cheap models for triage tasks, frontier models for high-value reasoning. Foundry catalog feed and APIM governance policies control access, all governed centrally with one auditable record per call.",
        "Azure API Center (registry/lifecycle), Foundry model catalog, APIM AI Gateway (runtime governance), Foundry Control Plane",
        "POC1: Show model registry in API Center with lifecycle stages",
        "https://learn.microsoft.com/en-us/azure/foundry/concepts/foundry-models-overview | https://learn.microsoft.com/en-us/azure/api-management/genai-gateway-capabilities",
    ],

    ("05-governance-oversight.csv", "8.4"): [
        "8.4",
        "Governance & Oversight",
        "Model Registry",
        "Can administrators restrict model access by user group, agent sensitivity, or deployment environment? How do you prevent shadow AI (developers connecting to unapproved endpoints)?",
        "Should",
        "Can do today",
        "APIM AI Gateway is the single entry point for all model calls. No agent can bypass APIM to reach a model endpoint directly — network-level enforcement ensures all traffic routes through the gateway. Administrators restrict access by: (1) Agent identity — Entra RBAC scopes which models each Hosted Agent can access. (2) Environment — separate APIM configurations for dev/staging/production with different model allowlists. (3) Sensitivity — APIM policies can restrict frontier models to high-sensitivity workflows only. Shadow AI prevention: APIM is the only route to model endpoints, and APIM itself runs in Private Endpoint mode as the sole public edge. Model endpoints, Cosmos DB, Key Vault, AI Search, Log Analytics, Event Grid, and Foundry sit behind Private Endpoints — no agent can reach them directly. Azure Firewall Premium enforces FQDN allow-listing on outbound traffic. Direct endpoint access is blocked at the network level via Azure Private Endpoints and NSGs. All model calls are logged and auditable. Foundry Control Plane surfaces unauthorised access attempts.",
        "APIM AI Gateway (single entry point), Entra RBAC, Azure Private Endpoints, Foundry Control Plane",
        "N/A",
        "https://learn.microsoft.com/en-us/azure/api-management/genai-gateway-capabilities",
    ],

    ("06-process-orchestration-hitl.csv", "9.1"): [
        "9.1",
        "Process Orchestration & HITL",
        "Workflow Designer",
        "Describe your low-code/no-code workflow designer for defining agentic workflows: conditional logic, loops, parallel processing.",
        "Must",
        "Can do today",
        "Three cooperating layers underpin every workflow and three builder experiences sit on top of them. The execution stack is: (a) Azure Durable Functions as the long-running durable envelope owning phase boundaries, HITL waits at zero compute, checkpoint/replay and geo-replicated state; (b) Microsoft Agent Framework (MAF) workflows v1.0 as the per-phase graph of typed executors with conditional routing, fan-out/fan-in, Pregel BSP execution and native pause/resume — wired to DF via Microsoft's productised MAF Durable Task extension for Azure Functions (the \"Durable Agent Orchestration\" pattern, Feb 2026); (c) GHCP SDK sessions invoked only from MAF agent executor nodes where LLM reasoning is genuinely needed. Most MAF executors are plain Python/C# functions — deterministic by default, agentic by exception. Builder experiences, each producing declarative, Git-committable artefacts flowing through the same APIOps governance pipeline (meeting §6.5 'Low-code artefacts must serialise to the same code/config format as pro-code artefacts'): (1) Pro-code: MAF workflow definitions in Python/.NET (executors, edges, validators) plus GHCP SDK skills in SKILL.md; DF orchestrations invoke MAF workflows as durable activities. Recommended for complex autonomous multi-step workflows. (2) Low-code visual builder — Microsoft Copilot Studio: Microsoft's flagship low-code agent builder with visual drag-and-drop designer, conditional branching, tool bindings (Power Platform connectors + MCP), HITL touchpoints, and knowledge grounding. Copilot Studio agents export as declarative YAML / JSON within Power Platform solutions, Git-committable via Power Platform ALM, versioned through environments (Dev → Test → Prod), and registered with Entra Agent ID (Agent 365 umbrella GA May 2026) — governed by APIM, Purview, and Defender alongside pro-code agents. 60-minute build benchmark hit natively via templates + pre-wired MCP connectors + Foundry IQ knowledge sources, target <30 min. (3) Low-code MCP tools (Azure Logic Apps): visual workflow chaining of 1,400+ connectors (SharePoint, Outlook, Dataverse, SAP, ServiceNow) exposed as MCP tools via APIM's REST→MCP gateway — no-code path for adding tools. Governed identically to hand-written MCP servers. (4) Low-code config (Control Plane UI): skill library (browse/fork/customise), tool catalogue, governance editor, autonomy dials, template fork-and-customise — for operational tuning by process owners, not agent construction; all changes written back to Git via APIOps. (5) 60-minute build benchmark (§6.4): Copilot Studio hits this natively — template + 3 MCP tool connectors + 3 Foundry IQ knowledge sources → publish to Agent 365; end-to-end <30 minutes, scripted for POC evaluation. (6) Agentic builder (design-time): a MAF agent executor generates SKILL.md files from natural-language specifications — typed skill definitions with declared tools, model assignment, governance rules; registered in API Center in Design state; human reviews and approves to promote to Production. Built and demonstrated. (7) Runtime agent assembly: MAF dynamic executor creation + auto-register spawned agents in Entra Agent ID + API Center Design state via governance-gate callback + human promotes to Production. (8) Threadlight (Microsoft delivery accelerator) captures SME interviews into SKILL.md / MAF / MCP artefacts — all Git-inspectable; same API Center governance pathway as hand-written skills.",
        "GHCP SDK (Python), Microsoft Agent Framework (MAF) v1.0 (Python/.NET), MAF Durable Task extension, Azure Durable Functions, Microsoft Copilot Studio (primary low-code visual builder, Power Platform ALM), Azure Logic Apps (low-code MCP), Custom Control Plane UI + template forge (operational config), Threadlight accelerator, Agent 365",
        "POC1: Show a MAF workflow graph per phase (plain-function, agent and validator executors) with parallel invoice processing, orchestrated by a DF envelope with HITL gates. Demonstrate Copilot Studio producing a deployed agent in <30 minutes (60-min build benchmark).",
        "https://github.com/github/copilot-sdk/blob/main/docs/features/skills.md | https://github.com/github/copilot-sdk/tree/main/python",
    ],

    ("07-multi-agent-orchestration.csv", "11.1"): [
        "11.1",
        "Multi-Agent Orchestration",
        "Team Composition",
        "Can you define, deploy, and manage a heterogeneous team of specialised agents with distinct roles, capabilities, and model assignments working toward a shared goal?",
        "Must",
        "Can do today",
        "Yes. WPP gets the outcome of a heterogeneous team — specialised capabilities with distinct roles, allowed tools and model assignments working toward a shared goal — but achieved through skill-based specialisation inside domain-scoped Hosted Agents plus typed executors inside a MAF workflow graph, not through separate agent processes per role. Execution substrate: Azure Durable Functions is the durable envelope around the whole workflow. Inside each phase, a Microsoft Agent Framework (MAF) workflow v1.0 graph wires typed executors — plain-function executors, agent executors, validator executors — with conditional routing, fan-out/fan-in, Pregel BSP execution, and native HITL pause/resume. The DF↔MAF integration uses Microsoft's productised MAF Durable Task extension for Azure Functions (the \"Durable Agent Orchestration\" pattern, Feb 2026). Where a MAF node is an agent executor, it invokes a GHCP SDK session that loads the role-appropriate skill and tool allow-list with its own model assignment (a screening skill may use a cheap model; a candidate evaluation skill a frontier model). The outcome is a heterogeneous team — distinct roles, tools, models, judges/validators — but with meaningful advantages: no inter-agent communication overhead on the hot path, shared typed state on the MAF graph edges rather than ad-hoc message passing, simpler governance (one Entra identity per domain Hosted Agent), and easier operationalisation at fleet scale. MAF also exposes stable orchestration patterns (sequential, concurrent, handoff, group chat, Magentic-One) when a true multi-agent topology is required inside a phase. This architectural choice (skills-based, not multi-agent-process) is deliberate and sells against the WPP brief's default mental model of 9+ specialist agents — see response §18 for the full side-by-side trade-off (latency, cost, governance surface, debuggability, failure modes). A2A (Agent-to-Agent protocol) is reserved for genuinely off-platform / cross-organisation scenarios (partner candidate agents, external supplier agents). Hybrid supported: skills inside a domain, A2A across domains. For matrix-structured tasks (e.g. a role in GroupM with budget from WPP Corp), Fabric IQ's ontology and graph engine is invoked by agent executors for cross-entity navigation.",
        "Microsoft Agent Framework (MAF) v1.0 (sequential/concurrent/handoff/group-chat/Magentic-One), MAF Durable Task extension, GHCP SDK skills (specialisation), Foundry model catalog (tiered models), Azure Durable Functions (durable envelope), Hosted Agent containers (domain-scoped Entra identity), Fabric IQ (cross-entity ontology)",
        "POC2: Show 10+ distinct skills loaded across hiring workflow phases inside MAF agent executors, with different model assignments and tool access, coordinated by a DF envelope with a MAF workflow graph per phase.",
        "https://learn.microsoft.com/en-us/azure/foundry/concepts/foundry-models-overview",
    ],
}

# =============================================================================
# PHASE 0.2 DECISION EDITS
# Each edit targets a (file, ref) + a field + an old->new string replacement.
# =============================================================================

EDITS: list[tuple[str, str, str, str, str]] = [
    # DECISION #1 — Control Plane UI is not "primary low-code builder surface"
    ("01-platform-vendor.csv", "2.1", "Response",
     "Control Plane UI skill library + template forge as the primary low-code builder surface (produces the same SKILL.md / MAF / APIM artefacts as pro-code, meeting §6.5 parity);",
     "Control Plane UI skill library + template forge for operational configuration by process owners (autonomy dial tuning, template fork-and-deploy) — not a builder surface; Copilot Studio remains the primary low-code visual builder with declarative YAML/JSON artefacts Git-committable via Power Platform ALM;"),

    # DECISION #2 — Agent 365 is GA May 2026, not "can do today"
    ("05-governance-oversight.csv", "8.5", "Response",
     "Agent 365 adds another layer: agent registration in the M365 admin center with Entra Agent ID, Purview, and Defender integration.",
     "Agent 365 (preview today, GA May 2026) adds another layer: agent registration in the M365 admin center with Entra Agent ID, Purview, and Defender integration."),
    ("05-governance-oversight.csv", "8.6", "Response",
     "Agent 365 extends this with Purview-enforced data classification and Defender threat detection per agent identity.",
     "Agent 365 (preview today, GA May 2026) extends this with Purview-enforced data classification and Defender threat detection per agent identity."),
    ("05-governance-oversight.csv", "8.8", "Response",
     "(4) Agent 365: administrators manage agent visibility and access in the M365 admin center — restrict which users can interact with which agents.",
     "(4) Agent 365 (preview today, GA May 2026): administrators manage agent visibility and access in the M365 admin center — restrict which users can interact with which agents."),
    ("05-governance-oversight.csv", "8.10", "Response",
     "Entra Agent ID (part of Agent 365) establishes agents as first-class identities in Microsoft Entra ID.",
     "Entra Agent ID (the identity layer; usable in preview today) establishes agents as first-class identities in Microsoft Entra ID; the full Agent 365 umbrella reaches GA May 2026."),
    ("08-multi-surface-engagement.csv", "12.5", "Response",
     "Capability-based routing: Agent 365 determines recipient.",
     "Capability-based routing: Agent 365 (preview today, GA May 2026) determines recipient."),
    ("15-builder-experiences.csv", "19.2", "Response",
     "Copilot Studio agents register in Agent 365 with first-class Entra Agent ID, are governed by APIM, Purview, and Defender, and appear alongside GHCP SDK agents in the Control Plane.",
     "Copilot Studio agents register with Entra Agent ID (Agent 365 umbrella GA May 2026), are governed by APIM, Purview, and Defender, and appear alongside GHCP SDK agents in the Control Plane."),
    ("15-builder-experiences.csv", "19.4", "Response",
     "Copilot Studio agents register in Entra Agent ID + Agent 365 automatically",
     "Copilot Studio agents register in Entra Agent ID automatically (Agent 365 umbrella GA May 2026)"),
    ("20-agent-identity-authority.csv", "24.1", "Response",
     "Entra Agent ID (part of Agent 365) establishes agents as first-class identity objects in Microsoft Entra ID — distinct from service accounts.",
     "Entra Agent ID establishes agents as first-class identity objects in Microsoft Entra ID — distinct from service accounts. Entra Agent ID is usable in preview today; the full Agent 365 umbrella (admin-center lifecycle, cross-service governance flows) reaches GA May 2026."),
    ("20-agent-identity-authority.csv", "24.2", "Response",
     "Agent 365 lifecycle management supports temporary agent activations for specific projects.",
     "Agent 365 lifecycle management (preview today, GA May 2026) supports temporary agent activations for specific projects."),
    ("20-agent-identity-authority.csv", "24.3", "Response",
     "Agent 365 records the responsible person/sponsor for each agent identity.",
     "Agent 365 (preview today, GA May 2026) records the responsible person/sponsor for each agent identity."),
    ("21-org-topology-awareness.csv", "25.2", "Response",
     "(1) Role and authority — Agent 365 determines who has the authority to",
     "(1) Role and authority — Agent 365 (preview today, GA May 2026) determines who has the authority to"),
    ("23-continuous-process-evolution.csv", "27.4", "Response",
     "(5) Agent 365 supports lifecycle actions (activate, block, delete) for agents that are no longer needed;",
     "(5) Agent 365 (preview today, GA May 2026) supports lifecycle actions (activate, block, delete) for agents that are no longer needed;"),
    ("28-regional-sovereignty.csv", "32.5", "Response",
     "Agent 365 correlates signals across Entra ID Protection, Defender, and Purview to assess agent risk.",
     "Agent 365 (preview today, GA May 2026) correlates signals across Entra ID Protection, Defender, and Purview to assess agent risk."),

    # DECISION #6 — align builder taxonomy to the 8-row structure
    # Note: 06/9.1 and 15/19.2 are updated; 06/9.1 also got fully rebuilt in REPAIRS above.
    ("15-builder-experiences.csv", "19.2", "Response",
     "(4) Note on .NET parity: MAF ships with full .NET parity — teams preferring C# build against MAF .NET with the same skills, MCPs, and governance; artefacts serialise identically. For complex autonomous multi-step workflows that need deterministic graph primitives (validator chains, crystallisation pipelines), pro-code (GHCP SDK + MAF) is the recommended path; Copilot Studio excels at the breadth of citizen-developer scenarios.",
     "(4) Note: the full builder taxonomy also includes pro-code (GHCP SDK + MAF, Python/.NET), the 60-minute-build benchmark via Copilot Studio templates + pre-wired MCP connectors, an agentic design-time builder (MAF executor generates SKILL.md from natural-language specs), runtime agent assembly, and Threadlight (SME-interview knowledge capture). For complex autonomous multi-step workflows that need deterministic graph primitives (validator chains, crystallisation pipelines), pro-code (GHCP SDK + MAF) is the recommended path; Copilot Studio excels at the breadth of citizen-developer scenarios. See response §9 for the full 8-mode taxonomy."),
]

FIELD_INDEX = {name: i for i, name in enumerate(EXPECTED_HEADER)}


def process_file(path: Path) -> dict[str, int]:
    stats = {"read": 0, "repaired": 0, "edited": 0, "written": 0, "already_ok": 0}
    with path.open(encoding='utf-8', newline='') as f:
        reader = csv.reader(f)
        header = next(reader)
        if header != EXPECTED_HEADER:
            raise RuntimeError(f"{path.name}: unexpected header {header}")
        rows: list[list[str]] = list(reader)
    stats["read"] = len(rows)

    # Repairs: replace rows with broken field counts using the hand-coded table.
    file_repairs = {ref: new_row for (fname, ref), new_row in REPAIRS.items()
                    if fname == path.name}
    if file_repairs:
        for i, row in enumerate(rows):
            if len(row) != len(EXPECTED_HEADER) and row and row[0] in file_repairs:
                assert len(file_repairs[row[0]]) == len(EXPECTED_HEADER)
                rows[i] = file_repairs[row[0]]
                stats["repaired"] += 1

    # Assert no broken rows remain (would break DictWriter or downstream consumers).
    for i, row in enumerate(rows):
        if len(row) != len(EXPECTED_HEADER):
            raise RuntimeError(
                f"{path.name} row {i+1} (Ref={row[0] if row else '?'}): "
                f"{len(row)} fields, expected {len(EXPECTED_HEADER)} — no repair defined"
            )

    # Edits: string replacements in specific field of specific ref.
    file_edits = [(ref, field, old, new) for (fname, ref, field, old, new) in EDITS
                  if fname == path.name]
    for ref, field, old, new in file_edits:
        col = FIELD_INDEX[field]
        for row in rows:
            if row[0] == ref:
                if old in row[col]:
                    row[col] = row[col].replace(old, new)
                    stats["edited"] += 1
                elif new in row[col]:
                    # Already applied — idempotent run
                    stats["already_ok"] += 1
                else:
                    raise RuntimeError(
                        f"{path.name} Ref {ref} field {field!r}: edit's old text not found. "
                        f"Expected to find: {old[:120]!r}..."
                    )
                break
        else:
            raise RuntimeError(f"{path.name} Ref {ref}: row not found for edit")

    # Write back (we always write — idempotent).
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(EXPECTED_HEADER)
        writer.writerows(rows)
    stats["written"] = len(rows)

    return stats


def main() -> int:
    affected_files = {fname for (fname, _ref) in REPAIRS} | {fname for (fname, _ref, _f, _o, _n) in EDITS}
    total = {"read": 0, "repaired": 0, "edited": 0, "written": 0, "already_ok": 0}
    for fname in sorted(affected_files):
        path = ROOT / fname
        if not path.exists():
            print(f"ERROR: {fname} not found", file=sys.stderr)
            return 2
        s = process_file(path)
        print(f"  {fname}: read={s['read']} repaired={s['repaired']} "
              f"edited={s['edited']} already_ok={s['already_ok']} written={s['written']}")
        for k in total:
            total[k] += s[k]

    print()
    print(f"TOTAL: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
