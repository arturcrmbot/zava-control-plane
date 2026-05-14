---
name: compose-persona
description: |
  Design-time meta-skill (v1). Given a persona brief (YAML) or a free-text
  idea, produce a complete Persona artefact set: a SKILL.md
  (frontmatter + executable decision_policy + prose body), a
  Python registry entry pasteable into `api/shared/personas.py`, and a
  graduate.sh script that mechanically wires the persona into the live
  trees.

  Sandbox-only; never touches real trees directly. Calls `author-persona`
  as its sole sub-skill.

  Sister to `compose-domain`. Where `compose-domain` graduates a whole
  Durable workflow + skills + personae for one new business process,
  `compose-persona` graduates ONE persona — useful when an existing
  domain needs an additional approver / reviewer, or when a new
  function (finance, legal, IT) needs its cast filling out before its
  domain lands.
audience: design-time-only
forbidden-runtime: true
---

# compose-persona (v1)

You are the orchestrator for a five-step procedure that turns a persona
brief into a complete sandboxed persona artefact set. You do not
improvise. You follow this skill literally. When you are uncertain,
you stop and ask the operator — you do not invent.

> **Forbidden.** This skill, and any sub-skill it invokes, **MUST NOT**
> write to any path outside `tools/scratch/compose-persona/<run-id>/`
> and `docs/superpowers/specs/`. In particular: never edit
> `api/server/personae/`, `api/shared/personas.py`,
> `api/server/services/persona_responder.py`, or any other live tree.
> Graduation is a separate, manual step (the operator runs the
> generated `graduate.sh`).

## Inputs

You are invoked one of two ways:

1. **With a brief path.** "Run compose-persona against
   `docs/superpowers/specs/<role>-persona-brief.yaml`." Skip step 1.
2. **With a free-text idea.** "Compose a new persona for X." Run step 1
   to produce the brief, then continue.

## The five steps

### Step 1 — Brief intake (only if no YAML brief was supplied)

Hand off to the existing `brainstorming` skill. It will elicit the
brief through one-question-at-a-time dialogue with the operator.
Capture the operator's answers into the YAML schema below and write
to `docs/superpowers/specs/<role>-persona-brief.yaml`. Read it back
to the operator. Wait for explicit approval. Then continue to step 2.

If the operator gives you a YAML brief path on entry, skip this step.

#### Brief schema (authoritative, v1)

```yaml
persona:
  role: <snake_case role name, used as folder/file prefix>
  archetype: approver | subject | reviewer | delegate | notifier
  scope_function: finance | hr | it | procurement | legal | legal_privacy | commercial | candidate
  scope_business_unit: <string or "*">    # OPTIONAL; default "*"
  scope_geography: <string or "*">        # OPTIONAL; default "*"
  workflow_label: <human label of the domain this persona belongs to>
  external_event: <snake_case>            # OPTIONAL; default <role>_decision
  default_authority_band: <free-text>     # OPTIONAL; documentation only
  uses_authority_mcp: true | false        # OPTIONAL; default false
  description: <one sentence>
  decision_policy_paragraph: |
    One paragraph stating the rule the persona uses to decide.
  decision_inputs:                        # OPTIONAL; documentation
    - <context_key_the_policy_reads>
    - ...
  decision_authority_action: <action>     # REQUIRED iff uses_authority_mcp=true.
                                          # Must match an `action` in
                                          # data/synthetic/authority/matrix.json.
  decision_code: |
    # Python source the persona_responder compiles. Reads `context`,
    # assigns `decision` ("approve" | "reject" | "escalate") and
    # `reason` (str). Mirror the decision_policy_paragraph above.
    # The responder runs this in a sandboxed namespace with a small
    # whitelist of safe builtins (see api/server/services/persona_responder.py
    # _DECISION_BUILTINS — currently includes `authority_check` for
    # personae that consult the delegated-authority MCP).
    pass
```

Validate the brief before continuing:

- `role` matches `^[a-z][a-z0-9_]*$`.
- `archetype` is one of the five allowed strings.
- `scope_function` is one of the eight allowed strings.
- `external_event` is `^[a-z][a-z0-9_]*$` if provided.
- If `uses_authority_mcp: true`, `decision_authority_action` is set
  AND the decision_code contains `authority_check(...)`.
- The decision_code uses only the safe builtins from
  `api/server/services/persona_responder.py` `_DECISION_BUILTINS`
  (no `import`, no `open`, no `os`, no `subprocess`, no `eval`).
- The decision_code assigns both `decision` and `reason`.

If validation fails, stop and tell the operator what's wrong. Do not
proceed to step 2.

### Step 2 — Plan

From the brief, produce the artefact list. **Print this list back to
the operator before you write a single file.** Wait for "go".

Always:

- 1 persona SKILL.md at
  `<RUN_ROOT>/api/server/personae/<role>/SKILL.md`.
- 1 `REGISTRY-ENTRY.py` at the run root containing the Python snippet
  to splice into `api/shared/personas.py` `PERSONAS` dict.
- 1 `GRADUATION.md` describing what `graduate.sh` will do.
- 1 executable `graduate.sh` that mechanically performs the live-tree
  edits.

### Step 3 — Inventory and isomorphism

Before invoking `author-persona`, read **exactly these 3 files**
end-to-end. They are the canonical examples this skill mirrors.

| # | Canonical file                                              | Why                                                  |
|---|-------------------------------------------------------------|------------------------------------------------------|
| 1 | `api/server/personae/finance_bp/SKILL.md`                   | Authority-MCP-using persona (template for `uses_authority_mcp: true`) |
| 2 | `api/server/personae/line_manager/SKILL.md`                 | Inline-logic persona (template for `uses_authority_mcp: false`)        |
| 3 | `api/server/services/persona_responder.py` (`_DECISION_BUILTINS`) | Sandbox surface — whitelist of callables the decision_code may use |

Drift in any of these means downstream output will be stale-shaped —
stop and update this SKILL before continuing.

### Step 4 — Generate into sandbox

Compute `RUN_ID = <YYYYMMDD-HHMMSS>-<role>` from current UTC
(`date -u +"%Y%m%d-%H%M%S"`). Create
`tools/scratch/compose-persona/<RUN_ID>/`.

#### 4.1 — Invoke `author-persona`

```
output_path: <RUN_ROOT>/api/server/personae/<role>/SKILL.md
brief: <persona block from the YAML brief>
domain_display_name: <persona.workflow_label>
default_external_event: <persona.external_event or persona.role + "_decision">
canonical_example_path:
  - api/server/personae/finance_bp/SKILL.md   (when uses_authority_mcp: true)
  - api/server/personae/line_manager/SKILL.md (when uses_authority_mcp: false)
responder_path: api/server/services/persona_responder.py
```

`author-persona` writes the SKILL.md to the sandbox path.

#### 4.2 — Write `<RUN_ROOT>/REGISTRY-ENTRY.py`

```python
# Splice into api/shared/personas.py inside the PERSONAS dict.
# Place under the matching domain section comment block.
"<role>": Persona(
    role="<role>",
    archetype="<archetype>",
    scope_function="<scope_function>",
    workflow_label="<workflow_label>",
    external_event_default="<external_event>",
    scope_business_unit="<scope_business_unit>",   # default "*"
    scope_geography="<scope_geography>",           # default "*"
    default_authority_band=<None or "<text>">,
    uses_authority_mcp=<True | False>,
    description="<description>",
),
```

#### 4.3 — Write `<RUN_ROOT>/GRADUATION.md`

Human-readable explanation of what `graduate.sh` does:

1. Copy `<RUN_ROOT>/api/server/personae/<role>/SKILL.md` →
   `api/server/personae/<role>/SKILL.md`.
2. Splice `<RUN_ROOT>/REGISTRY-ENTRY.py` content into
   `api/shared/personas.py` `PERSONAS` dict (between the appropriate
   per-domain comment markers — operator's manual call where exactly).
3. Add `<role>` to `PERSONA_AUTO_CLOSE` env var ONLY if the demo
   profile expects this persona to auto-close gates. Default: do not
   add (production-honest default).
4. Run `pytest tests/api/shared/test_personas_registry.py` to confirm
   the registry validates with the new entry.

#### 4.4 — Write `<RUN_ROOT>/graduate.sh`

Executable script:

```bash
#!/usr/bin/env bash
# graduate.sh — mechanically promote the persona generated at this run root
# into the live trees. Re-runnable; idempotent on the SKILL.md copy.
# The registry-entry splice is intentionally manual — printed to stdout for
# the operator to paste into the right per-domain section of personas.py.
set -euo pipefail

RUN_ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$RUN_ROOT/../../.." && pwd)"
ROLE="<role>"

SKILL_SRC="$RUN_ROOT/api/server/personae/$ROLE/SKILL.md"
SKILL_DST="$REPO_ROOT/api/server/personae/$ROLE/SKILL.md"

if [ ! -f "$SKILL_SRC" ]; then
    echo "ERROR: missing SKILL.md at $SKILL_SRC" >&2
    exit 1
fi

mkdir -p "$(dirname "$SKILL_DST")"
cp "$SKILL_SRC" "$SKILL_DST"
echo "wrote $SKILL_DST"

cat <<EOF

  Manual splice required:
  -----------------------
  Open $REPO_ROOT/api/shared/personas.py and paste the entry below
  inside the PERSONAS dict, under the matching domain's comment block.

EOF

cat "$RUN_ROOT/REGISTRY-ENTRY.py"

echo
echo "  Then run: uv run pytest tests/api/shared/test_personas_registry.py"
```

`chmod +x` the file.

### Step 5 — Self-check + operator handoff

Before returning, verify:

- All four files exist at `<RUN_ROOT>/`.
- `SKILL.md` parses as YAML frontmatter + markdown body
  (`yaml.safe_load(frontmatter_block)` works; body has the three
  required `##` sections from `author-persona`).
- `SKILL.md` `decision_policy` block compiles (`compile(source,
  "<test>", "exec")` doesn't raise).
- `REGISTRY-ENTRY.py` is valid Python and uses one of the
  documented `archetype` values.
- `graduate.sh` is executable (`-x` bit set).

Return a one-paragraph summary to the operator naming the four
generated paths and the next-step command (the manual splice + the
pytest command).

## Anti-patterns

- Letting the prose paragraph and the executable block disagree. The
  prose tracks the code; if they diverge, the brief author needs to
  resolve it before this skill runs.
- Generating a persona that uses the authority MCP without setting
  `uses_authority_mcp: true` in the registry entry. The registry flag
  is the auditable signal that this persona doesn't inline thresholds.
- Modifying the live `api/shared/personas.py`. Always emit the
  `REGISTRY-ENTRY.py` snippet for the operator to splice manually.
  Mechanical splicing risks placing the entry under the wrong
  per-domain comment block.
- Adding the persona to `PERSONA_AUTO_CLOSE` automatically.
  Production-honest default: every gate stays open until explicitly
  opted in. Demo profiles set the allow-list explicitly.
