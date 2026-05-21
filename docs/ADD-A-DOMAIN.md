# Add a Domain

This is the canonical "how do I add a new business workflow_type to the
Zava control-plane substrate?" doc. It answers two questions you might
arrive with:

1. **What gets added?** A new `Domain` row in `api/shared/domains.py`,
   one orchestrator + activities pair under `api/functions/workflows/`,
   one projection under `api/server/services/entity_projections/`, the
   persona `SKILL.md` files referenced by the new domain's persona gates,
   any new MCP tools the agents need, and the cadence/ambient-trigger
   plumbing if the domain is observed in the background.

2. **How automatic is it?** Almost entirely. The substrate has a
   four-stage **compose-domain** pipeline that takes a YAML brief and
   produces a complete sandboxed Durable-fidelity domain — orchestrator,
   per-phase graphs, validators, agent skills, MCP tool stubs,
   persona(e) — plus a `graduate.sh` script that mechanically wires the
   sandbox into the live trees. The hand-authored input is the brief.
   Everything downstream is generated.

---

## The four levels of automation

### Level 0 — manual edit

For a quick experiment, you can edit `api/shared/domains.py` directly,
add a phase tuple, write the orchestrator + activities yourself, and
add a projection by hand. This is what the original POC1
(`expense-claim`) and POC2 (`hiring`) domains did. It's the longest
path; you'll touch ~12 files and skip the boot-time validators that
the generators check.

### Level 1 — author a brief, drive the generators by hand

If you know the brief shape (`workflow_type`, phases, gates, function
membership, ambient triggers, agent skills), you can call the
**v3 generators** directly:

- [`docs/superpowers/skills/author-durable-domain/SKILL.md`](superpowers/skills/author-durable-domain/SKILL.md)
  — generates the orchestrator + activities + per-phase graphs.
- [`docs/superpowers/skills/author-runtime-skill/SKILL.md`](superpowers/skills/author-runtime-skill/SKILL.md)
  — generates an agent skill (markdown + Python policy block).
- [`docs/superpowers/skills/author-persona/SKILL.md`](superpowers/skills/author-persona/SKILL.md)
  — generates a persona `SKILL.md` with the executable
  `decision_policy` block.
- [`docs/superpowers/skills/author-mcp-tool/SKILL.md`](superpowers/skills/author-mcp-tool/SKILL.md)
  — generates an MCP tool stub.

You'd run each in turn. This is what the agency-pitch wave did when
the v4 meta-skill wasn't ready.

### Level 2 — drive the v4 meta-skill (recommended)

Use [`docs/superpowers/skills/compose-domain/SKILL.md`](superpowers/skills/compose-domain/SKILL.md).
It's a sequential enrichment pipeline that orchestrates the v3
generators on top of a shared brief:

```
brief.yaml  ──►  author-domain-skeleton    (Domain row + Phase tuple + HitlGate tuple)
            ──►  author-entity-projection  (projection function for the workflow_type)
            ──►  author-decision-mapping   (persona SKILL.md decision_policy blocks)
            ──►  author-function-membership (FUNCTIONS[fn].owns_domains entry)
            ──►  author-ambient-trigger    (BusTrigger / CypherTrigger / CadenceTrigger)
            ──►  v3 generators              (orchestrator + activities + agent skills)
            ──►  graduate.sh                (mechanically wires the sandbox into live trees)
```

The brief schema lives at
[`docs/superpowers/skills/compose-domain/brief.schema.yaml`](superpowers/skills/compose-domain/brief.schema.yaml).
Nineteen worked-example briefs ship in `docs/superpowers/specs/archive/`
(they were moved there after graduation; new briefs are authored to
`docs/superpowers/specs/<workflow_type>-brief.yaml` and archived after
`graduate.sh` succeeds). `fleet-purchase-card-brief.yaml` is the
freshest top-down authoring example.

The v4 sub-skills:

- [author-domain-skeleton](superpowers/skills/compose-domain/sub-skills/author-domain-skeleton/SKILL.md)
- [author-entity-projection](superpowers/skills/compose-domain/sub-skills/author-entity-projection/SKILL.md)
- [author-decision-mapping](superpowers/skills/compose-domain/sub-skills/author-decision-mapping/SKILL.md)
- [author-function-membership](superpowers/skills/compose-domain/sub-skills/author-function-membership/SKILL.md)
- [author-ambient-trigger](superpowers/skills/compose-domain/sub-skills/author-ambient-trigger/SKILL.md)

Output of every stage lands under `tools/scratch/compose-domain/<slug>/`
(a sandbox directory — never touches `api/` directly). Once you're
happy with the sandbox, run its `graduate.sh` to copy + wire
everything into the live trees and update the registries.

### Level 3 — pointer skill from the workspace

There's a thin **add-domain** skill at
[`.github/skills/add-domain/SKILL.md`](../.github/skills/add-domain/SKILL.md)
that the Copilot CLI auto-discovers. It does no work itself; it just
points at the v4 procedure above. Trigger phrases include "add a
new domain", "compose a domain", "design a new workflow for X",
"let's build the X domain".

---

## Adding a `summary_policy` to an existing persona (v1.0+ closed loop)

Different question — you're not adding a workflow_type, you're
extending an existing persona to publish `Insight` nodes via the
autonomous-domain-insights system (see
[`ARCHITECTURE.md` §12](ARCHITECTURE.md#12-autonomous-domain-insights-closed-loop-v10-v13-may-2026)).

Add a `summary_policy:` YAML block to the persona's
`api/server/personae/<role>/SKILL.md` frontmatter. The block must:

1. Read graph state via the injected `graph` callable
   (`graph.query("MATCH …")`).
2. Compose a `summary` dict with `headline`, `body`, `kpis`,
   `proposed_actions`, and `fingerprint`.
3. Make the fingerprint **deterministic over the inputs** so the
   cadence loop only writes a new Insight when state actually
   changes.
4. Avoid `import` statements (the sandbox doesn't expose `__import__`)
   and `sorted()` (use `list.sort()` in-place or `ORDER BY` in
   Cypher). `json` is also unavailable in the sandbox.

For first-person prose Insight bodies (the v1.2 polish), add a
parallel `voice_render:` block that takes the structured `summary`
and assigns a `body = "..."` string.

Worked examples: `api/server/personae/cfo/SKILL.md` (Brand spend vs
budget), `api/server/personae/hr_director/SKILL.md` (departmental
attrition), `api/server/personae/ceo/SKILL.md` (cross-domain
synthesis).

The `_load_personae()` discovery walks `api/server/personae/*/SKILL.md`
on FastAPI startup, so the persona is picked up the next time
`make server` (or `make up`) restarts the API. The cadence loop
fires the persona's summary every `INSIGHT_REFRESH_SECONDS` (default
300, demo profile sets 15) and skips writes when the fingerprint is
unchanged.

---

## Wiring checklist (after the generators run, before merging)

Whichever level you used, before the new domain is fully alive:

- [ ] `api/shared/domains.py` — `Domain` row added with `phases`,
      `hitl_gates`, `skills`, `spawn_fn`, `realistic_interval_seconds`.
      `function` is auto-stamped at boot by `_wire_function_back_refs`
      from `api/shared/functions.py:FUNCTIONS[fn].owns_domains`.
      **`graduate.sh` does NOT patch this file — it is a required
      hand-edit. Without it the new domain is invisible to the FM
      catalogue, the cosmic lens manifest, the resolve route, and the
      triage wake set.**
- [ ] `api/shared/functions.py` — the new `workflow_type` is listed
      in `FUNCTIONS[fn].owns_domains`. Patched by `graduate.sh` step
      9 (sentinel `# compose-domain:owns_domains:<fn>`); the
      boot-time orphan validator (`_wire_function_back_refs`) raises
      if a domain isn't owned by any function.
- [ ] `function_app.py` — orchestrator + activity decorators.
      Patched by `graduate.sh` step 3 between
      `# === BEGIN compose-domain <name> ===` markers.
- [ ] `api/server/services/entity_projections/<workflow_type_snake>.py`
      exists with `WORKFLOW_TYPE` + `project()`. Generated by
      compose-domain v4 and copied into the live tree by `graduate.sh`.
- [ ] `api/server/services/entity_projections/__init__.py` — append
      `from . import <workflow_type_snake>` to the alphabetised
      import block AND add the module to the `_DOMAIN_MODULES` tuple.
      **`graduate.sh` does NOT patch this file — it is a required
      hand-edit. Without it the projection module exists but never
      registers, so no entity nodes get written for the new domain.**
- [ ] Each `HitlGate.persona` referenced by the domain has a
      corresponding `api/server/personae/<role>/SKILL.md` with a
      compilable `decision_policy` block, and a registry entry in
      `api/shared/personas.PERSONAS`.
- [ ] Tests under `tests/api/server/services/entity_projections/` and
      `tests/api/shared/` pass — the registry consistency tests are
      the canonical safety net.
- [ ] Optional: ambient agent in `api/server/services/ambient_agents/<function>.py`
      if the domain should be triggered by a graph pattern or cron
      cadence rather than an external event. Generated by
      compose-domain v4 when the brief includes an `ambient:` block.
- [ ] Optional: cadence YAML under `data/governance/cadences/` if the
      ambient agent is `CadenceTrigger`-driven.

`graduate.sh` mechanically handles 7 of these wiring steps; the two
calls out as **"required hand-edit"** above are still on you (or the
agent following [`.github/skills/add-domain/SKILL.md`](../.github/skills/add-domain/SKILL.md)
Phase 4b/4c). The optional items it leaves alone for you to fill in if
relevant.

---

## See also

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — full architecture reference
  (the four planes + the v1.0–v1.3 closed-loop layer + a per-file
  source tour).
- [`docs/superpowers/skills/compose-domain/CHECKLIST.md`](superpowers/skills/compose-domain/CHECKLIST.md)
  — exhaustive per-stage checklist for the v4 generator pipeline.
- [`docs/superpowers/skills/compose-domain/SANDBOX.md`](superpowers/skills/compose-domain/SANDBOX.md)
  — what the sandbox directory looks like before graduation.
