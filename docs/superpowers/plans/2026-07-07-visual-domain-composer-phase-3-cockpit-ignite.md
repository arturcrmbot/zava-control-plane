# Visual Domain Composer — Phase 3 (Cockpit + Ignite) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `?view=compose` React cockpit that renders the Phase-2 SSE stream as cinematic "agent at work" theatre (thought-stream + tool/diff timeline + plan checklist + question/brief cards), and the **Ignite** mechanism (supervised restart of :3101 + :7071) that brings the new domain live and hands off to the cosmic lens.

**Architecture:** A pure reducer folds the normalized SSE events into cockpit state; a `useComposeStream` hook wires `EventSource` + the reducer + POST actions. Presentational components render each slice. Ignite is a detached shell script (`compose-ignite.sh`) that restarts the API + Functions host from PID files `boot-demo.sh` writes; the browser polls `/api/blueprint/composition` for the new `workflow_type`, then pans to the lens.

**Tech Stack:** React 19, Vite 6, TailwindCSS 4, Lucide icons, vitest + @testing-library/react. Bash for the ignite supervisor.

**Depends on:** Phases 1–2. **Design source of truth:** [`../specs/2026-07-07-visual-domain-composer-design.md`](../specs/2026-07-07-visual-domain-composer-design.md) §4.4 (event schema), §4.7 (Ignite), §5 (cockpit).

---

## File Structure

| File | Responsibility |
|---|---|
| `web/blueprint/src/pages/compose/reducer.ts` | Pure `composeReducer(state, event)` folding SSE events → `CockpitState`. |
| `web/blueprint/src/pages/compose/useComposeStream.ts` | `EventSource` + reducer + `answer()`/`approveBrief()`/`ignite()` actions. |
| `web/blueprint/src/pages/compose/api.ts` | `createSession()`, `postAnswer()`, `postBrief()`, `postIgnite()`, `pollComposition()`. |
| `web/blueprint/src/pages/ComposePage.tsx` | Route root: IntakePanel until `cid`, then Cockpit. |
| `web/blueprint/src/pages/compose/IntakePanel.tsx` | Drop/paste → `createSession`. |
| `web/blueprint/src/pages/compose/Cockpit.tsx` | 3-pane layout + overlays + Ignite. |
| `web/blueprint/src/pages/compose/ThoughtStream.tsx` | Left pane reasoning stream. |
| `web/blueprint/src/pages/compose/ActivityTimeline.tsx` + `ToolCallCard.tsx` | Center tool timeline + diff/terminal cards. |
| `web/blueprint/src/pages/compose/PlanChecklist.tsx` | Right pane plan checklist. |
| `web/blueprint/src/pages/compose/QuestionCard.tsx` | HITL question overlay. |
| `web/blueprint/src/pages/compose/BriefReviewPanel.tsx` | Editable brief review overlay. |
| `web/blueprint/src/pages/compose/IgniteButton.tsx` | Ignite + "re-arming" + lens handoff. |
| `web/blueprint/src/App.tsx` | Modify: add `view === "compose"` route. |
| `scripts/lib/compose-start.sh` | Shared `start_api` / `start_func` writing PID files. |
| `scripts/compose-ignite.sh` | Detached supervised restart of api + func. |
| `scripts/boot-demo.sh` | Modify: write PID files via the shared lib. |
| `api/server/routes/compose.py` | Modify: add `POST /{cid}/ignite`. |
| `web/blueprint/src/pages/compose/__tests__/reducer.test.ts` | reducer over canned SSE. |
| `web/blueprint/src/pages/compose/__tests__/QuestionCard.test.tsx` | posts answer. |
| `web/blueprint/src/pages/compose/__tests__/ToolCallCard.test.tsx` | renders variants. |
| `tests/api/compose/test_ignite_endpoint.py` | `/ignite` spawns the supervisor (mocked). |

---

## Task 1: The cockpit reducer (pure, TDD)

**Files:**
- Create: `web/blueprint/src/pages/compose/reducer.ts`
- Test: `web/blueprint/src/pages/compose/__tests__/reducer.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `web/blueprint/src/pages/compose/__tests__/reducer.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { composeReducer, initialState, type ComposeEvent } from "../reducer";

function run(events: ComposeEvent[]) {
  return events.reduce(composeReducer, initialState());
}

describe("composeReducer", () => {
  it("accumulates thoughts and narration", () => {
    const s = run([
      { type: "thought", text: "Reading " },
      { type: "thought", text: "the registry." },
      { type: "narration", text: "On it." },
    ]);
    expect(s.thoughts).toBe("Reading the registry.");
    expect(s.narration).toBe("On it.");
  });

  it("merges tool events by id", () => {
    const s = run([
      { type: "tool", id: "t1", title: "Creating x.py", kind: "edit", status: "pending" },
      { type: "tool", id: "t1", status: "completed", output: "done" },
    ]);
    expect(s.tools).toHaveLength(1);
    expect(s.tools[0]).toMatchObject({ id: "t1", title: "Creating x.py", status: "completed", output: "done" });
  });

  it("tracks stage and plan", () => {
    const s = run([
      { type: "stage", stage: "composing", label: "Composing" },
      { type: "plan", entries: [{ title: "brief", status: "done" }] },
    ]);
    expect(s.stage).toBe("composing");
    expect(s.plan).toEqual([{ title: "brief", status: "done" }]);
  });

  it("sets and clears a question", () => {
    let s = run([{ type: "question", request_id: "r1", text: "CFO?", options: ["CFO"] }]);
    expect(s.question).toMatchObject({ request_id: "r1", text: "CFO?" });
    s = composeReducer(s, { type: "question_cleared", request_id: "r1" });
    expect(s.question).toBeUndefined();
  });

  it("captures done + error", () => {
    const s = run([{ type: "done", workflow_type: "capex", display_name: "Capex" }]);
    expect(s.done).toEqual({ workflow_type: "capex", display_name: "Capex" });
    const e = run([{ type: "error", message: "boom", fatal: true }]);
    expect(e.error).toBe("boom");
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npm --prefix web/blueprint run test -- reducer` (or `npx vitest run src/pages/compose/__tests__/reducer.test.ts` from `web/blueprint`)
Expected: FAIL — cannot find `../reducer`.

- [ ] **Step 3: Implement `reducer.ts`**

Create `web/blueprint/src/pages/compose/reducer.ts`:

```ts
export type ToolItem = {
  id: string;
  title?: string;
  kind?: "read" | "edit" | "execute" | "search" | "other";
  status?: "pending" | "running" | "completed" | "failed";
  path?: string;
  diff?: { old: string; new: string };
  output?: string;
};

export type ComposeEvent =
  | { type: "stage"; stage: string; label?: string }
  | { type: "thought"; text: string; partial?: boolean }
  | { type: "narration"; text: string; partial?: boolean }
  | ({ type: "tool" } & Partial<ToolItem> & { id: string })
  | { type: "plan"; entries: { title: string; status: string }[] }
  | { type: "question"; request_id: string; text: string; options?: string[] }
  | { type: "question_cleared"; request_id: string }
  | { type: "brief"; request_id: string; yaml: string }
  | { type: "brief_cleared"; request_id: string }
  | { type: "done"; workflow_type: string; display_name: string }
  | { type: "error"; message: string; fatal?: boolean };

export type CockpitState = {
  stage: string;
  thoughts: string;
  narration: string;
  tools: ToolItem[];
  plan: { title: string; status: string }[];
  question?: { request_id: string; text: string; options: string[] };
  brief?: { request_id: string; yaml: string };
  done?: { workflow_type: string; display_name: string };
  error?: string;
};

export function initialState(): CockpitState {
  return { stage: "intake", thoughts: "", narration: "", tools: [], plan: [] };
}

export function composeReducer(state: CockpitState, ev: ComposeEvent): CockpitState {
  switch (ev.type) {
    case "stage":
      return { ...state, stage: ev.stage };
    case "thought":
      return { ...state, thoughts: state.thoughts + ev.text };
    case "narration":
      return { ...state, narration: ev.partial ? state.narration + ev.text : ev.text };
    case "tool": {
      const idx = state.tools.findIndex((t) => t.id === ev.id);
      const { type, ...patch } = ev;
      if (idx === -1) return { ...state, tools: [...state.tools, patch as ToolItem] };
      const tools = state.tools.slice();
      tools[idx] = { ...tools[idx], ...patch };
      return { ...state, tools };
    }
    case "plan":
      return { ...state, plan: ev.entries };
    case "question":
      return { ...state, question: { request_id: ev.request_id, text: ev.text, options: ev.options ?? [] } };
    case "question_cleared":
      return state.question?.request_id === ev.request_id ? { ...state, question: undefined } : state;
    case "brief":
      return { ...state, brief: { request_id: ev.request_id, yaml: ev.yaml } };
    case "brief_cleared":
      return state.brief?.request_id === ev.request_id ? { ...state, brief: undefined } : state;
    case "done":
      return { ...state, done: { workflow_type: ev.workflow_type, display_name: ev.display_name } };
    case "error":
      return { ...state, error: ev.message };
    default:
      return state;
  }
}
```

- [ ] **Step 4: Run to verify pass**

Run: `npm --prefix web/blueprint run test -- reducer`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add web/blueprint/src/pages/compose/reducer.ts web/blueprint/src/pages/compose/__tests__/reducer.test.ts
git commit -m "feat(compose-ui): cockpit SSE reducer (phase 3)"
```

---

## Task 2: API helpers + `useComposeStream` hook

**Files:**
- Create: `web/blueprint/src/pages/compose/api.ts`
- Create: `web/blueprint/src/pages/compose/useComposeStream.ts`

- [ ] **Step 1: Implement `api.ts`**

Create `web/blueprint/src/pages/compose/api.ts`:

```ts
export async function createSession(input: { text?: string; file?: File }): Promise<string> {
  const body = new FormData();
  if (input.file) body.append("file", input.file);
  if (input.text) body.append("text", input.text);
  const r = await fetch("/api/compose/session", { method: "POST", body });
  if (!r.ok) throw new Error(`create failed: ${r.status}`);
  return (await r.json()).compose_id as string;
}

export async function postAnswer(cid: string, request_id: string, answer: string) {
  await fetch(`/api/compose/${cid}/answer`, {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ request_id, answer }),
  });
}

export async function postBrief(cid: string, request_id: string, approved: boolean, yaml: string) {
  await fetch(`/api/compose/${cid}/brief`, {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ request_id, approved, yaml }),
  });
}

export async function postIgnite(cid: string) {
  await fetch(`/api/compose/${cid}/ignite`, { method: "POST" });
}

export async function pollComposition(workflowType: string, timeoutMs = 120000): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const r = await fetch("/api/blueprint/composition");
      if (r.ok) {
        const d = await r.json();
        if ((d.domains ?? []).some((x: any) => x.workflow_type === workflowType)) return true;
      }
    } catch { /* server restarting; keep polling */ }
    await new Promise((res) => setTimeout(res, 2000));
  }
  return false;
}
```

- [ ] **Step 2: Implement `useComposeStream.ts`**

Create `web/blueprint/src/pages/compose/useComposeStream.ts`:

```ts
import { useEffect, useReducer, useRef } from "react";
import { composeReducer, initialState, type ComposeEvent } from "./reducer";
import { postAnswer, postBrief, postIgnite } from "./api";

export function useComposeStream(cid: string | null) {
  const [state, dispatch] = useReducer(composeReducer, undefined, initialState);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!cid) return;
    const es = new EventSource(`/api/compose/${cid}/stream`);
    esRef.current = es;
    es.onmessage = (m) => {
      try { dispatch(JSON.parse(m.data) as ComposeEvent); } catch { /* ignore */ }
    };
    es.onerror = () => { es.close(); };
    return () => es.close();
  }, [cid]);

  return {
    state,
    async answer(request_id: string, value: string) {
      if (!cid) return;
      await postAnswer(cid, request_id, value);
      dispatch({ type: "question_cleared", request_id });
    },
    async approveBrief(request_id: string, approved: boolean, yaml: string) {
      if (!cid) return;
      await postBrief(cid, request_id, approved, yaml);
      dispatch({ type: "brief_cleared", request_id });
    },
    async ignite() {
      if (!cid) return;
      await postIgnite(cid);
    },
  };
}
```

- [ ] **Step 3: Typecheck**

Run: `npm --prefix web/blueprint run build` (or `npx tsc -b` in `web/blueprint`)
Expected: no type errors from these files.

- [ ] **Step 4: Commit**

```bash
git add web/blueprint/src/pages/compose/api.ts web/blueprint/src/pages/compose/useComposeStream.ts
git commit -m "feat(compose-ui): api helpers + useComposeStream hook (phase 3)"
```

---

## Task 3: Presentational components

**Files:** create the six component files below. Reuse the house design language (Tailwind, Lucide, dark-first, pill/card patterns from the design spec §5.3).

- [ ] **Step 1: `ToolCallCard.tsx` + its test**

Create `web/blueprint/src/pages/compose/ToolCallCard.tsx`:

```tsx
import { FileEdit, FileSearch, Terminal, Check, Loader2, Ban } from "lucide-react";
import type { ToolItem } from "./reducer";

const ICON = { edit: FileEdit, read: FileSearch, search: FileSearch, execute: Terminal, other: FileSearch };

export function ToolCallCard({ tool }: { tool: ToolItem }) {
  const Icon = ICON[tool.kind ?? "other"];
  const done = tool.status === "completed";
  const failed = tool.status === "failed";
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-900/60 p-3" data-testid="tool-card">
      <div className="flex items-center gap-2 text-sm text-slate-200">
        <Icon size={16} />
        <span className="font-medium">{tool.title ?? tool.path ?? tool.id}</span>
        <span className="ml-auto">
          {failed ? <Ban size={16} className="text-red-400" />
            : done ? <Check size={16} className="text-emerald-400" />
            : <Loader2 size={16} className="animate-spin text-sky-400" />}
        </span>
      </div>
      {tool.diff && (
        <pre className="mt-2 max-h-48 overflow-auto rounded bg-black/40 p-2 text-xs">
          <code className="text-emerald-300">{tool.diff.new}</code>
        </pre>
      )}
      {tool.output && tool.kind === "execute" && (
        <pre className="mt-2 max-h-48 overflow-auto rounded bg-black/40 p-2 text-xs text-slate-300">{tool.output}</pre>
      )}
    </div>
  );
}
```

Create `web/blueprint/src/pages/compose/__tests__/ToolCallCard.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ToolCallCard } from "../ToolCallCard";

describe("ToolCallCard", () => {
  it("renders an edit card with a diff", () => {
    render(<ToolCallCard tool={{ id: "t1", title: "Creating x.py", kind: "edit", status: "completed", diff: { old: "", new: "# hi" } }} />);
    expect(screen.getByText("Creating x.py")).toBeTruthy();
    expect(screen.getByText("# hi")).toBeTruthy();
  });

  it("renders an execute card with output", () => {
    render(<ToolCallCard tool={{ id: "t2", title: "graduate.sh", kind: "execute", status: "running", output: "step 1..." }} />);
    expect(screen.getByText("step 1...")).toBeTruthy();
  });
});
```

Run: `npm --prefix web/blueprint run test -- ToolCallCard`
Expected: PASS.

- [ ] **Step 2: `QuestionCard.tsx` + its test**

Create `web/blueprint/src/pages/compose/QuestionCard.tsx`:

```tsx
import { useState } from "react";

export function QuestionCard({
  question, onAnswer,
}: {
  question: { request_id: string; text: string; options: string[] };
  onAnswer: (request_id: string, answer: string) => void;
}) {
  const [text, setText] = useState("");
  return (
    <div className="rounded-xl border border-amber-500/50 bg-slate-900 p-5 shadow-xl" role="dialog" aria-label="Agent question">
      <p className="text-sm text-amber-300">The agent needs a decision</p>
      <p className="mt-1 text-base text-slate-100">{question.text}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {question.options.map((o) => (
          <button key={o} className="rounded-full border border-slate-600 px-3 py-1 text-sm hover:bg-slate-800"
            onClick={() => onAnswer(question.request_id, o)}>{o}</button>
        ))}
      </div>
      <div className="mt-3 flex gap-2">
        <input className="flex-1 rounded-md bg-slate-800 px-3 py-1.5 text-sm" value={text}
          onChange={(e) => setText(e.target.value)} placeholder="or type an answer…" aria-label="Free-text answer" />
        <button className="rounded-md bg-sky-600 px-3 py-1.5 text-sm font-medium disabled:opacity-50"
          disabled={!text.trim()} onClick={() => onAnswer(question.request_id, text.trim())}>Send</button>
      </div>
    </div>
  );
}
```

Create `web/blueprint/src/pages/compose/__tests__/QuestionCard.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QuestionCard } from "../QuestionCard";

describe("QuestionCard", () => {
  it("answers with a clicked option", () => {
    const onAnswer = vi.fn();
    render(<QuestionCard question={{ request_id: "r1", text: "CFO?", options: ["CFO", "committee"] }} onAnswer={onAnswer} />);
    fireEvent.click(screen.getByText("committee"));
    expect(onAnswer).toHaveBeenCalledWith("r1", "committee");
  });

  it("answers with free text", () => {
    const onAnswer = vi.fn();
    render(<QuestionCard question={{ request_id: "r1", text: "CFO?", options: [] }} onAnswer={onAnswer} />);
    fireEvent.change(screen.getByLabelText("Free-text answer"), { target: { value: "new persona" } });
    fireEvent.click(screen.getByText("Send"));
    expect(onAnswer).toHaveBeenCalledWith("r1", "new persona");
  });
});
```

Run: `npm --prefix web/blueprint run test -- QuestionCard`
Expected: PASS.

- [ ] **Step 3: `BriefReviewPanel.tsx`**

Create `web/blueprint/src/pages/compose/BriefReviewPanel.tsx`:

```tsx
import { useState } from "react";

export function BriefReviewPanel({
  brief, onDecision,
}: {
  brief: { request_id: string; yaml: string };
  onDecision: (request_id: string, approved: boolean, yaml: string) => void;
}) {
  const [yaml, setYaml] = useState(brief.yaml);
  return (
    <div className="rounded-xl border border-sky-500/50 bg-slate-900 p-5 shadow-xl" role="dialog" aria-label="Brief review">
      <p className="text-sm text-sky-300">Here's what I understood — edit anything, then approve.</p>
      <textarea className="mt-2 h-64 w-full rounded-md bg-slate-950 p-3 font-mono text-xs text-slate-100"
        value={yaml} onChange={(e) => setYaml(e.target.value)} aria-label="Brief YAML" />
      <div className="mt-3 flex justify-end gap-2">
        <button className="rounded-md border border-slate-600 px-3 py-1.5 text-sm hover:bg-slate-800"
          onClick={() => onDecision(brief.request_id, false, yaml)}>Revise</button>
        <button className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium"
          onClick={() => onDecision(brief.request_id, true, yaml)}>Approve &amp; compose</button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: `ThoughtStream.tsx`, `PlanChecklist.tsx`, `ActivityTimeline.tsx`**

Create `web/blueprint/src/pages/compose/ThoughtStream.tsx`:

```tsx
export function ThoughtStream({ text }: { text: string }) {
  return (
    <div className="h-full overflow-auto rounded-lg border border-slate-800 bg-slate-950/60 p-3">
      <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">Thinking</p>
      <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-slate-400">{text || "…"}</pre>
    </div>
  );
}
```

Create `web/blueprint/src/pages/compose/PlanChecklist.tsx`:

```tsx
import { Check, Loader2, Circle } from "lucide-react";

export function PlanChecklist({ plan }: { plan: { title: string; status: string }[] }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
      <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">Plan</p>
      <ul className="space-y-1.5">
        {plan.map((p, i) => (
          <li key={i} className="flex items-center gap-2 text-sm text-slate-300">
            {p.status === "done" ? <Check size={14} className="text-emerald-400" />
              : p.status === "in_progress" ? <Loader2 size={14} className="animate-spin text-sky-400" />
              : <Circle size={14} className="text-slate-600" />}
            {p.title}
          </li>
        ))}
      </ul>
    </div>
  );
}
```

Create `web/blueprint/src/pages/compose/ActivityTimeline.tsx`:

```tsx
import { ToolCallCard } from "./ToolCallCard";
import type { ToolItem } from "./reducer";

export function ActivityTimeline({ narration, tools }: { narration: string; tools: ToolItem[] }) {
  return (
    <div className="flex h-full flex-col gap-3 overflow-auto">
      {narration && <p className="text-base font-medium text-slate-100">{narration}</p>}
      {tools.map((t) => <ToolCallCard key={t.id} tool={t} />)}
    </div>
  );
}
```

- [ ] **Step 5: `IgniteButton.tsx`**

Create `web/blueprint/src/pages/compose/IgniteButton.tsx`:

```tsx
import { useState } from "react";
import { Rocket } from "lucide-react";
import { pollComposition } from "./api";

export function IgniteButton({
  done, onIgnite,
}: {
  done: { workflow_type: string; display_name: string };
  onIgnite: () => Promise<void>;
}) {
  const [phase, setPhase] = useState<"idle" | "rearming" | "live">("idle");
  async function go() {
    setPhase("rearming");
    await onIgnite();
    const live = await pollComposition(done.workflow_type);
    setPhase("live");
    if (live) {
      // hand off to the cosmic lens, highlighting the new domain
      window.location.href = `/?view=constellation&highlight=${encodeURIComponent(done.workflow_type)}`;
    }
  }
  if (phase === "rearming")
    return <div className="text-sm text-amber-300">Re-arming the substrate…</div>;
  return (
    <button onClick={go}
      className="flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-3 text-base font-semibold text-white shadow-lg hover:bg-emerald-500">
      <Rocket size={18} /> Ignite “{done.display_name}”
    </button>
  );
}
```

- [ ] **Step 6: Commit**

```bash
git add web/blueprint/src/pages/compose/ThoughtStream.tsx web/blueprint/src/pages/compose/PlanChecklist.tsx web/blueprint/src/pages/compose/ActivityTimeline.tsx web/blueprint/src/pages/compose/ToolCallCard.tsx web/blueprint/src/pages/compose/QuestionCard.tsx web/blueprint/src/pages/compose/BriefReviewPanel.tsx web/blueprint/src/pages/compose/IgniteButton.tsx web/blueprint/src/pages/compose/__tests__/ToolCallCard.test.tsx web/blueprint/src/pages/compose/__tests__/QuestionCard.test.tsx
git commit -m "feat(compose-ui): cockpit presentational components + tests (phase 3)"
```

---

## Task 4: `IntakePanel`, `Cockpit`, `ComposePage` + route

**Files:**
- Create: `IntakePanel.tsx`, `Cockpit.tsx`, `ComposePage.tsx`
- Modify: `web/blueprint/src/App.tsx`

- [ ] **Step 1: `IntakePanel.tsx`**

Create `web/blueprint/src/pages/compose/IntakePanel.tsx`:

```tsx
import { useState } from "react";
import { UploadCloud } from "lucide-react";
import { createSession } from "./api";

export function IntakePanel({ onStarted }: { onStarted: (cid: string) => void }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);

  async function start(input: { text?: string; file?: File }) {
    setBusy(true);
    try { onStarted(await createSession(input)); }
    finally { setBusy(false); }
  }

  return (
    <div className="mx-auto max-w-2xl p-8">
      <h1 className="text-2xl font-semibold text-slate-100">Compose a new domain</h1>
      <p className="mt-1 text-slate-400">Drop a process document, or paste a description. An agent will read it, ask you anything ambiguous, draft a spec for your review, then build it live.</p>

      <label className="mt-6 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-slate-700 p-10 text-slate-400 hover:border-sky-500"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files?.[0]; if (f) void start({ file: f }); }}>
        <UploadCloud size={28} />
        <span>Drop a PDF / docx / transcript here</span>
        <input type="file" className="hidden" accept=".pdf,.docx,.md,.txt"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) void start({ file: f }); }} />
      </label>

      <textarea className="mt-4 h-40 w-full rounded-lg bg-slate-900 p-3 text-sm text-slate-100"
        placeholder="…or paste a process description" value={text} onChange={(e) => setText(e.target.value)} />
      <button className="mt-3 rounded-md bg-sky-600 px-4 py-2 font-medium text-white disabled:opacity-50"
        disabled={busy || !text.trim()} onClick={() => void start({ text })}>Compose</button>
    </div>
  );
}
```

- [ ] **Step 2: `Cockpit.tsx`**

Create `web/blueprint/src/pages/compose/Cockpit.tsx`:

```tsx
import { useComposeStream } from "./useComposeStream";
import { ThoughtStream } from "./ThoughtStream";
import { ActivityTimeline } from "./ActivityTimeline";
import { PlanChecklist } from "./PlanChecklist";
import { QuestionCard } from "./QuestionCard";
import { BriefReviewPanel } from "./BriefReviewPanel";
import { IgniteButton } from "./IgniteButton";

export function Cockpit({ cid }: { cid: string }) {
  const { state, answer, approveBrief, ignite } = useComposeStream(cid);
  return (
    <div className="relative h-screen bg-slate-950 text-slate-100">
      <div className="grid h-full grid-cols-[320px_1fr_280px] gap-3 p-3">
        <ThoughtStream text={state.thoughts} />
        <ActivityTimeline narration={state.narration} tools={state.tools} />
        <PlanChecklist plan={state.plan} />
      </div>

      {(state.question || state.brief || state.done || state.error) && (
        <div className="absolute inset-0 flex items-center justify-center bg-slate-950/60 p-6">
          <div className="w-full max-w-2xl">
            {state.error && <div className="rounded-lg border border-red-500/50 bg-slate-900 p-5 text-red-300">{state.error}</div>}
            {state.question && <QuestionCard question={state.question} onAnswer={answer} />}
            {state.brief && !state.question && <BriefReviewPanel brief={state.brief} onDecision={approveBrief} />}
            {state.done && !state.brief && !state.question &&
              <div className="flex justify-center"><IgniteButton done={state.done} onIgnite={ignite} /></div>}
          </div>
        </div>
      )}

      <div className="absolute left-3 top-3 rounded-full bg-slate-800/80 px-3 py-1 text-xs text-slate-300">stage: {state.stage}</div>
    </div>
  );
}
```

- [ ] **Step 3: `ComposePage.tsx`**

Create `web/blueprint/src/pages/ComposePage.tsx`:

```tsx
import { useState } from "react";
import { IntakePanel } from "./compose/IntakePanel";
import { Cockpit } from "./compose/Cockpit";

export function ComposePage() {
  const [cid, setCid] = useState<string | null>(null);
  return cid ? <Cockpit cid={cid} /> : <IntakePanel onStarted={setCid} />;
}
```

- [ ] **Step 4: Wire the route in `App.tsx`**

Open `web/blueprint/src/App.tsx`. Find where the `?view=` query is resolved to a page (the switch that renders `<EntitiesPage/>` for `entities`, `<FunctionsPage/>` for `functions`, etc.). Add an import and a case:

```tsx
import { ComposePage } from "./pages/ComposePage";
// …in the view switch, alongside the other ?view cases:
if (view === "compose") return <ComposePage />;
```

- [ ] **Step 5: Typecheck + build**

Run: `npm --prefix web/blueprint run build`
Expected: builds clean.

- [ ] **Step 6: Manual check against a fake stream (optional)**

With the Phase-2 backend running on the demo stack, open `http://localhost:5275/?view=compose`, paste a short process, and confirm the cockpit renders thoughts/tools/brief. (Full end-to-end is the Task-6 check.)

- [ ] **Step 7: Commit**

```bash
git add web/blueprint/src/pages/ComposePage.tsx web/blueprint/src/pages/compose/IntakePanel.tsx web/blueprint/src/pages/compose/Cockpit.tsx web/blueprint/src/App.tsx
git commit -m "feat(compose-ui): intake + cockpit + ?view=compose route (phase 3)"
```

---

## Task 5: Ignite — supervised restart

**Files:**
- Create: `scripts/lib/compose-start.sh`
- Create: `scripts/compose-ignite.sh`
- Modify: `scripts/boot-demo.sh`
- Modify: `api/server/routes/compose.py` (add `/ignite`)
- Test: `tests/api/compose/test_ignite_endpoint.py`

- [ ] **Step 1: Shared start lib**

Create `scripts/lib/compose-start.sh`:

```bash
#!/usr/bin/env bash
# Shared launch helpers so boot-demo.sh and compose-ignite.sh start the API +
# Functions host identically and record PIDs for a clean restart.
set -euo pipefail
PIDDIR="${ZAVA_REPO_ROOT:-$PWD}/.compose"
mkdir -p "$PIDDIR"

start_api() {
  ( uv run uvicorn api.server.main:app --port 3101 >>"$PIDDIR/api.log" 2>&1 &
    echo $! >"$PIDDIR/api.pid" )
}

start_func() {
  ( cd "${ZAVA_REPO_ROOT:-$PWD}" && func host start --port 7071 >>"$PIDDIR/func.log" 2>&1 &
    echo $! >"$PIDDIR/func.pid" )
}

stop_pid() {  # $1 = pidfile
  local f="$1"
  [ -f "$f" ] || return 0
  local pid; pid="$(cat "$f")"
  if kill -0 "$pid" 2>/dev/null; then kill "$pid" 2>/dev/null || true; fi
  rm -f "$f"
}
```

- [ ] **Step 2: Ignite script**

Create `scripts/compose-ignite.sh`:

```bash
#!/usr/bin/env bash
# Supervised restart of the Functions host + API so a freshly graduated domain
# goes live. Detached from the API it restarts. Localhost/demo only.
set -euo pipefail
cd "${ZAVA_REPO_ROOT:-$PWD}"
source scripts/lib/compose-start.sh

stop_pid "$PIDDIR/func.pid"
stop_pid "$PIDDIR/api.pid"
sleep 2
start_func
# give the Functions host a moment to bind before the API's ramp loop looks for it
sleep 3
start_api
echo "compose-ignite: restarted func + api"
```

Run: `chmod +x scripts/compose-ignite.sh scripts/lib/compose-start.sh`

- [ ] **Step 3: Make `boot-demo.sh` write PID files**

In `scripts/boot-demo.sh`, near the top (after it sets up the repo root) add:

```bash
source scripts/lib/compose-start.sh
```

Replace the existing bare uvicorn launch line (`uv run uvicorn api.server.main:app --port 3101 &`) with `start_api`, and the Functions-host launch line with `start_func`. (Keep everything else — azurite, mocks, vite — unchanged.)

- [ ] **Step 4: `/ignite` endpoint + test**

Create `tests/api/compose/test_ignite_endpoint.py`:

```python
import pytest
from api.server.services.compose import registry
from api.server.services.compose.session import ComposeSession
from api.server.routes import compose as compose_routes


@pytest.mark.asyncio
async def test_ignite_spawns_supervisor(monkeypatch):
    registry.reset()
    registry.register(ComposeSession("cid"))
    calls = {}
    def fake_popen(args, **kw):
        calls["args"] = args
        class P: pass
        return P()
    monkeypatch.setattr(compose_routes.subprocess, "Popen", fake_popen)
    res = await compose_routes.ignite("cid")
    assert res["ok"] is True
    assert "compose-ignite.sh" in " ".join(calls["args"])
```

Add to `api/server/routes/compose.py`:

```python
import subprocess
from api.shared import compose_config


@router.post("/api/compose/{cid}/ignite")
async def ignite(cid: str):
    session = registry.get(cid)
    if session is None:
        return {"ok": False, "error": "not found"}
    session.emit({"type": "stage", "stage": "ready", "label": "Igniting — re-arming the substrate"})
    script = str(compose_config.repo_root() / "scripts" / "compose-ignite.sh")
    # Detached so it survives the API restart it performs.
    subprocess.Popen(
        ["bash", script],
        cwd=str(compose_config.repo_root()),
        start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return {"ok": True}
```

Run: `uv run pytest tests/api/compose/test_ignite_endpoint.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/compose-start.sh scripts/compose-ignite.sh scripts/boot-demo.sh api/server/routes/compose.py tests/api/compose/test_ignite_endpoint.py
git commit -m "feat(compose): Ignite supervised restart + /ignite endpoint (phase 3)"
```

---

## Task 6: Phase-3 exit check (full end-to-end, manual)

- [ ] **Step 1: Frontend unit sweep**

Run: `npm --prefix web/blueprint run test -- compose`
Expected: reducer + component tests green.

- [ ] **Step 2: Backend sweep**

Run: `uv run pytest tests/api/compose/ -q`
Expected: green (real E2E skipped).

- [ ] **Step 3: Full demo dry-run (manual, throwaway checkout)**

  1. `bash scripts/boot-demo.sh` (writes PID files; API :3101, func :7071, blueprint :5275).
  2. Open `http://localhost:5275/?view=compose`.
  3. Drop a short capex process doc with one deliberate ambiguity.
  4. Watch: thought-stream + tool timeline populate; a question card fires; the brief panel appears; approve it; graduate.sh streams in an execute card; `done` arrives.
  5. Click **Ignite** → "re-arming" → the page hands off to `?view=constellation&highlight=<wt>` and the new domain's planet is present.
  6. Confirm: `curl -s localhost:3101/api/blueprint/composition | grep <workflow_type>` returns the new domain.

- [ ] **Step 4: Confirm Phase-3 done-criteria**

  - `?view=compose` renders intake → cockpit.
  - SSE events drive thoughts/tools/plan; question + brief overlays resolve via POST.
  - Ignite restarts the stack and the new domain appears in the cosmic lens.

---

## Self-Review (against the spec)

- **Coverage:** cockpit acts + event→visual mapping §5.1/§5.2 ✓ T1/T3/T4; components §5.3 ✓ T3/T4; SSE client §5.4 ✓ T2; Ignite/restart §4.7 ✓ T5; lens handoff §5.2 ✓ IgniteButton. Voice (§10) correctly out of scope.
- **Placeholder scan:** none — every component + script + endpoint is complete code.
- **Type consistency:** `CockpitState`/`ComposeEvent`/`ToolItem` shapes match the reducer and every component prop; `useComposeStream` returns `{ state, answer, approveBrief, ignite }` consumed exactly by `Cockpit`; event `type` strings match Phase-2's SSE emitter (`stage`/`thought`/`narration`/`tool`/`plan`/`question`/`brief`/`done`/`error`) plus the UI-only `question_cleared`/`brief_cleared`.

---

## Feature complete

With Phases 1–3 merged, the Visual Domain Composer is a genuinely usable, localhost-only self-service tool: drop a document → a real agent composes a new Zava domain with live thinking + HITL → Ignite → it's born in the cosmic lens. Follow-ups (design §10): voice input, true hot-reload (no restart), and a compose-history gallery.
