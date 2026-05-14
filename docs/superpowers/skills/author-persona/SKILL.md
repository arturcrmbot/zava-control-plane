---
name: author-persona
description: |
  Sub-skill of `compose-domain` (NEW v3). Writes ONE persona SKILL.md to
  a sandbox path, shape-isomorphic to the personae under
  `api/server/personae/`. Personae differ from phase-agent skills: their
  YAML frontmatter contains an executable `decision_policy` Python block
  the persona_responder compiles at load time.
audience: design-time-only
forbidden-runtime: true
---

# author-persona (v3)

You write **one persona SKILL.md** per invocation. You do not
orchestrate anything. The caller (`compose-domain`) decides what to
invoke and where.

A persona is loaded by `api/server/services/persona_responder.py` at
attach time. Its frontmatter is parsed as YAML; the `decision_policy`
block is compiled to a callable that runs in a sandboxed namespace
with only `context` in scope plus a small whitelist of safe builtins.

## Inputs you require from the caller

1. **`output_path`** — absolute path inside the sandbox, e.g.
   `tools/scratch/compose-domain/<run-id>/api/server/personae/<role>/SKILL.md`.
2. **`brief`** — the matching `personae[]` entry. MUST include both
   `decision_policy` (prose) and `decision_code` (Python source).
3. **`domain_display_name`** — used in the body's "You are X for Y" line.
4. **`default_external_event`** — the convention default
   (`<hitl_phase_name>_decision`). Used as the persona's
   `external_event` frontmatter field.
5. **`canonical_example_path`** — `api/server/personae/line_manager/SKILL.md`.
6. **`responder_path`** — `api/server/services/persona_responder.py`. Used
   only to verify the safe-builtins whitelist hasn't drifted; you don't
   write to it.

If any input is missing, **stop and ask**.

## Procedure

### Step 1 — Read the canonical example + responder

Read `canonical_example_path` end-to-end. Note frontmatter shape,
section structure, the way the prose body mirrors the executable
policy.

Read `responder_path` `_DECISION_BUILTINS` to confirm what the
`decision_code` is allowed to use. Currently:

```python
isinstance, len, str, int, float, bool, list, dict, set, tuple,
min, max, abs, round, any, all, sum, True, False, None
```

Anything outside this is unavailable in `decision_code`. If the brief's
`decision_code` uses something else (e.g. `re`, `datetime`, `import`),
**stop and tell the caller** — the policy can't run as-is.

### Step 2 — Fill the frontmatter

```yaml
---
name: <role>
description: <one sentence; what this persona decides>
allowed-tools:
workflow_label: <domain_display_name>
external_event: <default_external_event>
decision_policy: |
    <verbatim from brief.personae[].decision_code>
---
```

Rules:
- `name` is exactly the leaf folder name. No spaces.
- `description` is one sentence; no marketing register.
- `allowed-tools` is empty (personae do not call MCP tools — they
  decide and emit external events).
- `decision_policy` block is the Python source the responder will
  compile. Indent under `decision_policy: |` with 4 spaces. Use only
  the safe builtins from step 1.
- The block MUST assign `decision` (str: "approve" | "reject") and
  `reason` (str). Anything else is a bug — the responder rejects.

### Step 3 — Write the body

```markdown
# <role>

You are the **<role>** for the **<domain_display_name>** workflow.

## Decision policy

<verbatim from brief.personae[].decision_policy — the prose paragraph
that mirrors the decision_code in the frontmatter>

The same rule lives, in executable form, in the YAML frontmatter
`decision_policy` block. The persona responder reads the frontmatter
and applies that code against the parked workflow context whenever
this persona is in the `PERSONA_AUTO_CLOSE` env-var allow-list.

## When this fires

The orchestrator parks at the matching HITL gate and emits a
`workflow.hitl.requested` FleetEvent carrying:

- `persona: "<role>"`
- `external_event: "<default_external_event>"`
- `context.<keys>`: the prior-phase outputs the policy reads

## How a real human resolves the same gate

When `<role>` is NOT in `PERSONA_AUTO_CLOSE`, the gate stays open
indefinitely. The real <role> resolves it via whatever UI surface the
domain provides (or by directly POSTing to
`/internal/durable-event` with kind `<default_external_event>`).
```

### Step 4 — Write the file

Write the assembled markdown to `output_path`. Create parent
directories if needed.

### Step 5 — Self-check

Before returning, verify:

- Frontmatter parses as YAML.
- `decision_policy` block is non-empty, indented under `: |`, assigns
  both `decision` and `reason`.
- `decision_policy` source uses only the safe builtins listed in
  step 1 (no `import`, no `open`, no `os`, no `subprocess`, no `eval`,
  no `__import__`).
- Body has `## Decision policy`, `## When this fires`, `## How a real
  human resolves the same gate`.
- The `external_event` in frontmatter is the same string as in the
  body's `external_event:` field.
- No `TODO` placeholder remains.
- No marketing register.

If any check fails, **fix in place**. If `decision_code` uses unsafe
operations, stop — the brief is wrong, not the output.

## Anti-patterns

- Letting the prose paragraph and the executable block disagree. The
  prose tracks the code; if they diverge, the brief author needs to
  resolve it before this skill runs.
- Mixing phase-agent and persona shape in one file. Personae have no
  Output JSON schema — they have a `decision_policy` block in the
  frontmatter.
- Inventing the external_event name. Convention is
  `<hitl_phase_name>_decision`; the caller passes it in
  `default_external_event` and you write it verbatim. The
  orchestrator's `wait_for_external_event(...)` and this persona's
  frontmatter MUST match byte-for-byte.
- Importing anything in `decision_code`. The responder's
  `__builtins__` whitelist is exhaustive; an `import` raises and the
  policy degrades to "reject" with the exception message as reason.
