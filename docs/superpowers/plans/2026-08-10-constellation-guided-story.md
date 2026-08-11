# Constellation Guided Story Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the full-screen Constellation understandable without a presenter by orienting the viewer, labelling replay truthfully, guiding one cross-functional Aurora journey, naming governance outcomes, and showing where customer systems connect.

**Architecture:** Add one compact `StoryGuide` overlay as the narrative entry point instead of adding another dashboard. Keep the existing 3D scene, HUDs, Aurora API, and Narrator. A small guided-journey adapter uses the real API in live mode and a checked-in explanatory arc in read-only replay mode; existing event-driven visuals remain the evidence layer.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, Vite

---

**Design authority:** `docs/superpowers/specs/2026-08-10-zava-constellation-story-design.md`

**Depends on:** `docs/superpowers/plans/2026-08-10-blueprint-article-story-realignment.md`

**Owned files:**

- `web/blueprint/src/pages/ConstellationPage.tsx`
- `web/blueprint/src/pages/__tests__/ConstellationPage.test.tsx`
- `web/blueprint/src/components/cosmicLens/HUD/StoryGuide.tsx`
- `web/blueprint/src/components/cosmicLens/HUD/__tests__/StoryGuide.test.tsx`
- `web/blueprint/src/components/cosmicLens/HUD/guidedJourney.ts`
- `web/blueprint/src/components/cosmicLens/HUD/__tests__/guidedJourney.test.ts`
- `web/blueprint/src/components/cosmicLens/HUD/DecisionTicker.tsx`
- `web/blueprint/src/components/cosmicLens/HUD/ActivityRail.tsx`
- `web/blueprint/src/components/cosmicLens/HUD/VitalSignsBar.tsx`
- `web/blueprint/src/components/cosmicLens/HUD/Narrator.tsx`
- `web/blueprint/src/components/cosmicLens/HUD/NarrativeArcs.tsx`
- `web/blueprint/src/components/cosmicLens/HUD/PolicyRipple.tsx`
- Corresponding existing HUD tests

**Out of scope:** Changes to workflow APIs, the 3D scene model, replay recording, article prose, deployment, and customer-specific integrations.

### Task 1: Add the persistent story guide

**Files:**
- Create: `web/blueprint/src/components/cosmicLens/HUD/StoryGuide.tsx`
- Create: `web/blueprint/src/components/cosmicLens/HUD/__tests__/StoryGuide.test.tsx`

- [ ] **Step 1: Write the failing StoryGuide test**

```tsx
// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { StoryGuide } from "../StoryGuide";

describe("StoryGuide", () => {
  it("orients the viewer and labels recorded telemetry", () => {
    render(
      <StoryGuide
        isReplay
        recordedAt="2026-08-10T09:00:00Z"
        busy={false}
        error={null}
        onStartJourney={vi.fn()}
      />,
    );

    expect(
      screen.getByText(/watching a working agentic organisation/i),
    ).toBeTruthy();
    expect(screen.getByText(/recorded telemetry/i)).toBeTruthy();
  });

  it("explains real, synthetic and customer connection boundaries", () => {
    render(
      <StoryGuide
        isReplay
        busy={false}
        error={null}
        onStartJourney={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByText(/where your systems connect/i));
    expect(screen.getByText(/durable workflows/i)).toBeTruthy();
    expect(screen.getByText(/synthetic records/i)).toBeTruthy();
    expect(screen.getByText(/existing systems, skills and MCPs/i)).toBeTruthy();
  });

  it("starts the guided journey", () => {
    const onStartJourney = vi.fn();
    render(
      <StoryGuide
        isReplay={false}
        busy={false}
        error={null}
        onStartJourney={onStartJourney}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /follow one decision/i }));
    expect(onStartJourney).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Run the test and verify it fails**

```bash
npm exec vitest -- run \
  web/blueprint/src/components/cosmicLens/HUD/__tests__/StoryGuide.test.tsx
```

Expected: FAIL because `StoryGuide.tsx` does not exist.

- [ ] **Step 3: Implement the compact story guide**

```tsx
interface StoryGuideProps {
  isReplay: boolean;
  recordedAt?: string;
  busy: boolean;
  error: string | null;
  onStartJourney: () => void;
}

export function StoryGuide({
  isReplay,
  recordedAt,
  busy,
  error,
  onStartJourney,
}: StoryGuideProps) {
  const recordedLabel =
    isReplay && recordedAt
      ? `Recorded telemetry from ${new Date(recordedAt).toLocaleDateString()}`
      : isReplay
        ? "Recorded telemetry"
        : "Live runtime";

  return (
    <aside
      aria-label="Constellation story guide"
      style={{
        position: "fixed",
        top: 70,
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 32,
        width: "min(620px, calc(100vw - 720px))",
        minWidth: 420,
        padding: "12px 16px",
        border: "1px solid rgba(148,163,184,0.25)",
        borderRadius: 10,
        background: "rgba(2,6,23,0.9)",
        color: "#e2e8f0",
        fontFamily: "ui-sans-serif, system-ui",
        boxShadow: "0 8px 30px rgba(0,0,0,0.35)",
      }}
    >
      <strong>You are watching a working agentic organisation.</strong>
      <div style={{ marginTop: 4, color: "#94a3b8", fontSize: 12 }}>
        Agents, people, durable workflows, policy and enterprise tools are
        operating across functions through one shared control plane.
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          marginTop: 10,
        }}
      >
        <button type="button" onClick={onStartJourney} disabled={busy}>
          {busy ? "Starting..." : "Follow one decision"}
        </button>
        <span style={{ color: isReplay ? "#a78bfa" : "#4ade80", fontSize: 11 }}>
          {recordedLabel}
        </span>
      </div>
      {error && <div role="alert">{error}</div>}
      <details style={{ marginTop: 10, color: "#cbd5e1", fontSize: 12 }}>
        <summary style={{ cursor: "pointer" }}>
          Where your systems connect
        </summary>
        <p>
          <strong>Real:</strong> durable workflows, agent sessions, governance,
          audit, MCP boundaries and runtime events.
        </p>
        <p>
          <strong>Synthetic:</strong> organisational records, personae and
          external systems used to keep the public reference running.
        </p>
        <p>
          <strong>Connect:</strong> your existing systems, skills and MCPs,
          policies, data and people replace those edges incrementally.
        </p>
      </details>
    </aside>
  );
}
```

- [ ] **Step 4: Run the StoryGuide test**

```bash
npm exec vitest -- run \
  web/blueprint/src/components/cosmicLens/HUD/__tests__/StoryGuide.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit the story guide**

```bash
git add web/blueprint/src/components/cosmicLens/HUD/StoryGuide.tsx \
  web/blueprint/src/components/cosmicLens/HUD/__tests__/StoryGuide.test.tsx
git commit -m "feat(constellation): add story guide"
```

### Task 2: Make live and replay language truthful everywhere

**Files:**
- Modify: `web/blueprint/src/components/cosmicLens/HUD/DecisionTicker.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/HUD/ActivityRail.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/HUD/VitalSignsBar.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/HUD/__tests__/DecisionTicker.test.tsx`
- Create: `web/blueprint/src/components/cosmicLens/HUD/__tests__/ActivityRail.story.test.tsx`

- [ ] **Step 1: Add the failing DecisionTicker replay assertion**

Append:

```tsx
it("labels replay data as recorded rather than live", async () => {
  render(<DecisionTicker enabled={true} isReplay />);
  await waitFor(() => {
    expect(screen.getByText(/Recorded · org decisions and insights/i)).toBeTruthy();
  });
});
```

- [ ] **Step 2: Add a failing ActivityRail copy test**

```tsx
// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../../../lib/useReplayMode", () => ({
  useReplayMode: () => ({ isReplay: true, recordedAt: "2026-08-10T09:00:00Z" }),
}));

import { ActivityRail } from "../ActivityRail";

describe("ActivityRail story copy", () => {
  it("labels replay activity and avoids simulation controls in the empty state", () => {
    render(
      <ActivityRail
        flashesRef={{ current: { buffer: [], version: 0 } }}
        mode="capabilities"
      />,
    );

    expect(screen.getByText("Recorded activity")).toBeTruthy();
    expect(screen.getByText(/Waiting for organisational activity/i)).toBeTruthy();
    expect(screen.queryByText(/BURST/i)).toBeNull();
  });
});
```

- [ ] **Step 3: Run both tests and verify they fail**

```bash
npm exec vitest -- run \
  web/blueprint/src/components/cosmicLens/HUD/__tests__/DecisionTicker.test.tsx \
  web/blueprint/src/components/cosmicLens/HUD/__tests__/ActivityRail.story.test.tsx
```

Expected: FAIL because `DecisionTicker` has no `isReplay` prop and `ActivityRail` always says `Live activity` and `Press the BURST button`.

- [ ] **Step 4: Add replay-aware labels**

Change the `DecisionTicker` props to:

```typescript
export function DecisionTicker({
  enabled = true,
  max = 8,
  isReplay = false,
}: {
  enabled?: boolean;
  max?: number;
  isReplay?: boolean;
}) {
```

Replace its heading with:

```tsx
<div style={{ opacity: 0.6, marginBottom: 4 }}>
  {isReplay ? "Recorded" : "Live"} · org decisions and insights
</div>
```

In `ActivityRail.tsx`, import and call `useReplayMode()`:

```typescript
import { useReplayMode } from "../../../lib/useReplayMode";

const replay = useReplayMode();
```

Replace `Live activity` with:

```tsx
{replay.isReplay ? "Recorded activity" : "Live activity"}
```

Replace the empty-state sentence with:

```tsx
Waiting for organisational activity to arrive.
```

In `VitalSignsBar.tsx`, add a truthful tooltip to the status pill root:

```tsx
title={
  replay
    ? `Recorded telemetry${recordedAt ? ` from ${recordedAt}` : ""}; not live`
    : undefined
}
```

- [ ] **Step 5: Run the replay-language tests**

```bash
npm exec vitest -- run \
  web/blueprint/src/components/cosmicLens/HUD/__tests__/DecisionTicker.test.tsx \
  web/blueprint/src/components/cosmicLens/HUD/__tests__/ActivityRail.story.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit replay truthfulness**

```bash
git add web/blueprint/src/components/cosmicLens/HUD/DecisionTicker.tsx \
  web/blueprint/src/components/cosmicLens/HUD/ActivityRail.tsx \
  web/blueprint/src/components/cosmicLens/HUD/VitalSignsBar.tsx \
  web/blueprint/src/components/cosmicLens/HUD/__tests__/DecisionTicker.test.tsx \
  web/blueprint/src/components/cosmicLens/HUD/__tests__/ActivityRail.story.test.tsx
git commit -m "fix(constellation): label replay truthfully"
```

### Task 3: Reuse the Aurora arc as a guided explanation

**Files:**
- Create: `web/blueprint/src/components/cosmicLens/HUD/guidedJourney.ts`
- Create: `web/blueprint/src/components/cosmicLens/HUD/__tests__/guidedJourney.test.ts`
- Modify: `web/blueprint/src/components/cosmicLens/HUD/StoryGuide.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/HUD/Narrator.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/HUD/NarrativeArcs.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/HUD/__tests__/Narrator.test.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/HUD/__tests__/NarrativeArcs.test.tsx`

- [ ] **Step 1: Write guided-journey adapter tests**

```typescript
import { afterEach, describe, expect, it, vi } from "vitest";
import { loadGuidedJourney } from "../guidedJourney";

describe("loadGuidedJourney", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("uses checked-in narration in read-only replay mode", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const result = await loadGuidedJourney(true);

    expect(result.phases.map((phase) => phase.phase)).toEqual([
      "overrun",
      "cfo_observe",
      "approve",
      "cfo_observe_post",
      "spawn_invoices",
      "ceo_synthesise",
    ]);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("uses the real Aurora endpoint in live mode", async () => {
    const response = {
      phases: [{ phase: "overrun", elapsed_ms: 1 }],
      total_elapsed_ms: 1,
      narrative: "live arc",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(response), { status: 200 })),
    );

    await expect(loadGuidedJourney(false)).resolves.toEqual(response);
  });

  it("surfaces a failed live trigger", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("no", { status: 503 })),
    );

    await expect(loadGuidedJourney(false)).rejects.toThrow(
      "Could not start the Aurora journey (503)",
    );
  });
});
```

- [ ] **Step 2: Run the adapter test and verify it fails**

```bash
npm exec vitest -- run \
  web/blueprint/src/components/cosmicLens/HUD/__tests__/guidedJourney.test.ts
```

Expected: FAIL because `guidedJourney.ts` does not exist.

- [ ] **Step 3: Implement the live/replay adapter**

```typescript
import type { ArcResult } from "./Narrator";

const REPLAY_AURORA_ARC: ArcResult = {
  phases: [
    { phase: "overrun", elapsed_ms: 0 },
    {
      phase: "cfo_observe",
      elapsed_ms: 2500,
      headline: "Budget pressure crossed the CFO observation threshold.",
    },
    { phase: "approve", elapsed_ms: 5000 },
    {
      phase: "cfo_observe_post",
      elapsed_ms: 7500,
      freezes_remaining: 1,
    },
    {
      phase: "spawn_invoices",
      elapsed_ms: 10000,
      cascades: [{}, {}, {}],
    },
    {
      phase: "ceo_synthesise",
      elapsed_ms: 12500,
      headline: "The executive view now includes the governed intervention.",
    },
  ],
  total_elapsed_ms: 15000,
  narrative:
    "Aurora pressure -> CFO observation -> governed policy -> in-flight escalation -> CEO synthesis",
};

export async function loadGuidedJourney(
  isReplay: boolean,
): Promise<ArcResult> {
  if (isReplay) return REPLAY_AURORA_ARC;

  const response = await fetch(
    "/api/demo/trigger/full-aurora-arc?delay_seconds=2.0&count=3",
    { method: "POST" },
  );
  if (!response.ok) {
    throw new Error(`Could not start the Aurora journey (${response.status})`);
  }
  return response.json() as Promise<ArcResult>;
}
```

- [ ] **Step 4: Wire StoryGuide to load and trigger the Narrator**

Move the `busy` and `error` state into `StoryGuide`, reduce its public props to
`isReplay` and `recordedAt`, and use:

```tsx
interface StoryGuideProps {
  isReplay: boolean;
  recordedAt?: string;
}

const [busy, setBusy] = useState(false);
const [error, setError] = useState<string | null>(null);

async function startJourney() {
  setBusy(true);
  setError(null);
  try {
    triggerNarrator(await loadGuidedJourney(isReplay));
  } catch (caught) {
    setError(caught instanceof Error ? caught.message : String(caught));
  } finally {
    setBusy(false);
  }
}
```

Replace the start-journey test in `StoryGuide.test.tsx` with:

```tsx
const loadGuidedJourneyMock = vi.hoisted(() => vi.fn());
const triggerNarratorMock = vi.hoisted(() => vi.fn());

vi.mock("../guidedJourney", () => ({
  loadGuidedJourney: loadGuidedJourneyMock,
}));
vi.mock("../Narrator", () => ({
  triggerNarrator: triggerNarratorMock,
}));

it("loads and starts the guided journey", async () => {
  const arc = {
    phases: [{ phase: "overrun", elapsed_ms: 1 }],
    total_elapsed_ms: 1,
    narrative: "test",
  };
  loadGuidedJourneyMock.mockResolvedValue(arc);
  render(<StoryGuide isReplay />);

  fireEvent.click(screen.getByRole("button", { name: /follow one decision/i }));

  await waitFor(() => {
    expect(loadGuidedJourneyMock).toHaveBeenCalledWith(true);
    expect(triggerNarratorMock).toHaveBeenCalledWith(arc);
  });
});
```

Update the two remaining render calls in that test file to the final prop shape:

```tsx
render(
  <StoryGuide
    isReplay
    recordedAt="2026-08-10T09:00:00Z"
  />,
);

render(<StoryGuide isReplay />);
```

- [ ] **Step 5: Repair Narrator language and expose the named cast**

Replace the overrun secondary copy with:

```typescript
"A budget overrun arrived on Aurora - the kind of signal that starts a response across finance, operations and executive oversight."
```

Replace `CFO observes - autonomously.` with:

```typescript
"CFO agent observes within delegated authority."
```

In `NarrativeArcs.tsx`, remove the `defaultCollapsed` prop so the cast is open
when the guided story begins.

Update the existing tests to assert the new overrun sentence and that a named
arc is visible immediately after render.

- [ ] **Step 6: Run guided-journey and narrator tests**

```bash
npm exec vitest -- run \
  web/blueprint/src/components/cosmicLens/HUD/__tests__/guidedJourney.test.ts \
  web/blueprint/src/components/cosmicLens/HUD/__tests__/StoryGuide.test.tsx \
  web/blueprint/src/components/cosmicLens/HUD/__tests__/Narrator.test.tsx \
  web/blueprint/src/components/cosmicLens/HUD/__tests__/NarrativeArcs.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Commit the guided journey**

```bash
git add web/blueprint/src/components/cosmicLens/HUD/guidedJourney.ts \
  web/blueprint/src/components/cosmicLens/HUD/StoryGuide.tsx \
  web/blueprint/src/components/cosmicLens/HUD/Narrator.tsx \
  web/blueprint/src/components/cosmicLens/HUD/NarrativeArcs.tsx \
  web/blueprint/src/components/cosmicLens/HUD/__tests__
git commit -m "feat(constellation): guide Aurora decision story"
```

### Task 4: Name governance outcomes in the scene

**Files:**
- Modify: `web/blueprint/src/components/cosmicLens/HUD/PolicyRipple.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/HUD/__tests__/PolicyRipple.test.tsx`

- [ ] **Step 1: Add the failing named-policy assertion**

After emitting the policy event in the existing test, add:

```tsx
const label = await screen.findByTestId("policy-ripple-label");
expect(label.textContent).toMatch(/CFO approved policy for Aurora/i);
```

Include `decided_on: ["BRAND-aurora"]` in the emitted event.

- [ ] **Step 2: Run the focused test and verify it fails**

```bash
npm exec vitest -- run \
  web/blueprint/src/components/cosmicLens/HUD/__tests__/PolicyRipple.test.tsx
```

Expected: FAIL because only rings render.

- [ ] **Step 3: Extend ripple state with a human-readable label**

Change the type:

```typescript
type Ripple = {
  id: number;
  color: string;
  born: number;
  label: string;
};
```

When handling the event:

```typescript
const roleLabel =
  role === "cfo" ? "CFO" : role.replaceAll("_", " ");
const verdict = String(item.verdict || "set");
const verdictLabel =
  ({ approve: "approved", reject: "rejected", escalate: "escalated" } as
    Record<string, string>)[verdict] ?? verdict;
const target = String(item.decided_on?.[0] || "")
  .replace("BRAND-", "")
  .replaceAll("-", " ");
const label =
  `${roleLabel} ${verdictLabel} policy${target ? ` for ${target}` : ""}`;
setRipples((prev) => [
  ...prev,
  { id, color, born: Date.now(), label },
]);
```

Render once per ripple, outside the three-ring loop:

```tsx
<div
  data-testid="policy-ripple-label"
  style={{
    position: "absolute",
    top: "44%",
    left: "50%",
    transform: "translateX(-50%)",
    color: r.color,
    background: "rgba(2,6,23,0.9)",
    border: `1px solid ${r.color}`,
    borderRadius: 999,
    padding: "6px 12px",
    font: "12px ui-sans-serif, system-ui",
  }}
>
  {r.label}
</div>
```

- [ ] **Step 4: Run the PolicyRipple tests**

```bash
npm exec vitest -- run \
  web/blueprint/src/components/cosmicLens/HUD/__tests__/PolicyRipple.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit named governance**

```bash
git add web/blueprint/src/components/cosmicLens/HUD/PolicyRipple.tsx \
  web/blueprint/src/components/cosmicLens/HUD/__tests__/PolicyRipple.test.tsx
git commit -m "feat(constellation): name policy outcomes"
```

### Task 5: Wire the story into the full-screen page

**Files:**
- Modify: `web/blueprint/src/pages/ConstellationPage.tsx`
- Create: `web/blueprint/src/pages/__tests__/ConstellationPage.test.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/HUD/DemoHUD.tsx`

- [ ] **Step 1: Write the failing page wiring test**

```tsx
// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../components/cosmicLens/CosmicLens", () => ({
  CosmicLens: () => <div data-testid="cosmic-lens" />,
}));
vi.mock("../../components/cosmicLens/HUD/DemoHUD", () => ({
  DemoHUD: () => null,
}));
vi.mock("../../components/cosmicLens/HUD/DecisionTicker", () => ({
  DecisionTicker: ({ isReplay }: { isReplay?: boolean }) => (
    <div data-testid="ticker-mode">{isReplay ? "recorded" : "live"}</div>
  ),
}));
vi.mock("../../components/cosmicLens/HUD/PolicyRipple", () => ({
  PolicyRipple: () => null,
}));
vi.mock("../../components/cosmicLens/HUD/Narrator", () => ({
  Narrator: () => null,
}));
vi.mock("../../components/cosmicLens/HUD/StoryGuide", () => ({
  StoryGuide: ({ isReplay }: { isReplay: boolean }) => (
    <div data-testid="story-mode">{isReplay ? "recorded" : "live"}</div>
  ),
}));
vi.mock("../../lib/useReplayMode", () => ({
  useReplayMode: () => ({
    isReplay: true,
    recordedAt: "2026-08-10T09:00:00Z",
  }),
}));

import { ConstellationPage } from "../ConstellationPage";

describe("ConstellationPage", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/?view=constellation");
  });

  it("wires replay truth into the story guide and ticker", () => {
    render(<ConstellationPage />);
    expect(screen.getByTestId("cosmic-lens")).toBeTruthy();
    expect(screen.getByTestId("story-mode").textContent).toBe("recorded");
    expect(screen.getByTestId("ticker-mode").textContent).toBe("recorded");
  });
});
```

- [ ] **Step 2: Run the page test and verify it fails**

```bash
npm exec vitest -- run \
  web/blueprint/src/pages/__tests__/ConstellationPage.test.tsx
```

Expected: FAIL because the page does not use `useReplayMode`, render `StoryGuide`, or pass replay state to `DecisionTicker`.

- [ ] **Step 3: Wire replay state and StoryGuide**

Import:

```typescript
import { StoryGuide } from "../components/cosmicLens/HUD/StoryGuide";
import { useReplayMode } from "../lib/useReplayMode";
```

Inside the page:

```typescript
const replay = useReplayMode();
```

Render:

```tsx
<StoryGuide
  isReplay={replay.isReplay}
  recordedAt={replay.recordedAt}
/>
<CosmicLens embed={embed} />
<DemoHUD enabled={demoEnabled} />
<DecisionTicker enabled={true} isReplay={replay.isReplay} />
<PolicyRipple enabled={true} />
<Narrator />
```

Move DemoHUD's closed and open positions from `top: 16` to `top: 72` so the
presenter controls do not overlap the always-visible top bar.

- [ ] **Step 4: Run the page and focused HUD tests**

```bash
npm exec vitest -- run \
  web/blueprint/src/pages/__tests__/ConstellationPage.test.tsx \
  web/blueprint/src/components/cosmicLens/HUD/__tests__
```

Expected: PASS.

- [ ] **Step 5: Build the blueprint**

```bash
npm run build:blueprint
```

Expected: TypeScript and Vite build complete successfully.

- [ ] **Step 6: Commit page integration**

```bash
git add web/blueprint/src/pages/ConstellationPage.tsx \
  web/blueprint/src/pages/__tests__/ConstellationPage.test.tsx \
  web/blueprint/src/components/cosmicLens/HUD/DemoHUD.tsx
git commit -m "feat(constellation): add guided public journey"
```

### Task 6: Verify the full Constellation track

**Files:**
- Verify only; no changes expected.

- [ ] **Step 1: Run all Constellation unit tests**

```bash
npm exec vitest -- run \
  web/blueprint/src/components/cosmicLens \
  web/blueprint/src/pages/__tests__/ConstellationPage.test.tsx
```

Expected: PASS.

- [ ] **Step 2: Build the public bundle**

```bash
npm run build:blueprint
```

Expected: PASS.

- [ ] **Step 3: Confirm ownership isolation**

```bash
git diff --name-only -- README.md docs .github/workflows infra deploy scripts
```

Expected: no documentation or deployment files changed by this plan.
