# AG-UI Render Implementation Plan (POC2 §4.21)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the existing `AgentDrivenComponent.tsx` primitive into `WorkflowDetail.tsx` so that the Triage agent's per-role component spec actually renders on screen. Closes POC2 §4.21.

**Architecture:** Triage Phase 4 (`cv-crystalliser` skill) emits a `component_spec` field — a list of `AgentComponentSpec` entries — into the workflow's agent_outputs. `WorkflowDetail.tsx` reads this and renders one `<AgentDrivenComponent>` per entry inside a new "Candidate scorecard" section. Different roles produce different spec kinds (Senior Data Engineer → fact_grid + skill_chips; Creative Director → fact_grid + portfolio_gallery).

**Tech Stack:** React + TypeScript. Existing `AgentDrivenComponent.tsx` already supports 5 spec kinds. No new components needed.

**Master spec:** [docs/superpowers/specs/2026-04-30-poc1-poc2-demo-ready-design.md](../specs/2026-04-30-poc1-poc2-demo-ready-design.md) §8

---

## Task 1: Extend `cv-crystalliser` SKILL.md with component-spec output

**Files:** `api/server/skills/cv-crystalliser/SKILL.md`

- [ ] **Step 1: Read the current SKILL.md.** Confirm the existing JSON output schema.

- [ ] **Step 2: Append a new `component_spec` field** to the output schema:

```markdown
## Component spec for AG-UI

In addition to the canonical profile fields, emit a `component_spec` array
of UI hints for the Control Plane to render. Pick spec kinds based on the
candidate's role:

- **Senior Data Engineer** (or any "engineer" / "developer" title) →
    [
      {"kind": "fact_grid", "title": "Profile",
       "facts": [
         {"label": "Current role", "value": <current_title>},
         {"label": "Total tenure", "value": "<tenure_years_total> yrs"},
         {"label": "Right to work", "value": <right_to_work.evidence>}
       ]},
      {"kind": "skill_chips", "title": "Top skills",
       "skills": <top 6 skills from skills array>}
    ]

- **Creative Director / Designer / Brand** roles →
    [
      {"kind": "fact_grid", "title": "Profile", "facts": [...]},
      {"kind": "portfolio_gallery", "title": "Portfolio",
       "image_urls": <up to 6 image URLs from CV — synthesise placeholder
                      paths under data/synthetic/hiring/portfolios/{candidate_id}/*.jpg if not in CV>}
    ]

- **Default** (any other role) →
    [{"kind": "fact_grid", "title": "Profile", "facts": [...]}]

If `inconsistencies` is non-empty, additionally emit a `callout`:
    {"kind": "callout", "tone": "warn",
     "text": "<count> CV/LinkedIn inconsistencies — see Inconsistencies tab"}
```

- [ ] **Step 3: Update the JSON schema example in SKILL.md** to show `component_spec` as a top-level array.

- [ ] **Step 4: Commit**

```
git commit -m "feat(skill): cv-crystalliser emits component_spec for AG-UI"
```

---

## Task 2: Persist `component_spec` on the workflow ledger

**Files:** `api/functions/graphs/triage.py`

- [ ] **Step 1: Read the current Triage graph.** Identify where `cv-crystalliser`'s output is consumed.

- [ ] **Step 2: Persist `component_spec`** alongside the canonical profile in the workflow's agent_outputs:

```python
# inside triage.py — after parsing cv-crystalliser result
agent_output = {
    "candidate_id": result["candidate_id"],
    "profile": {... canonical fields ...},
    "component_spec": result.get("component_spec", []),
    "inconsistencies": result.get("inconsistencies", []),
}
ctx.append_agent_output("cv_crystalliser", agent_output)
```

- [ ] **Step 3: Update the StateStore method** that reads agent_outputs (so the API serialiser surfaces `component_spec`).

- [ ] **Step 4: Tests** for state-store round-trip

```python
def test_state_store_round_trips_component_spec():
    spec = [{"kind": "fact_grid", "title": "Profile", "facts": [{"label": "Role", "value": "SDE"}]}]
    store = StateStore()
    store.append_agent_output(workflow_id="HIRE-1", agent="cv_crystalliser",
                              output={"profile": {...}, "component_spec": spec})
    workflow = store.get_workflow("HIRE-1")
    assert workflow.agent_outputs["cv_crystalliser"]["component_spec"] == spec
```

- [ ] **Step 5: Commit**

---

## Task 3: Render `<AgentDrivenComponent>` in `WorkflowDetail.tsx`

**Files:** `web/client/routes/WorkflowDetail.tsx`

- [ ] **Step 1: Read the current component.** Identify the right insertion point (probably near the existing "Candidate Profile" tab for hiring workflows, or at the top of the Overview tab).

- [ ] **Step 2: Pull `component_spec` from workflow data**

```tsx
const triageOutput = workflow.agent_outputs?.cv_crystalliser;
const specs = triageOutput?.component_spec ?? [];
```

- [ ] **Step 3: Render the section (only for hiring workflows)**

```tsx
import AgentDrivenComponent, { AgentComponentSpec } from "../components/AgentDrivenComponent";

{workflow.type === "hiring" && specs.length > 0 && (
  <section data-testid="candidate-scorecard" className="space-y-3">
    <h3 className="text-sm font-semibold text-slate-700">Candidate scorecard <span className="text-xs font-normal text-slate-500">— agent-emitted</span></h3>
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
      {specs.map((spec: AgentComponentSpec, i: number) =>
        <AgentDrivenComponent key={i} spec={spec}/>
      )}
    </div>
  </section>
)}
```

- [ ] **Step 4: Tests**

```tsx
// tests/web/WorkflowDetail.test.tsx
test("renders agent-emitted component spec for hiring workflows", async () => {
  // mock /api/workflows/HIRE-1 to include cv_crystalliser.component_spec with two entries
  render(<WorkflowDetail/>);
  expect(await screen.findByTestId("candidate-scorecard")).toBeInTheDocument();
  expect(screen.getByText("Profile")).toBeInTheDocument();
  expect(screen.getByText("Top skills")).toBeInTheDocument();
});

test("does not render scorecard section for expense-claim workflows", async () => {
  // mock for an expense workflow (type = "expense_claim")
  render(<WorkflowDetail/>);
  expect(screen.queryByTestId("candidate-scorecard")).not.toBeInTheDocument();
});

test("does not render scorecard when component_spec is empty", async () => {
  // hiring workflow but cv_crystalliser hasn't run yet
  render(<WorkflowDetail/>);
  expect(screen.queryByTestId("candidate-scorecard")).not.toBeInTheDocument();
});
```

- [ ] **Step 5: Commit**

```
git commit -m "feat(ui): WorkflowDetail renders agent-emitted candidate scorecard"
```

---

## Task 4: Synthetic fixture (so the demo always has data)

**Files:** `data/synthetic/hiring/cvs/*.json` (existing fixtures), maybe a fixture loader.

- [ ] **Step 1: For at least 3 of the 50 existing CV fixtures**, hand-author a `component_spec` block matching the role. This guarantees the demo has data even if a fresh Triage run hasn't completed at demo time.

- [ ] **Step 2: Update the loader** that seeds the StateStore at startup (or the simulator that injects hires) to write the fixture's `component_spec` into the workflow's agent_outputs.

- [ ] **Step 3: Verify** by booting the stack, opening any seeded HIRE-* workflow, and seeing the scorecard.

- [ ] **Step 4: Commit**

```
git commit -m "feat(ag-ui): hand-authored component_spec fixtures for demo"
```

---

## Acceptance criteria

- [ ] `cv-crystalliser` SKILL.md describes `component_spec` and the per-role kind selection
- [ ] Triage Phase 4 persists `component_spec` on the workflow's `agent_outputs.cv_crystalliser`
- [ ] `WorkflowDetail.tsx` renders the scorecard section only for hiring workflows that have a non-empty `component_spec`
- [ ] At least 3 seeded HIRE-* workflows show a populated scorecard at demo time
- [ ] All tests under `tests/web/WorkflowDetail.test.tsx` (new) pass

## Out of scope

- New `AgentComponentSpec` kinds (the 5 existing ones cover the demo)
- Editor / live-preview tooling for AG-UI specs
- Cross-workflow scorecard comparison
