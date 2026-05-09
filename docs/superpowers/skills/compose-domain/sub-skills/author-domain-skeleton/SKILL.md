---
name: author-domain-skeleton
description: |
  v4 sub-skill #1. Owns the `domain` and `phases` sections of the
  brief. Takes a free-text idea or an existing skeleton and emits
  the v0 brief — domain.workflow_type / prefix / display_name plus
  the phase list (with kind ∈ {deterministic, agent, hitl}).
audience: design-time-only
forbidden-runtime: true
inputs:
  - one of: free-text idea OR partial skeleton brief
outputs:
  - brief.domain (workflow_type, prefix, display_name, description?)
  - brief.phases (ordered list; ≥ 1 deterministic intake; ≥ 1 hitl gate)
hands_off_to: author-entity-projection
---

# author-domain-skeleton

You are the first pass of compose-domain v4's sequential pipeline.
Your job is the *workflow shape*: name, file-prefix, ordered phases.
Nothing else. The four enrichment passes that follow each layer one
new top-level brief section.

## Procedure

1. **Source the idea.** If invoked with a free-text idea, hand off to
   `superpowers:brainstorming` for one-question-at-a-time elicitation
   of: domain workflow_type (kebab-case, no `fleet-` prefix today),
   display_name, prefix (`fleet` for synthetic-journey domains;
   `creative` for `creative-campaign`), and the ordered phase list.
   If invoked with an existing skeleton brief path, load it and skip
   the brainstorm.

2. **Write the v0 brief** at
   `tools/scratch/compose-domain/<run-id>/brief/v0-skeleton.yaml` AND
   at `docs/superpowers/specs/<workflow_type>-brief.yaml` (the
   canonical home; subsequent passes overwrite the same file
   in-place, growing it).

3. **Validate.** Run `validator.py:validate(brief_dict)`. On
   `SchemaError`, print the structured failure (path + reason) and
   STOP. Do not attempt to recover.

4. **Hand off** to `author-entity-projection` with the validated
   brief.

## v0 brief shape (this sub-skill's slice)

```yaml
domain:
  workflow_type: <kebab-case>          # e.g. "vendor-kyc", "purchase-card"
  prefix:        <snake_case>          # e.g. "fleet", "creative"
  display_name:  <human label>
  description:   |                     # optional, recommended
    One paragraph of context.

phases:
  - name: <snake_case>                 # e.g. "vendor_intake"
    kind: deterministic | agent | hitl
    intent: <one sentence>             # optional but recommended
    # only when kind == agent:
    agent_skill_name: <kebab-case>
    # only when kind == hitl:
    persona: <snake_case role>
    external_event: <snake_case>       # default: <phase>_decision
```

## Constraints

- ≥ 1 phase with `kind: deterministic` (the intake).
- ≥ 1 phase with `kind: hitl` (the operator gate).
- Every HITL phase MUST declare `persona` and SHOULD declare
  `external_event` (validator defaults the latter to
  `<phase>_decision` if absent).

## Failure handling

Any validator miss aborts the pipeline. Fix the brief, re-run.
Do NOT silently patch in the sandbox.
