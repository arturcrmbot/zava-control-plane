---
name: compose-domain-live
description: Compose a new Zava domain from a process document while streaming progress + HITL to the Visual Domain Composer UI via the compose-bridge MCP tools. Wraps add-domain. Invoked only by the ComposeBridge (localhost-only).
---

# compose-domain-live

You are composing a new Zava domain from a process document through the Visual
Domain Composer UI. Route operator interaction through the **compose-bridge**
MCP tools. Follow the real [`add-domain`](../add-domain/SKILL.md) procedure,
the [Vertical Build Contract](../../../docs/superpowers/contracts/VERTICAL-BUILD-CONTRACT.md),
and [`docs/VERTICAL-PROOF.md`](../../../docs/VERTICAL-PROOF.md).

This skill governs communication and visible stage state. It does not define a
different build procedure.

## Contract

1. Call `report_stage("understanding", "Reading the document")` first.
2. Read the document. If and only if something material is genuinely
   ambiguous (an approver role, a threshold, whether a phase is agent vs hitl),
   call `ask_operator(question, options)` and use the returned answer. Phrase
   questions in **plain business language** for a non-technical operator — ask
   about the process, not the schema (e.g. "Who signs off above £50,000?" with
   options like "Finance Director", "CFO" — never "hitl persona?" or YAML). Do
   NOT ask about things the document already answers. Do NOT ask more than a
   couple of questions.
3. `report_stage("brief", "Drafting the brief")`, author the current brief, then
   **always** call `present_brief(yaml)`. Honour the
   returned `{approved, yaml}` — if the operator edited the YAML, use their
   version; if `approved` is false, revise and present again.
4. `report_stage("composing", ...)` then run compose-domain into the sandbox.
   Run compose-domain **inline in this session**. Do not
   dispatch this critical path to a nested subagent: if nested dispatch fails,
   no sandbox exists and there is nothing to graduate.
5. `report_stage("graduating", ...)` then run the generated graduate.sh.
   Graduation must be complete and pack-scoped; do not apply an undocumented
   manual patch list.
6. `report_stage("verifying", ...)` then run the active-pack, runtime, and
   execution-visibility gates referenced by add-domain.
   Include compose-domain CHECKLIST §12: live authority closure, persisted
   HITL recovery context, persona/Durable resume timing, and browser event
   recovery across a lower `latest_seq`. If a check fails, fix it and
   re-verify — narrate what you're doing.
   Also enforce the **blocking execution-visibility gate**: actual execution
   evidence must be visible and self-consistent for every active non-stub
   workflow type. Validate observed evidence rather than predicting conditional
   branches. Generated agents use `run_agent_session`; run the live/replay
   `tools/workflow_visibility_proof.py` commands from compose-domain CHECKLIST
   §13.
7. If a gate fails, report the exact failing gate and evidence. Fix the owning
   generator or implementation, rerun the required stage, and do not emit a
   readiness-shaped result.
8. Only call `composition_complete(workflow_type, display_name)` after the
   sandbox exists, graduation completed, the active pack contains the new
   `workflow_type`, and every verification gate above passed. A missing sandbox
   or failed verification is a failure: report the exact error and stop. Never
   report the domain as ready when it was not built. Do not restart the server
   yourself — the UI's Ignite control handles the restart.

Normal assistant messages may briefly explain current stage and evidence. Do
not expose hidden chain-of-thought or replace artifact state with optimistic
narration. The UI's Ignite control owns server restart.
