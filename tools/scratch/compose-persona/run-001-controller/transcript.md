# compose-persona dry-run transcript — controller (run-001)

**Date:** 2026-05-05
**Brief:** [`docs/superpowers/specs/controller-persona-brief.yaml`](../../../docs/superpowers/specs/controller-persona-brief.yaml)
**Output root:** `tools/scratch/compose-persona/run-001-controller/`

## Steps executed

1. **Brief intake (skipped step 1).** A pre-authored YAML brief was supplied
   directly. Validated against the v1 schema:
   - `role` matches snake_case ✅
   - `archetype: approver` ✅
   - `scope_function: finance` ✅
   - `external_event: controller_signoff_decision` ✅
   - `uses_authority_mcp: true` AND `decision_authority_action: ap_invoice_approval` ✅
   - `decision_code` calls `authority_check(...)` ✅
   - `decision_code` uses only safe-builtins (no import/open/os) ✅
   - `decision_code` assigns `decision` and `reason` ✅

2. **Plan.** Artefact list confirmed: 1 SKILL.md, 1 REGISTRY-ENTRY.py, 1 GRADUATION.md, 1 graduate.sh.

3. **Inventory.** Read the three canonical files:
   - `api/server/personae/finance_bp/SKILL.md` (authority-MCP-using template)
   - `api/server/personae/line_manager/SKILL.md` (inline-logic template)
   - `api/server/services/persona_responder.py` `_DECISION_BUILTINS` (sandbox surface)

4. **Generate.**
   - 4.1 — Invoked `author-persona` against the brief; SKILL.md written to
     `<RUN_ROOT>/api/server/personae/controller/SKILL.md`.
   - 4.2 — Wrote `<RUN_ROOT>/REGISTRY-ENTRY.py` with the Persona() snippet
     for `api/shared/personas.py`.
   - 4.3 — Wrote `<RUN_ROOT>/GRADUATION.md` describing the manual splice.
   - 4.4 — Wrote `<RUN_ROOT>/graduate.sh`, marked executable.

5. **Self-check (all green).**
   - SKILL.md frontmatter parses as YAML ✅ (keys: `name`, `description`,
     `allowed-tools`, `workflow_label`, `external_event`, `decision_policy`)
   - `decision_policy` compiles via `compile(..., "<test>", "exec")` ✅
   - Body has the three required `##` sections ✅
   - `REGISTRY-ENTRY.py` is valid Python and uses `archetype="approver"` ✅
   - `graduate.sh` has the `-x` bit set ✅

## What this proved

The compose-persona meta-skill produces deterministic, sandbox-only
artefacts that are wire-ready for a single graduation step (SKILL.md
copy + manual registry splice). The brief schema covers the hardest
case (authority-MCP-using persona); the simpler inline-logic case is a
strict subset.

## What it did NOT do

- Did not modify `api/server/personae/`, `api/shared/personas.py`, or
  any other live tree.
- Did not add `controller` to `PERSONA_AUTO_CLOSE`. Production-honest
  default: every gate stays open until explicitly opted in.
- Did not generate a regression test under
  `tests/api/server/personae/test_authority_parity.py`. That's a Phase
  6 follow-up (the parity test pattern is already established for the
  three Phase-4 migrated personae and can be parameterised on
  `controller` when the persona graduates for real).

## Next step

The operator runs `bash tools/scratch/compose-persona/run-001-controller/graduate.sh`
to copy the SKILL.md into place + print the registry entry for splicing.
