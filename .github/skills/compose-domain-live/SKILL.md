---
name: compose-domain-live
description: Compose a new Zava domain from a process document while streaming progress + HITL to the Visual Domain Composer UI via the compose-bridge MCP tools. Wraps add-domain. Invoked only by the ComposeBridge (localhost-only).
---

# compose-domain-live

You are composing a new Zava domain from a process document, driven by the
Visual Domain Composer UI. You MUST route every interaction through the
**compose-bridge** MCP tools so the operator sees your progress and can answer
you. Otherwise, follow the real [`add-domain`](../add-domain/SKILL.md) recipe
exactly — this skill only governs *how you communicate*, not *what you build*.

## Contract

1. Call `report_stage("understanding", "Reading the document")` first.
2. Read the document. If — and only if — something material is genuinely
   ambiguous (an approver role, a threshold, whether a phase is agent vs hitl),
   call `ask_operator(question, options)` and use the returned answer. Phrase
   questions in **plain business language** for a non-technical operator — ask
   about the process, not the schema (e.g. "Who signs off above £50,000?" with
   options like "Finance Director", "CFO" — never "hitl persona?" or YAML). Do
   NOT ask about things the document already answers. Do NOT ask more than a
   couple of questions.
3. `report_stage("brief", "Drafting the brief")`, author the v4 brief per
   add-domain Phase 2, then **always** call `present_brief(yaml)`. Honour the
   returned `{approved, yaml}` — if the operator edited the YAML, use their
   version; if `approved` is false, revise and present again.
4. `report_stage("composing", ...)` then run compose-domain (add-domain Phase 3)
   into the sandbox.
5. `report_stage("graduating", ...)` then run graduate.sh + the Phase-4b/4c
   hand-stitches (domains.py, entity_projections/__init__.py, AGT matrix, etc.).
6. `report_stage("verifying", ...)` then run add-domain Phase 4d verification.
   Include compose-domain CHECKLIST §12: live authority closure, persisted
   HITL recovery context, persona/Durable resume timing, and browser event
   recovery across a lower `latest_seq`. If a check fails, fix it and
   re-verify — narrate what you're doing.
7. On success call
   `composition_complete(workflow_type, display_name)`. Do not restart the
   server yourself — the UI's Ignite control handles the restart.

Narrate briefly as you go (your normal assistant messages appear in the UI as
the agent's "voice"). Think out loud — your reasoning is shown as the thought
stream.
