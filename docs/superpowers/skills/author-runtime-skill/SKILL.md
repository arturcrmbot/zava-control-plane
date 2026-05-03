---
name: author-runtime-skill
description: |
  Sub-skill of `compose-domain` (v3). Writes ONE phase-agent SKILL.md to
  a sandbox path, shape-isomorphic to existing skills under
  `api/server/skills/`. Persona authoring moved to `author-persona` in v3.
  Never writes to `api/server/skills/` directly.
audience: design-time-only
forbidden-runtime: true
---

# author-runtime-skill (v3, phase_agent only)

You write **one phase-agent SKILL.md** per invocation. You do not
orchestrate anything. The caller (`compose-domain`) decides what to
invoke and where. Your job is the file.

> **v3 change:** persona authoring is now `author-persona`. This skill
> only writes phase-agent skills.

## Inputs you require from the caller

The caller passes you, in their prompt, the structured arguments
documented in `compose-domain/SKILL.md` step 4. Specifically:

1. **`output_path`** — the absolute path inside the sandbox to write to.
   Looks like
   `tools/scratch/compose-domain/<run-id>/api/server/skills/<domain>-<agent_skill_name>/SKILL.md`.
2. **`brief`** — the relevant phase entry from brief.phases[].
3. **`canonical_example_path`** — `api/server/skills/receipt-validator/SKILL.md`.
4. **`available_mcp_tools`** — list of `{name, description}` for every MCP
   tool that the agent may legitimately reference in `allowed-tools`. The
   caller assembles this from the phase's `external_systems[]` plus any
   explicit `phase.allowed_tools[]` override. You may NOT invent a tool
   name not on this list.

If any input is missing, **stop and ask**.

## Procedure

### Step 1 — Read the canonical example

Read `canonical_example_path` end-to-end. Note the YAML frontmatter
shape, section structure, tone, output JSON schema convention, worked-
examples convention. Mirror it.

### Step 2 — Fill the frontmatter

```yaml
---
name: <domain>-<agent_skill_name>
description: <one sentence describing what the agent does in this phase>
allowed-tools: <comma-separated subset of available_mcp_tools[].name>
---
```

Rules:
- `name` is exactly the leaf folder name. No spaces, no underscores.
- `description` is one sentence; no marketing register; no "AI-powered".
- `allowed-tools` is a comma-separated list. Single-line CSV — do not
  use YAML list form.

### Step 3 — Resolve `allowed-tools`

- Take `phase.allowed_tools[]` from the brief if present; otherwise the
  union of all `<mcp_tool>_<operation>` entries derived from
  `phase.external_systems[]`.
- Verify each appears in `available_mcp_tools`. If one doesn't, **stop**
  and tell the caller. Do not invent a tool name.

### Step 4 — Write the body

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
- <Schema invariants the validator will enforce. At least one.>
- Never propose actions outside this phase's intent.
```

### Step 5 — Write the file

Write the assembled markdown to `output_path`. Create parent directories
if needed.

### Step 6 — Self-check

Before returning, verify the file you just wrote satisfies:

- Frontmatter parses as YAML (no tabs, no unmatched quotes).
- `allowed-tools` is comma-separated, every entry in `available_mcp_tools`.
- The body has `## Inputs`, `## Procedure`, and `## Output` sections.
- The Output JSON schema names a `verdict` (or domain-appropriate
  equivalent) field — what the matching validator will gate on.
- No `TODO` placeholder remains.
- No marketing register ("AI-powered", "leverage", "synergy").

If any check fails, **fix the file in place**. If you cannot fix it
without inventing fields, stop and tell the caller.

## Anti-patterns

- Inventing tool names. The `allowed-tools` list is the authoritative
  capability surface; if the brief implies a tool the caller did not
  put in `available_mcp_tools`, that is the caller's bug, not yours.
  Stop.
- Writing the body before reading the canonical example.
- Writing a persona — that's `author-persona`'s job in v3.
- Leaving the JSON schema vague ("an object containing the verdict" —
  no, show the schema).
- Adding a "Notes" / "References" / "Future work" section. Existing
  skills don't have them.
