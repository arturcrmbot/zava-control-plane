---
goal: Convert the Zava substrate from per-phase MAF graphs to per-segment agentic loops with per-skill identity, provider-neutral LLM runtime, and segment-output Pydantic validators
version: 1.0
date_created: 2026-05-19
last_updated: 2026-05-19
owner: arturzielinski
status: 'Planned'
tags: ['architecture', 'refactor', 'agt', 'maf', 'hiring', 'reference-architecture']
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

Today every workflow phase opens a fresh single-skill `CopilotSession`, runs one LLM turn, and tears it down. A hiring workflow with 10 phases costs ~10 subprocess cold starts, ~10 sessions, and the model never sees more than one skill's slice of the problem. The substrate also has three side-by-side abstractions doing related work (AGT, MAF, Durable Functions) where one or two would suffice, plus a hard-coded `finance-agent` runtime label that contradicts AGT's per-skill identity design (fixed in commit `725ad18a`).

This plan does four things:

1. Wire AGT enforcement into the GHCP SDK's pre-tool hook so the per-skill capability allow-list is actually enforced at MCP call time.
2. Define an `LLMRuntime` protocol so the substrate is not pinned to GHCP forever.
3. Convert the Hiring workflow from per-phase graphs to per-segment agentic loops, with Durable owning segment boundaries / HITL / retries and Pydantic owning segment-output validation. Roll out one segment first, prove it, then the rest.
4. Update the `compose-domain` skill (and a small note in the cross-repo `zava-design-skills/compose-org`) so newly composed domains use the segment shape, not the per-phase MAF graph shape. Rewrite the published blueprint article to describe the segment + agentic-loop model honestly.

MAF stays in the dependency tree but stops being on the main path. It remains an optional pattern documented for the cases where in-process graph chaining (parallel fan-out + merge, agent → validator → agent inside one activity) is genuinely useful.

## 1. Requirements & Constraints

### Functional requirements

- **REQ-001**: A workflow with N consecutive non-HITL phases must complete in ≤ ⌈N / segment_size⌉ `CopilotSession`s, not N sessions. For Hiring Segment B that is 4 phases → 1 session.
- **REQ-002**: Within a segment, the model decides which skill to invoke and in what order. The user prompt must not prescribe skill ordering ("first call X then Y"). Determinism comes from the segment's skill allow-list, MCP allow-list, and output schema.
- **REQ-003**: Each MCP call inside a session must pass through AGT capability check before firing. Denials must surface to the model as a tool error so it can adapt within the same loop.
- **REQ-004**: Each segment must declare a Pydantic output model. The orchestrator runs a `validate_segment_output` activity after the segment returns. On validation failure, the orchestrator retries the segment up to `SEGMENT_MAX_RETRIES` (default 2) with the validator error fed back into the next prompt as additional context.
- **REQ-005**: HITL boundaries, phase order, conditional branching, audit checkpoints and retry semantics remain in the Durable orchestrator. The LLM is never given control of these.
- **REQ-006**: Every span emitted by the GHCP session must be tagged with the actual per-skill agent_id (the fix landed in commit `725ad18a`) and with the segment_id.
- **REQ-007**: The runtime LLM client must be obtained through an `LLMRuntime` protocol, not by importing `copilot.CopilotClient` directly. The included implementation is `GHCPRuntime`; the protocol is shaped so a `ClaudeRuntime` / `AzureOpenAIRuntime` can be added in <300 lines without touching segment code.
- **REQ-008**: The Hiring workflow under segment mode must produce outputs structurally equivalent (Pydantic-equal on shared fields) to the current per-phase outputs on a fixed set of replay inputs.

### Security requirements

- **SEC-001**: When `AGT_ENFORCE=1`, an MCP call that fails the AGT capability check must be denied before the MCP is invoked. The denial event must be written to the audit ledger with the agent_id, attempted action, and denial reason.
- **SEC-002**: Per-skill Ed25519 signing of audit ledger entries must continue to work for every MCP call inside a segment session. The kid on the JWS header is the skill name that initiated the call, not the segment name.
- **SEC-003**: The segment activity must not log raw GHCP tokens, MCP credentials or PII in span attributes or webhook payloads beyond what `_wrapper.py` already truncates (4096-byte response text cap).

### Constraints

- **CON-001**: Durable Functions remains the orchestration backbone. No replacement.
- **CON-002**: Backward compatibility: the existing per-phase activities (`hiring_budget_activity_trigger`, `hiring_job_design_activity_trigger`, …) must continue to work and be selectable via a feature flag (`HIRING_SEGMENT_MODE=off|b|all`), so we can A/B compare and roll back without a deploy.
- **CON-003**: No new third-party dependencies. The `LLMRuntime` protocol is plain `typing.Protocol`. Pydantic is already in the tree.
- **CON-004**: No Entra Agent ID, no managed identity, no per-skill Entra principals in this plan. AGT signing keys stay Ed25519 + Key Vault (prod) / `azurite-data/agt-keys/` (dev). The article must not imply Entra.
- **CON-005**: The `agent-framework`, `agent-framework-github-copilot`, `agent-framework-azurefunctions` packages stay installed (no `pyproject.toml` removal in this plan) so existing per-phase graphs keep working through the rollout. A separate cleanup plan retires them later if telemetry shows they are unused.
- **CON-006**: Article must remain accurate after every phase of this plan, not only at the end. We don't ship the rewrite before the segment code lands.

### Guidelines and patterns

- **GUD-001**: Goal-shaped prompts only. The segment prompt names the deliverable and JSON schema; it does not name the procedure.
- **GUD-002**: One feature flag per change. `LLM_RUNTIME=ghcp|claude|aoai`, `AGT_ENFORCE=0|1`, `HIRING_SEGMENT_MODE=off|b|all`. No coupled flags.
- **GUD-003**: Every new module is reviewable top-to-bottom in ≤ 200 lines. If a file grows beyond that, split it.
- **PAT-001**: The reference-architecture default path is `Durable orchestrator → segment activity → run_agent_session(LLMRuntime, skills, mcps) → segment-output Pydantic validator activity`. MAF is documented as an optional in-activity-graph pattern, not the default.

## 2. Implementation Steps

### Implementation Phase 1 — AGT enforcement wired into the session

- GOAL-001: Replace `PermissionHandler.approve_all` in `_wrapper.py` with a policy-aware handler that calls the governance kernel, gated by `AGT_ENFORCE`. End state: a segment session whose model attempts to call an MCP not in the calling skill's allow-list gets a denial that the model can see and react to.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Add `class AGTPermissionHandler` in `api/functions/graphs/executors/agents/_permission.py`. Constructor takes `skill_label`, `workflow_id`. `__call__(tool_call)` resolves the MCP operation name to a tool_id, calls `governance_kernel.check_capability(skill_label, tool_id, args)` and returns allow/deny. On deny, append a structured audit entry via `app_state.store.append_audit(...)` and return `PermissionDecision.DENY` with a reason string the SDK forwards to the model. | | |
| TASK-002 | In `api/functions/graphs/executors/agents/_wrapper.py:run_agent_session`, replace `"on_permission_request": PermissionHandler.approve_all` with `AGTPermissionHandler(skill_label=skill_label, workflow_id=workflow_id) if os.environ.get("AGT_ENFORCE","0") == "1" else PermissionHandler.approve_all`. Import the handler at module top. | | |
| TASK-003 | Verify `api/server/services/governance/kernel.py` exposes `check_capability(agent_id: str, tool_id: str, args: dict) -> CapabilityDecision` (allow / deny + reason). If not, add a thin wrapper that composes the existing `policy_compiler`, `kill_switch` and `agents.AGENTS[agent_id].allowed_tools` checks. Do not introduce a new policy layer. | | |
| TASK-004 | Add `tests/api/server/services/governance/test_permission_handler.py`. Cases: (a) allowed tool + AGT off → approve, (b) allowed tool + AGT on → approve + audit entry, (c) disallowed tool + AGT on → deny + audit entry, (d) kill-switch active for (skill, action) → deny. | | |
| TASK-005 | Run `pytest tests/api/server/services/governance/ -q` and `pytest tests/api/unit/test_state_store.py -q`. Both must pass with `AGT_ENFORCE=0` (default) and `AGT_ENFORCE=1`. | | |

### Implementation Phase 2 — `LLMRuntime` protocol

- GOAL-002: Define a 1-file provider-neutral abstraction over the LLM client. Move the existing GHCP call path behind it. No behaviour change; future Claude / Azure OpenAI providers are addable in one new file each.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-006 | Create `api/functions/graphs/executors/agents/runtime.py` defining `class LLMRuntime(typing.Protocol)` with one method: `async def run_session(self, *, prompt: str, system_message: str \| None, skill_directories: list[Path], tools: list, permission_handler, attachments: list[dict] \| None, model: str, timeout_s: float) -> LLMRuntimeResult`. `LLMRuntimeResult` is a Pydantic model with fields `text: str`, `tool_calls: list[ToolCallRecord]`, `input_tokens: int \| None`, `output_tokens: int \| None`, `raw_event: Any`. | | |
| TASK-007 | Create `api/functions/graphs/executors/agents/runtime_ghcp.py` with `class GHCPRuntime(LLMRuntime)`. Move the `CopilotClient`/`create_session`/`send_and_wait`/`disconnect` body from `_wrapper.py` into `GHCPRuntime.run_session`. Keep the OTEL session-event bridge inside `_wrapper.py` because it is independent of the provider. | | |
| TASK-008 | Refactor `_wrapper.py:run_agent_session` to: (a) instantiate a runtime via `_get_runtime()` which reads `os.environ.get("LLM_RUNTIME","ghcp")` and returns the matching implementation, defaulting to `GHCPRuntime`, (b) call `runtime.run_session(...)`, (c) keep the rest of the function unchanged (OTEL spans, agent_name derivation, attachments, return shape). | | |
| TASK-009 | Add `tests/api/functions/agents/test_runtime_protocol.py`. Cases: (a) `GHCPRuntime` instantiates and matches the `LLMRuntime` protocol via `isinstance` with `runtime_checkable`, (b) a stub `FakeRuntime` implementing the protocol drops in to `_wrapper.py` when `LLM_RUNTIME=fake` and produces the same return shape. The fake never opens a subprocess. | | |
| TASK-010 | Update `pyproject.toml` extras: leave `github-copilot-sdk`, `agent-framework`, `agent-framework-github-copilot`, `agent-framework-azurefunctions` in `dependencies` (still used). Add a comment block above them stating they are runtime-optional once `LLM_RUNTIME != ghcp` for non-GHCP deployments. No dependency removal. | | |

### Implementation Phase 3 — Hiring Segment B (candidate discovery) agentic loop

- GOAL-003: Replace `hiring_job_design_activity` + `hiring_sourcing_activity` + `hiring_triage_activity` + `hiring_screening_activity` (Phases 2–5) with one `hiring_segment_b_activity` that opens one session, loads all four skills, and returns a `SegmentBOutput`. Feature-flagged.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-011 | Create `api/functions/segments/__init__.py` and `api/functions/segments/hiring_b.py`. Define `class SegmentBOutput(BaseModel)` with fields `verdict: Literal["low","borderline","strong"]`, `jd_draft_id: str`, `sourcing_pool_id: str`, `candidates: list[CandidateScore]`, `rationale: str`. | | |
| TASK-012 | In `api/functions/segments/hiring_b.py` add `async def run_segment_b(enriched: dict) -> dict`. It calls `run_agent_session` with `skill_dir=None`, `skill_label="hiring-segment-b"`, `tools=<resolved Tool list for policy_search + ocr_extract>`, and a goal-shaped prompt built by `_build_segment_b_prompt(enriched)`. The prompt names the deliverable schema and lists the four available skills + two MCPs by name. It does NOT prescribe order. `skill_directories` passed to the runtime is the list `[skills_dir/jd-drafter, skills_dir/sourcing-orchestrator, skills_dir/cv-crystalliser, skills_dir/auto-shortlister]`. | | |
| TASK-013 | Add `hiring_segment_b_activity_trigger` in `function_app.py` next to the existing hiring activities. The activity calls `asyncio.run(run_segment_b(input_dict))`, returns the result dict. Same pattern as existing `hiring_*_activity_trigger` wrappers. | | |
| TASK-014 | Add `validate_segment_b_output_activity_trigger` in `function_app.py` that takes `output_dict` and returns `{"ok": True, "output": output_dict}` or `{"ok": False, "errors": [...]}` based on `SegmentBOutput.model_validate`. | | |
| TASK-015 | Patch `api/functions/workflows/hiring.py:hiring_orchestration` to branch on `os.environ.get("HIRING_SEGMENT_MODE", "off")`. When `b` or `all`, after the budget HITL completes, replace the four `call_activity` lines (Job Design / Sourcing / Triage / Screening) with: one `call_activity("hiring_segment_b_activity_trigger", enriched)`, then `call_activity("validate_segment_b_output_activity_trigger", segment_result)`, then on `ok==False` retry up to `SEGMENT_MAX_RETRIES` (default 2) appending the validator errors to the next call's input. On final failure, write a `checkpoint_activity_trigger` event of kind `"segment.failed"` and re-raise. When the flag is `off`, keep the existing four-phase path verbatim. | | |
| TASK-016 | Add `tests/api/unit/test_hiring_segment_b.py`. Cases: (a) `run_segment_b` invoked with a fake `LLMRuntime` returns a valid `SegmentBOutput`, (b) malformed runtime output triggers a Pydantic validation failure surface, (c) orchestrator under `HIRING_SEGMENT_MODE=b` calls `hiring_segment_b_activity_trigger` once and skips the four per-phase triggers, (d) orchestrator under `HIRING_SEGMENT_MODE=off` calls the four per-phase triggers and never calls the segment one. Use `unittest.mock` for Durable context, the same shape as `test_hiring_voice_phase.py`. | | |
| TASK-017 | Create `scripts/replay_hiring_compare.py` that loads N (default 5) fixed enriched-input records from `data/synthetic/hiring/` or recorded fleet events, runs each under both `HIRING_SEGMENT_MODE=off` and `HIRING_SEGMENT_MODE=b`, and prints a side-by-side comparison: latency, session count, input/output token totals, output schema equality on shared fields. Use `FakeRuntime` for deterministic comparison; document that real-LLM comparison requires `LLM_RUNTIME=ghcp`. | | |
| TASK-018 | Run `pytest tests/api/unit/test_hiring_segment_b.py -q` and `python scripts/replay_hiring_compare.py` against the fake runtime. Both must pass. Capture the latency / token output into `tmp/segment-b-baseline.txt` and commit it as a sanity reference (not used by CI). | | |

### Implementation Phase 4 — Roll out segments D, E, F

- GOAL-004: Once Segment B passes Phase 3, repeat the pattern for D (Interview decisioning, Phase 7), E (Compliance + Offer prep, Phases 8 + 9), F (Onboarding, Phase 10). Phase A (Budget, Phase 1) and Phase C (Voice, Phase 6) are single-skill and stay as their existing single-activity calls; they do not become segment activities.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-019 | Repeat the Phase 3 task pattern for Segment D. Files: `api/functions/segments/hiring_d.py`, `SegmentDOutput` Pydantic model, `hiring_segment_d_activity_trigger`, `validate_segment_d_output_activity_trigger`. Skills loaded: `interview-recommender`. (Currently Phase 7 is one skill; the value here is structural consistency and future-proofing if Phase 7 grows.) | | |
| TASK-020 | Repeat for Segment E. Files: `api/functions/segments/hiring_e.py`, `SegmentEOutput` Pydantic model, triggers. Skills loaded: `betrvg-checker`, `jurisdiction-router`, `offer-personaliser`. MCPs: `policy_search`. | | |
| TASK-021 | Repeat for Segment F. Files: `api/functions/segments/hiring_f.py`, `SegmentFOutput` Pydantic model, triggers. Skills loaded: `onboarding-buddy`. MCPs: `avatar_render`. | | |
| TASK-022 | Extend `HIRING_SEGMENT_MODE` parser to accept `b`, `d`, `e`, `f`, `all`, or any comma-separated subset (`b,e`). Each enabled segment swaps in its activity; disabled segments fall back to the per-phase activities. | | |
| TASK-023 | Add segment-mode tests for D / E / F mirroring `test_hiring_segment_b.py` cases (a)–(d). | | |
| TASK-024 | Run `scripts/replay_hiring_compare.py` with `HIRING_SEGMENT_MODE=all` against the fake runtime. Net session count for an end-to-end hiring run must be ≤ 6 (was ~10). Record in `tmp/segment-all-baseline.txt`. | | |

### Implementation Phase 5 — `compose-domain` skill update

- GOAL-005: When the user composes a new domain via the design-time skill, the default scaffold must emit segment activities + Pydantic output models, not per-phase MAF graphs. The MAF graph path remains available behind an explicit flag for the rare in-activity-graph case.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-025 | Edit `docs/superpowers/skills/compose-domain/SKILL.md`. In §"v3 generators" section, change the default phase shape from `kind: agent` → `1 MAF graph file with agent → validator → terminal` to: default → `1 segment activity at api/functions/segments/<wt_snake>_<segment_letter>.py with a Pydantic <Segment><Letter>Output model and matching validate_<wt_snake>_<segment_letter>_output_activity_trigger`. Add a new optional `kind: graph` for cases where in-process chaining is genuinely required; document the criteria (parallel fan-out with merge; agent → validator → agent without an HITL gate). | | |
| TASK-026 | Update the path table in the same SKILL.md to list segment paths alongside legacy graph paths. New rows: `segment activity`, `segment output Pydantic model`, `segment validator activity`. Mark the graph rows as `legacy / kind:graph only`. | | |
| TASK-027 | Update the `compose-domain` worked example (Step 7 in the skill) to walk through generating a segment by default. Keep one short appendix showing the legacy graph generation for `kind: graph`. | | |
| TASK-028 | Add a new section "When to use kind:graph" to the same SKILL.md. State the three legitimate triggers verbatim: (1) parallel fan-out with blind merge, (2) agent → validator → agent inside one activity, (3) saga/compensation chains where Durable round-trips per node are unacceptable. Everything else: default segment. | | |
| TASK-029 | Update `docs/superpowers/skills/compose-domain/templates/` (if present) — replace the per-phase MAF graph template with a segment activity template. Verify by `find docs/superpowers/skills/compose-domain -name '*.template.py'` and rewriting any that emit `WorkflowBuilder`/`TrackedExecutor`. | | |

### Implementation Phase 6 — Cross-repo coordination note

- GOAL-006: Note the change in `zava-design-skills` so a future composer working in that repo doesn't generate against the obsolete shape.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-030 | In `zava-design-skills/skills/compose-org/README.md`, in the section that mentions "Generate orchestrator/graphs/skills for new domains," append a one-paragraph note: "The target substrate's compose-domain skill now emits segment activities by default rather than per-phase MAF graphs. compose-org does not generate these files itself; it forks the substrate, after which compose-domain (executed inside the fork) produces the segment scaffold. See zava-control-plane/plan/refactor-substrate-agentic-segments-1.md for the canonical pattern." | | |
| TASK-031 | Confirm there is no other file in `zava-design-skills` that hard-codes the MAF-graph shape. Run `grep -rln 'WorkflowBuilder\|TrackedExecutor\|MAF\|agent_framework' ~/dev/github-repos/zava-design-skills`. Address any hits with a similar pointer note or — if the file is a template that actually emits code — change the template. | | |

### Implementation Phase 7 — Article rewrite

- GOAL-007: Update the published blueprint article in `web/blueprint/src/sections/` so it describes the segment + agentic-loop model honestly. No claim of Entra. No claim of per-workflow single session. No claim of "thousands of agents torn down". Each claim in the article must be checkable against the code that ships after Phase 4.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-032 | Rewrite `web/blueprint/src/sections/Argument.tsx` caption 1 ("The harness"). New title: "Agentic segments inside deterministic workflows." New body: a workflow is a sequence of segments, each segment opens one short-lived agent session that can use a bounded set of skills and MCPs, segment boundaries and HITL gates live in Durable orchestrator code. Replace the current "agents are spawned … and torn down" framing with the segment framing. | | |
| TASK-033 | Rewrite `web/blueprint/src/sections/Argument.tsx` caption 4 ("The foundation"). Clarify what "each agent runs under its own identity" actually means in this repo: per-skill `agent_id`, per-skill Ed25519 signing key, AGT capability allow-list enforced at MCP-call time via the pre-tool hook. Explicitly say there is no Entra Agent ID and no per-skill Entra principal in this substrate today. | | |
| TASK-034 | Audit every section file under `web/blueprint/src/sections/` for any phrase implying Entra, Agent 365, managed identity, per-workflow single session, or thousands-of-agents lifecycle. List violations in `tmp/article-audit.md`. Fix each one in place. The auditing script is a single `grep -E 'entra\|agent 365\|managed identity\|principal\|thousands of agents\|torn down'` over the section files. | | |
| TASK-035 | Add a new short paragraph to `web/blueprint/src/sections/Composition.tsx` explaining that a workflow's `n` phases collapse into `m ≤ n` segments at HITL boundaries, that the model decides skill order inside a segment, and that the orchestrator decides everything else. Cite the hiring example: 10 phases → 6 segments → 5 HITL waits. | | |
| TASK-036 | Build and deploy: `cd web/blueprint && npm run build`, then `git commit && git push origin main`. GitHub Pages workflow `deploy-blueprint-pages.yml` redeploys. Verify the live bundle hash changes and the new captions are visible at https://arturcrmbot.github.io/zava-control-plane/. | | |

## 3. Alternatives

- **ALT-001**: **Per-workflow single session (Option 3a from the design discussion).** Open one session per workflow that lives across all phases including HITL. Closest to the autonomous-agent paradigm. Rejected because HITL waits can be days, GHCP `CopilotSession` cannot be serialised across that gap, and we lose deterministic phase order which is the part of the article's value proposition we want to keep.
- **ALT-002**: **Decoupled session pool (Option 3c).** A separate long-lived process holds live `CopilotSession`s keyed by `workflow_id`, Durable signals it. Cleanest separation but ~4–6 weeks of work, new failure mode (pool crash = lost context), and sessions held in RAM for multi-day HITL waits are operationally painful.
- **ALT-003**: **Keep MAF graphs as the default; add segment as an optional pattern.** Inverse of the choice taken. Rejected because MAF earns nothing for the linear `agent → validator → terminal` graphs we have today, and a reference architecture should default to the simpler path.
- **ALT-004**: **Add a third enforcement layer (custom hook framework over GHCP SDK).** Briefly considered. Rejected because AGT already does pre-tool enforcement once `AGT_ENFORCE=1` is wired in. Inventing a parallel framework is exactly the "five ways to skin a cat" the architecture review pushed back on.

## 4. Dependencies

- **DEP-001**: `github-copilot-sdk>=0.2.1` — present in `pyproject.toml`. Used by `GHCPRuntime`.
- **DEP-002**: `pydantic>=2.x` — already in the tree.
- **DEP-003**: `azure-functions-durable>=1.2` — present. Provides orchestrator + activity primitives.
- **DEP-004**: `cryptography` — present. Used by AGT identity store for Ed25519.
- **DEP-005**: `agent-framework` + `agent-framework-github-copilot` + `agent-framework-azurefunctions` — present. Stay installed for the legacy per-phase graph path during rollout. No new MAF code in this plan.
- **DEP-006**: `gh` CLI (system binary) — already required by `_wrapper.py:_gh_token`. Unchanged.

## 5. Files

### New

- **FILE-001**: `api/functions/graphs/executors/agents/_permission.py` — `AGTPermissionHandler` for the SDK's `on_permission_request` hook.
- **FILE-002**: `api/functions/graphs/executors/agents/runtime.py` — `LLMRuntime` Protocol + `LLMRuntimeResult` Pydantic model + `_get_runtime()` factory.
- **FILE-003**: `api/functions/graphs/executors/agents/runtime_ghcp.py` — `GHCPRuntime` implementation.
- **FILE-004**: `api/functions/segments/__init__.py`
- **FILE-005**: `api/functions/segments/hiring_b.py` — `SegmentBOutput`, `_build_segment_b_prompt`, `run_segment_b`.
- **FILE-006**: `api/functions/segments/hiring_d.py` — Segment D equivalents.
- **FILE-007**: `api/functions/segments/hiring_e.py` — Segment E equivalents.
- **FILE-008**: `api/functions/segments/hiring_f.py` — Segment F equivalents.
- **FILE-009**: `scripts/replay_hiring_compare.py` — A/B harness.
- **FILE-010**: `tests/api/server/services/governance/test_permission_handler.py`
- **FILE-011**: `tests/api/functions/agents/test_runtime_protocol.py`
- **FILE-012**: `tests/api/unit/test_hiring_segment_b.py` (and `_d.py`, `_e.py`, `_f.py` mirrors)
- **FILE-013**: `tmp/segment-b-baseline.txt`, `tmp/segment-all-baseline.txt`, `tmp/article-audit.md` — reference artifacts, not CI-load-bearing.

### Modified

- **FILE-020**: `api/functions/graphs/executors/agents/_wrapper.py` — delegate to `LLMRuntime`, install `AGTPermissionHandler` when `AGT_ENFORCE=1`.
- **FILE-021**: `api/server/services/governance/kernel.py` — ensure `check_capability` is exposed (composing existing checks; do not add a new policy layer).
- **FILE-022**: `function_app.py` — register four new activity triggers per segment + their four validator triggers (8 new triggers total for Hiring).
- **FILE-023**: `api/functions/workflows/hiring.py` — branch on `HIRING_SEGMENT_MODE`, swap in segment activities and validators per enabled segment.
- **FILE-024**: `pyproject.toml` — comment-only change noting MAF deps are runtime-optional once `LLM_RUNTIME != ghcp`; no version changes.
- **FILE-025**: `docs/superpowers/skills/compose-domain/SKILL.md` — segment-default scaffold, optional `kind: graph` path documented.
- **FILE-026**: `docs/superpowers/skills/compose-domain/templates/*` — any per-phase MAF graph template rewritten as a segment activity template.
- **FILE-027**: `web/blueprint/src/sections/Argument.tsx` — captions 1 and 4 rewritten.
- **FILE-028**: `web/blueprint/src/sections/Composition.tsx` — new paragraph on segments and HITL boundaries.
- **FILE-029**: Other section files under `web/blueprint/src/sections/` — minor edits per Phase 7 audit.

### Modified in `zava-design-skills` (cross-repo)

- **FILE-030**: `~/dev/github-repos/zava-design-skills/skills/compose-org/README.md` — append the segment-default pointer paragraph (TASK-030).
- **FILE-031**: Any further `zava-design-skills` file that hard-codes the MAF-graph shape, if Phase 6 grep finds one.

## 6. Testing

- **TEST-001**: AGT pre-tool denial round-trip. Configure a skill whose `allowed_tools` does not include `policy_search`. Run a fake-runtime segment that "decides" to call `policy_search`. Assert the call is denied, an audit entry is written, and the model is handed the denial reason in the next turn (verified via the fake runtime's recorded prompts).
- **TEST-002**: `LLMRuntime` protocol substitution. `FakeRuntime` (no subprocess) drops into `_wrapper.py` when `LLM_RUNTIME=fake`. End-to-end segment activity returns a valid `SegmentBOutput` with no GHCP subprocess involvement. Asserts no `CopilotClient` is constructed.
- **TEST-003**: Per-skill agent_id stamp. Span emitted by `_wrapper.py` for a segment session has `gen_ai.agent.name == <skill_label>` for each skill invocation, not `"finance-agent"`. Regression test on the fix landed in `725ad18a`.
- **TEST-004**: Segment B output schema. Pydantic `SegmentBOutput.model_validate` accepts a hand-crafted valid example; rejects each of: missing `verdict`, invalid `verdict` literal, empty `candidates`, missing `jd_draft_id`.
- **TEST-005**: Orchestrator branching. With `HIRING_SEGMENT_MODE=off`, `hiring_orchestration` calls `hiring_job_design_activity_trigger`, `hiring_sourcing_activity_trigger`, `hiring_triage_activity_trigger`, `hiring_screening_activity_trigger` in order and never calls `hiring_segment_b_activity_trigger`. With `HIRING_SEGMENT_MODE=b`, the reverse.
- **TEST-006**: Segment retry on validation failure. Inject a `FakeRuntime` that returns malformed output once then valid output. Assert orchestrator calls the segment activity twice and proceeds.
- **TEST-007**: Segment retry exhaustion. `FakeRuntime` always returns malformed output. After `SEGMENT_MAX_RETRIES + 1` calls, orchestrator writes a `checkpoint_activity_trigger` of kind `"segment.failed"` and raises.
- **TEST-008**: Replay parity. `scripts/replay_hiring_compare.py` runs 5 fixed input records under both modes, asserts shared output fields are Pydantic-equal. Captured baselines in `tmp/segment-*-baseline.txt`.
- **TEST-009**: Article audit grep. `grep -E -i 'entra|agent 365|managed identity|per-skill principal|thousands of agents|torn down after' web/blueprint/src/sections/` returns zero matches after Phase 7.
- **TEST-010**: `compose-domain` skill round-trip. Given a minimal domain brief, running the skill produces the new segment scaffold under `api/functions/segments/<wt_snake>_b.py` rather than `api/functions/graphs/<wt_snake>_*.py`. Verified by executing the skill against a throwaway brief in `tmp/test-compose-domain/`.

## 7. Risks & Assumptions

- **RISK-001**: GHCP SDK's `on_permission_request` may not surface the denial reason back to the model in a way the model can act on. Mitigation: Phase 1 day-1 spike on `AGTPermissionHandler` with a test segment to verify the denial round-trip works. If it doesn't, fall back to deny-by-wrapping-the-MCP (the MCP itself raises a structured error). No third hook framework either way.
- **RISK-002**: Loading 4 skill directories in one session may produce skill bleed — model uses sourcing-orchestrator's voice to answer a screening question. Mitigation: tighten SKILL.md `description` fields for the four Segment B skills before TASK-018; A/B comparison in `replay_hiring_compare.py` flags any qualitative regression on output rationale.
- **RISK-003**: Bigger blast radius on segment retry — a crash mid-Segment-B re-runs all 4 skills' MCP calls. Mitigation: every MCP used by Segment B must be idempotent or have dedup on a deterministic key. The MCPs in scope (`policy_search`, `ocr_extract`) are already read-only.
- **RISK-004**: Compose-domain skill change breaks any in-flight composed-but-not-yet-merged domain branches in other clones of this repo (e.g. wpp-control-plane-poc3-ai-agency, colt-clone). Mitigation: TASK-031 grep is run across `~/dev/github-repos/` to flag any active forks; communicate the change in repo CHANGELOG and in plan README.
- **RISK-005**: Article rewrite must wait for code. Shipping the rewrite before Phase 3 lands would make the published page claim things that aren't true. Phase 7 explicitly comes after Phase 4 in execution order despite appearing here as a top-level phase. Hard ordering rule: Phase 7 PR cannot be merged until Phase 3 + 4 PRs are merged.
- **RISK-006**: `agent-framework-github-copilot` is on a beta channel (`>=1.0.0b260409`). A breaking beta update during the rollout could surface in `GHCPRuntime`. Mitigation: pin the beta version in `pyproject.toml` if necessary; monitor on the first failed CI run.
- **ASSUMPTION-001**: AGT's `check_capability` composes cleanly from the existing policy_compiler / kill_switch / allowed_tools lookup. Verified by reading `api/server/services/governance/kernel.py` during TASK-003; if it doesn't, the thin wrapper is added in the same task without expanding scope.
- **ASSUMPTION-002**: The four Segment B skills (jd-drafter, sourcing-orchestrator, cv-crystalliser, auto-shortlister) each have SKILL.md files that are self-describing enough that the model can pick the right one without procedural instruction in the prompt. This is the agentic-loop premise; if it fails on the A/B comparison the article narrative breaks and we revisit.
- **ASSUMPTION-003**: The `agent-framework` packages can stay installed without affecting runtime behaviour when no per-phase graph is built. Verified by reading the package's import-time side effects during TASK-010.
- **ASSUMPTION-004**: There is no production user of the substrate today; the rollout is from one set of local + GitHub-Pages-hosted demos to another. If a real customer environment appears mid-rollout, this plan needs a deployment section.

## 8. Related Specifications / Further Reading

- [api/server/services/governance/kernel.py](../api/server/services/governance/kernel.py) — AGT sign / verify / capability check entrypoints.
- [api/server/services/governance/identity.py](../api/server/services/governance/identity.py) — per-skill Ed25519 keystore.
- [api/shared/agents.py](../api/shared/agents.py) — per-skill agent registry (`AGENTS` dict).
- [api/functions/graphs/executors/agents/_wrapper.py](../api/functions/graphs/executors/agents/_wrapper.py) — current GHCP session wrapper; the integration point for `LLMRuntime` and `AGTPermissionHandler`.
- [api/functions/workflows/hiring.py](../api/functions/workflows/hiring.py) — current per-phase orchestrator; the file edited in Phase 3 + 4.
- [docs/superpowers/skills/compose-domain/SKILL.md](../docs/superpowers/skills/compose-domain/SKILL.md) — the design-time skill rewritten in Phase 5.
- `~/dev/github-repos/zava-design-skills/skills/compose-org/README.md` — cross-repo file edited in Phase 6.
- Commit `725ad18a` — the per-skill `agent_id` fix this plan builds on.
- Article peer-review discussion in conversation `01c6b5dc-7dd7-4a4d-8946-8fc793dfb92f` — the rationale tree behind the segment + AGT + LLMRuntime decisions.
