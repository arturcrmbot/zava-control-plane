---
name: author-runtime-skill
description: |
  Sub-skill of `compose-domain`. Writes ONE runtime SKILL.md to a sandbox
  path, shape-isomorphic to existing skills under `api/server/skills/`.
  Covers both phase-agent skills and persona skills (same SKILL.md shape,
  different rhetorical role). Never writes to `api/server/skills/` directly.
audience: design-time-only
forbidden-runtime: true
---

# author-runtime-skill

You write **one** runtime SKILL.md per invocation. You do not orchestrate
anything. The caller (`compose-domain`) decides what to invoke and where.
Your job is the file.

## Inputs you require from the caller

The caller passes you, in their prompt, the structured arguments
documented in `compose-domain/SKILL.md` step 4. Specifically:

1. **`mode`** — `"phase_agent"` or `"persona"`.
2. **`output_path`** — the absolute path inside the sandbox to write to.
   For phase agents this looks like
   `tools/scratch/compose-domain/<run-id>/api/server/skills/<domain>-<agent_skill_name>/SKILL.md`.
   For personae it looks like
   `tools/scratch/compose-domain/<run-id>/api/server/personae/<role>/SKILL.md`.
3. **`brief`** — the relevant fragment of the YAML brief (the phase entry
   for `phase_agent`, the persona entry for `persona`).
4. **`canonical_example_path`** — one absolute path to a real existing
   SKILL.md you should mirror in shape. For `phase_agent`, the canonical
   is `api/server/skills/receipt-validator/SKILL.md`. For `persona`, the
   canonical is `api/server/personae/line_manager/SKILL.md` (the
   one shipped with the v1 graduated `fleet-travel-preapproval` domain).
5. **`available_mcp_tools`** — a list of `{name, description}` for every MCP
   tool that the agent may legitimately reference in `allowed-tools`. The
   caller assembles this from the brief's `external_systems[]` and from
   `api/server/mcp_tools/`. You may NOT invent a tool name not on this list.
6. **`external_event_name`** (persona mode only) — the exact string the
   orchestrator's `wait_for_external_event(...)` will use. Convention is
   `<hitl_phase_name>_decision`. The caller passes this verbatim; you
   write it verbatim into the persona's `## Procedure` step 3 and Rules
   block. Do not invent.

If any of these are missing, **stop and ask**. Do not guess.

## Procedure

### Step 1 — Read the canonical example

Read `canonical_example_path` end-to-end. Note the YAML frontmatter shape,
the section structure, the tone, the output JSON schema convention, the
worked-examples convention. You will mirror it.

### Step 2 — Choose the SKILL.md skeleton

Use the template at `docs/superpowers/skills/compose-domain/templates/SKILL.md.tmpl`
for `mode == "phase_agent"`, or `persona_SKILL.md.tmpl` for
`mode == "persona"`.

### Step 3 — Fill the frontmatter

```yaml
---
name: <for phase_agent: <domain>-<agent_skill_name>; for persona: <role>>
description: <one sentence; for phase_agent describe what the agent does in
              this phase, for persona describe the decision the persona owns>
allowed-tools: <comma-separated subset of available_mcp_tools[].name —
                see step 4>
---
```

Rules:
- `name` is exactly the leaf folder name. No spaces, no underscores.
- `description` is one sentence; no marketing register; no "AI-powered".
- `allowed-tools` is a comma-separated list (matches the existing repo
  convention). Do not use YAML list form — single-line CSV.

### Step 4 — Resolve `allowed-tools`

For `phase_agent`:
- Take the phase's `external_systems[]` from the brief.
- For each, look up the matching `external_systems[].mcp_tool` from the
  brief's top-level list.
- Verify each appears in `available_mcp_tools`. If one doesn't, **stop**
  and tell the caller. Do not invent a tool name.

For `persona`:
- Personae generally have `allowed-tools: ` empty (they don't call MCP
  tools — they just decide and emit external events). If the brief's
  `decision_policy` paragraph names a system the persona must read from
  before deciding (e.g. "look at the Workday team calendar"), include
  the matching tool from `available_mcp_tools`.

### Step 5 — Write the body

Body sections in order. Mirror the canonical example's tone exactly.

For `phase_agent`:

```markdown
You are the <agent_skill_name> step in the <domain.display_name>
orchestrator (Phase <N>: <phase_name>).

## Inputs

A `<workflow_id>` and the orchestrator-enriched payload from prior phases.
Specifically: <list the keys this phase reads, derived from the brief>.

## Procedure

1. <Call <tool_a>(<args>) to <intent>.>
2. <Reason over the result per the phase intent.>
3. <Decide / compose / classify per the phase intent.>

## Output

Return exactly one JSON object, no prose:

\```json
{
  "verdict": "<one of the values your downstream validator expects>",
  "reasoning": "<1-2 sentences>",
  "confidence": 0.0
}
\```

Rules:
- <Schema invariants the validator will enforce. Always include at least one.>
- <Never propose actions outside this phase's intent.>
```

For `persona`:

```markdown
You are <persona.role> for the <domain.display_name> workflow.

## Decision policy

<Verbatim from brief.persona.decision_policy.>

## Procedure

1. Read the parked workflow payload (the orchestrator gives you everything
   prior phases produced).
2. Apply your decision policy.
3. Return exactly one JSON object — the resolving external event payload:

\```json
{
  "decision": "approve" | "reject",
  "reason": "<one sentence>"
}
\```

Rules:
- The orchestrator is waiting on the `<external_event_name>` event with this
  payload. Do not return anything else.
- If you cannot decide because a required field is missing from the payload,
  return `{"decision": "reject", "reason": "missing <field>"}`. Do not stall.
```

The `<external_event_name>` placeholder in the body MUST be replaced with
the exact `external_event_name` argument the caller passed. By
convention this is `<hitl_phase_name>_decision` (e.g.
`manager_approval_decision`). The same string appears in the
orchestrator's `wait_for_external_event(...)` call — they MUST match
byte-for-byte.

### Step 6 — Write the file

Write the assembled markdown to `output_path`. Create parent directories
if needed.

### Step 7 — Self-check

Before returning, verify the file you just wrote satisfies:

- Frontmatter parses as YAML (no tabs, no unmatched quotes).
- `allowed-tools` is comma-separated, every entry in `available_mcp_tools`.
- For `phase_agent`: the body has an `## Inputs`, `## Procedure`, and
  `## Output` section; the JSON schema names a `verdict` (or domain-
  appropriate equivalent) field.
- For `persona`: the body has `## Decision policy` and `## Procedure`; the
  output JSON has `decision` and `reason`.
- No `TODO` placeholder remains.
- No mention of the words "AI-powered", "leverage", "synergy", or any
  similar marketing register.

If any check fails, **fix the file in place** before returning. If you
cannot fix it without inventing fields, stop and tell the caller.

## Anti-patterns

- Inventing tool names. The `allowed-tools` list is the authoritative
  capability surface; if the brief implies a tool the caller did not put
  in `available_mcp_tools`, that is the caller's bug, not yours. Stop.
- Writing the body before reading the canonical example.
- Mixing `phase_agent` and `persona` rhetorical voices in one file.
- Leaving the JSON schema vague ("an object containing the verdict" — no,
  show the schema).
- Adding a "Notes" / "References" / "Future work" section. Existing skills
  don't have them.
