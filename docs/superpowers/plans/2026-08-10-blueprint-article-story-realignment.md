# Blueprint Article Story Realignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Realign the published blueprint essay around Zava as a working reference implementation of an agentic organisation at scale while preserving the useful printing-press argument.

**Architecture:** Keep the existing section structure and visual components. Change only the narrative spine: isolated pilots become the problem, the running reference organisation becomes the answer, Constellation becomes the visibility layer, and connecting the customer's existing estate becomes the close. A source-level Vitest contract guards high-value language without coupling prose to brittle DOM snapshots.

**Tech Stack:** React 19, TypeScript, Vitest, Vite

---

**Design authority:** `docs/superpowers/specs/2026-08-10-zava-constellation-story-design.md`

**Depends on:** `docs/superpowers/plans/2026-08-10-zava-story-documentation-alignment.md`

**Owned files:**

- `web/blueprint/src/sections/Opening.tsx`
- `web/blueprint/src/sections/Composition.tsx`
- `web/blueprint/src/sections/Personae.tsx`
- `web/blueprint/src/sections/Memory.tsx`
- `web/blueprint/src/sections/MetaSkill.tsx`
- `web/blueprint/src/sections/Observatory.tsx`
- `web/blueprint/src/sections/Closing.tsx`
- `web/blueprint/src/App.tsx`
- `web/blueprint/src/sections/__tests__/StoryContract.test.ts`

**Out of scope:** The full-screen Constellation runtime, HUD behavior, deployment workflows, replay tape generation, and external plugin copy.

### Task 1: Add the article story contract

**Files:**
- Create: `web/blueprint/src/sections/__tests__/StoryContract.test.ts`

- [ ] **Step 1: Write the failing source-level contract**

```typescript
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const here = dirname(fileURLToPath(import.meta.url));

function section(name: string): string {
  return readFileSync(resolve(here, "..", `${name}.tsx`), "utf8");
}

describe("blueprint article story contract", () => {
  it("leads with the approved agentic-organisation promise", () => {
    expect(section("Opening")).toContain(
      "See what an agentic organisation",
    );
    expect(section("Opening")).toContain(
      "use the blueprint to build yours",
    );
  });

  it("does not position simulation as the product", () => {
    expect(section("Personae")).not.toContain(
      "The people in the simulated organisation",
    );
    expect(section("Personae")).not.toContain(
      "The substrate runs as a simulated organisation",
    );
    expect(section("MetaSkill")).not.toContain(
      "a live simulation running against real Azure infra",
    );
  });

  it("names Constellation as the visual command surface", () => {
    const observatory = section("Observatory");
    expect(observatory).toContain("Constellation");
    expect(observatory).toContain("visual command surface");
  });

  it("keeps memory claims bounded to enabled domains", () => {
    const memory = section("Memory");
    expect(memory).toContain("Where memory is enabled");
    expect(memory).not.toContain("Anthropic invented this");
  });

  it("closes with incremental connection to the existing estate", () => {
    const closing = section("Closing");
    expect(closing).toContain("existing agent");
    expect(closing).toContain("existing systems");
    expect(closing).toContain("make its edges real");
    expect(closing).not.toContain("nine workflows");
  });
});
```

- [ ] **Step 2: Run the focused test and verify it fails**

```bash
npm exec vitest -- run \
  web/blueprint/src/sections/__tests__/StoryContract.test.ts
```

Expected: FAIL on every assertion because the current article uses the older opening, simulation-first persona copy, unbounded memory claims, and stale closing count.

- [ ] **Step 3: Commit the red test**

```bash
git add web/blueprint/src/sections/__tests__/StoryContract.test.ts
git commit -m "test(blueprint): guard article story"
```

### Task 2: Reframe the opening and working reference organisation

**Files:**
- Modify: `web/blueprint/src/sections/Opening.tsx:1-48`
- Modify: `web/blueprint/src/sections/Composition.tsx:9-46`
- Test: `web/blueprint/src/sections/__tests__/StoryContract.test.ts`

- [ ] **Step 1: Replace the opening headline and lede**

Use this headline block:

```tsx
<h1 className="headline">
  <em>See what an agentic organisation</em>
  <br />
  actually looks like.
</h1>
<p className="subhead">And use the blueprint to build yours.</p>
```

Replace the first three lede paragraphs with:

```tsx
<p className="lede">
  Most agent demonstrations show one assistant doing one task. They do not
  show what happens when specialised agents and people operate across many
  functions, share enterprise systems, wait for decisions, recover from
  failure and remain governed as one workforce.
</p>

<p className="lede">
  That is why agentic initiatives keep restarting. Each pilot rebuilds its
  orchestration, prompts, evaluation, integrations, policy and observability.
  The next initiative inherits almost none of it.
</p>

<p className="lede">
  Zava is a working reference implementation of the alternative: an agentic
  organisation operating through a shared control plane. It runs as a complete
  synthetic organisation so the pattern can be shown anywhere, then exposes
  the same boundaries where your systems, skills, MCPs, policies, data and
  people connect.
</p>
```

Keep the printing-press pullquote unchanged as the supporting analogy.

- [ ] **Step 2: Reframe Composition as the running reference**

Replace the section subtitle, heading, and first two paragraphs with:

```tsx
<p className="subtitle">A working reference implementation</p>
<h2 className="section-title">
  An agentic organisation you can inspect while it runs.
</h2>
<p className="body">
  Zava makes the architecture concrete. The {data.vertical.display_name} view
  running here composes specialised skills, shared MCP adapters, durable
  workflows, personae, governance and observability through one control plane.
  The code is executable; the organisational records and external systems are
  synthetic so the reference can run without a customer's estate.
</p>
<p className="body">
  The point is not that every routine decision should be delegated to an
  agent. It is to show how many bounded capabilities can operate together,
  reuse the same foundations and hand work to people at explicit authority
  boundaries.
</p>
```

Keep the live composition map and segment explanation.

- [ ] **Step 3: Run the article contract**

```bash
npm exec vitest -- run \
  web/blueprint/src/sections/__tests__/StoryContract.test.ts
```

Expected: the opening assertions pass; remaining assertions still fail.

- [ ] **Step 4: Commit the opening and composition changes**

```bash
git add web/blueprint/src/sections/Opening.tsx \
  web/blueprint/src/sections/Composition.tsx
git commit -m "docs(blueprint): centre agentic organisation"
```

### Task 3: Make people and memory truthful connection points

**Files:**
- Modify: `web/blueprint/src/sections/Personae.tsx:31-60`
- Modify: `web/blueprint/src/sections/Memory.tsx:1-54`
- Test: `web/blueprint/src/sections/__tests__/StoryContract.test.ts`

- [ ] **Step 1: Replace simulation-first persona copy**

Use:

```tsx
<p className="subtitle">The people who operate the reference organisation</p>
<h2 className="section-title">
  Agent and human authority share the same boundary.
</h2>
<p className="body">
  Workflows need approvers, reviewers and delegates. In the public
  demonstrator, synthetic personae keep that work moving without requiring
  customer identities or inboxes. In a connected organisation, the same
  boundary can resolve to a real person, an agent acting under delegation, or
  an escalation chain.
</p>
<p className="body">
  A persona records the role, function, workflow scope and authority context
  used by that routing. Zava has {data.total} personae in the active reference
  organisation. One, the AP controller, looks like this:
</p>
```

Replace the closing persona paragraph with:

```tsx
<p className="body">
  Every persona boundary is a connection point. Synthetic personae make the
  reference portable; customer people, delegation rules and approval channels
  connect at the same boundary without changing the durable workflow around
  them.
</p>
```

- [ ] **Step 2: Bound the memory claims to implemented capability**

Change the first memory item to:

```typescript
{
  label: "01 · Memory",
  title: "Where memory is enabled, one run can inform the next.",
  body:
    "Decisions, approvals and tool calls can be written to a structured domain store. A later agent session retrieves relevant entries and adds them to its context, so useful precedent can travel across runs without being baked into a prompt.",
},
```

Change the second item to:

```typescript
{
  label: "02 · Consolidation",
  title: "Configured consolidation turns repeated evidence into a smaller lesson set.",
  body:
    "At configured intervals, the substrate can review recent memory entries, identify repeated outcomes and write a more durable lesson back to the same governed store. Raw runs remain evidence; promoted lessons remain attributable and policy-bound.",
},
```

Replace `Every workflow projects` in the knowledge-graph item with:

```text
Enabled workflows project the entities they touch
```

- [ ] **Step 3: Run the article contract**

```bash
npm exec vitest -- run \
  web/blueprint/src/sections/__tests__/StoryContract.test.ts
```

Expected: persona and memory assertions pass; Constellation and closing assertions remain red.

- [ ] **Step 4: Commit people and memory changes**

```bash
git add web/blueprint/src/sections/Personae.tsx \
  web/blueprint/src/sections/Memory.tsx
git commit -m "docs(blueprint): clarify people and memory"
```

### Task 4: Name Constellation and explain vertical adaptation

**Files:**
- Modify: `web/blueprint/src/sections/MetaSkill.tsx:7-58`
- Modify: `web/blueprint/src/sections/Observatory.tsx:1-88`
- Test: `web/blueprint/src/sections/__tests__/StoryContract.test.ts`

- [ ] **Step 1: Reframe the extension section around customer reuse**

Keep `Research -> Design -> Build -> Prove`, but replace the private-live
sentence with:

```tsx
<strong>zava-workspace-deploy</strong> takes that proven output and requires
an explicit choice: private-live (the reference implementation running on
live Azure infrastructure with synthetic organisational activity) or
public-replay (recorded telemetry anyone can inspect without writable
systems).
```

Add after the mode explanation:

```tsx
<p className="body">
  The output is an executable blueprint, not a requirement to replace the
  customer's estate. Existing agent investments, workflows, skills, MCPs,
  policies and people connect at the same boundaries; synthetic edges remain
  only where a real connection has not been made yet.
</p>
```

Add this proof-status sentence:

```tsx
<p className="body">
  Telco is the current proven reference. Other vertical packs demonstrate
  different industry behavior and are described as proven only when their own
  evidence gate passes.
</p>
```

- [ ] **Step 2: Turn Observatory into the Constellation explanation**

Replace the subtitle, heading, and first two body paragraphs with:

```tsx
<p className="subtitle">Constellation</p>
<h2 className="section-title">
  The visual command surface for the agentic workforce.
</h2>

<p className="body observatory__note">
  Constellation makes the organisation-wide pattern visible. Work begins
  across functions, agents use shared skills and tools, policies intervene,
  people decide and durable workflows resolve. The public page uses recorded
  telemetry from the same runtime so it remains inspectable without exposing
  writable systems.
</p>

<p className="body">
  Each event maps to execution evidence rather than decorative animation. The
  active domain, phase, skill, MCP call, validator and authority outcome remain
  traceable to the workflow that produced them.
</p>
```

Add this helper above `Observatory`:

```typescript
function constellationUrl(): string {
  const isLocalBlueprint = window.location.port === "5275";
  const url = isLocalBlueprint
    ? new URL(window.location.href)
    : new URL(getDemoUrl("article-constellation"));
  if (!isLocalBlueprint) url.pathname = "/blueprint/";
  url.searchParams.set("view", "constellation");
  return url.toString();
}
```

Change the CTA to:

```tsx
<a
  className="observatory__cta"
  href={constellationUrl()}
  target="_blank"
  rel="noopener noreferrer"
>
  Open Constellation →
</a>
```

- [ ] **Step 3: Run the article contract**

```bash
npm exec vitest -- run \
  web/blueprint/src/sections/__tests__/StoryContract.test.ts
```

Expected: only the closing assertions remain red.

- [ ] **Step 4: Commit Constellation and adaptation copy**

```bash
git add web/blueprint/src/sections/MetaSkill.tsx \
  web/blueprint/src/sections/Observatory.tsx
git commit -m "docs(blueprint): name Constellation story"
```

### Task 5: Replace the closing with the incremental adoption path

**Files:**
- Modify: `web/blueprint/src/sections/Closing.tsx:4-93`
- Modify: `web/blueprint/src/App.tsx:75-95`
- Test: `web/blueprint/src/sections/__tests__/StoryContract.test.ts`

- [ ] **Step 1: Replace the closing body before the final question**

Use:

```tsx
<p className="body">
  What we hand over is a running reference implementation: shared governance,
  durable workflows, agent and human boundaries, skills, MCP interfaces,
  memory, audit and one control plane that makes the workforce visible.
</p>

<p className="body">
  The public organisation uses synthetic records, personae and external
  systems so it can run anywhere. Those are connection points, not a separate
  simulation phase. Keep the existing agent and workflow investments that fit,
  connect existing systems and data through the MCP boundaries, bring real
  people into the same approval gates, and make its edges real one valuable
  journey at a time.
</p>

<p className="body">
  Start with the reference pattern, connect one cross-functional journey to
  the customer's estate, then expand across functions without rebuilding
  identity, policy, audit, orchestration and observability for every use case.
</p>
```

Replace the final statement with:

```tsx
<p className="closing__final">
  The interesting question is no longer which isolated agent to fund next,
  but which parts of your organisation should begin operating as one agentic
  workforce.
</p>
```

Keep the existing three CTAs, but change the `Build this for your own
organisation` note to:

```tsx
<span className="closing__cta-note">
  Use the executable blueprint to agree the pattern, then connect your
  existing systems, skills, MCPs, policies, data and people.
</span>
```

- [ ] **Step 2: Update the article footer date**

In `web/blueprint/src/App.tsx`, change:

```tsx
{" · May 2026"}
```

to:

```tsx
{" · August 2026"}
```

- [ ] **Step 3: Run the story contract and existing section test**

```bash
npm exec vitest -- run \
  web/blueprint/src/sections/__tests__/StoryContract.test.ts \
  web/blueprint/src/sections/__tests__/Composition.vertical.test.tsx
```

Expected: PASS.

- [ ] **Step 4: Build the published article**

```bash
npm run build:blueprint
```

Expected: TypeScript and Vite build complete successfully.

- [ ] **Step 5: Commit the closing**

```bash
git add web/blueprint/src/sections/Closing.tsx web/blueprint/src/App.tsx
git commit -m "docs(blueprint): connect story to customer estate"
```

### Task 6: Verify article-only ownership

**Files:**
- Verify only; no changes expected.

- [ ] **Step 1: Run all blueprint section and story tests**

```bash
npm exec vitest -- run web/blueprint/src/sections
```

Expected: PASS.

- [ ] **Step 2: Confirm no runtime HUD or deployment files changed**

```bash
git diff --name-only -- \
  web/blueprint/src/components/cosmicLens \
  web/blueprint/src/pages \
  .github/workflows infra deploy scripts
```

Expected: no output from this plan.
