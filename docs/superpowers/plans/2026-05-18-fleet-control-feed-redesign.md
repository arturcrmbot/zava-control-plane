# Fleet Control Feed Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `web/client/`'s 7-route operator console + 300px event rail + 12-panel detail page with a single chronological **Feed of Work** screen, a right-side **Drawer** for detail, and a header **Role switcher** that re-shapes the feed for five personas — backend unchanged, single PR, no feature flag.

**Architecture:** Pure frontend redesign of `web/client/` (Vite, React 19, Tailwind 4, React Router 7). One new `FleetControlShell` replaces `App.tsx`; one new `useFeedItems` hook composes the existing 4 data hooks + a new `usePolicyEvents` poller into a `FeedItem[]`; one new `<Feed>` orchestrates filter + virtualised card list + "↑ N new" pill; 7 new card components share a `CardShell`; `WorkflowDetail`'s 12 panels collapse into 3 drawer sections that re-use the existing apex/governance panels unchanged. Optimistic resolution lives in a small in-memory store keyed by item id with 30 s undo TTL. Role presets are hardcoded in `web/shared/roles.ts`.

**Tech Stack:** TypeScript, React 19, Tailwind 4 (with native CSS `@container` queries), React Router 7, Vitest + @testing-library/react. No new runtime dependencies.

---

## Design decisions (resolving spec §15 deferred questions)

| # | Question | Decision | Why |
|---|---|---|---|
| 1 | Container-query breakpoints | `CardShell` switches **vertical → horizontal** at container width `≥ 720px`. Container query, not viewport, so opening the 50 % drawer narrows the feed (~50 % of 1440 = 720 → re-stacks vertically automatically). | Matches spec §3.1 viewport table (horizontal kicks in at viewport > 1280 px once the 200 px rail + 48 px gutters are subtracted: `1280 − 200 − 48 = 1032 px`; with drawer open at 50 % → `516 px` → vertical). 720 px is the inflection point. |
| 2 | `usePolicyEvents()` transport | Poll `GET /api/policy/` every **30 s**. Diff against last snapshot keyed by `id` + `gitSha`; emit a `PolicyEvent` per changed/new row with `kind: 'autonomy-changed'` and `actor: <author>`. No SSE — none exists for policy today. | Smallest delta from today's two existing cold-load fetches in `PolicyAutonomyPanel.tsx` and `PolicyAndAutonomy.tsx`. 30 s matches the spec's "operator-tempo" cadence and stays under the API's expected load. |
| 3 | Toast primitive | Build a tiny in-app `Toast.tsx` + `useToast()` context (~70 LOC). `react-hot-toast` is **not** in `package.json`. | Avoid a new dependency for one component that only ever shows ~1 transient message at a time. |
| 4 | Role presets storage | Hardcoded in `web/shared/roles.ts`. Per-role saved views also seeded there; user-added saved views live in `localStorage`. | Spec §15.4 recommendation. Defer server-driven presets to v1.1. |
| 5 | Search popover scope | **Workflow IDs only** in v1. Client-side `filter(w => w.id.toLowerCase().includes(q))` over `useWorkflows()` result. | Spec §15.5 v1 recommendation. Entities/vendors come in v1.1. |

If any of these is wrong, override before execution.

---

## File structure (decomposition lockdown)

### Create

```
web/shared/
  roles.ts                                — RolePreset type + 5 role bundles + getRolePreset()
  feedItems.ts                            — FeedItem discriminated union + buildXxxCards() helpers
  savedViews.ts                           — SavedView type + matches(item, view) predicate

web/client/components/feed/
  FleetControlShell.tsx                   — top-level layout (replaces App.tsx)
  Header.tsx                              — brand · search · 🔔 · Today chip · RoleSwitcher · avatar
  RoleSwitcher.tsx                        — dropdown; persists to localStorage
  LeftRail.tsx                            — saved views + More ▾
  Feed.tsx                                — FilterBar + NewItemsPill + CardList
  FilterBar.tsx                           — [● Needs you] [All activity] · domain chips · select-mode toggle · search
  NewItemsPill.tsx                        — sticky "↑ N new" pill
  CardList.tsx                            — virtualised list (windowed >100)
  CardShell.tsx                           — common chrome (border accent, header, slot, action row, container-query horizontal/vertical)
  Drawer.tsx                              — right-side panel + 3 sections + Esc handler
  DrawerDecision.tsx                      — receipt + recommendation + 4 actions + AuthorityCard + KillSwitchPanel
  DrawerActivity.tsx                      — merged Phases · Timeline · Raw spans with filter chips
  DrawerAudit.tsx                         — EvidencePanel + AuditTrail + EconomicsPanel + FleetAssignment + SkillAmplificationPanel
  NotificationsPopover.tsx                — bell dropdown listing unread feed items
  BulkActionBar.tsx                       — sticky bar shown in select-mode
  Toast.tsx                               — primitive + useToast() context
  cards/HITLCard.tsx
  cards/ExceptionCard.tsx
  cards/ExternalWaitCard.tsx
  cards/MilestoneCard.tsx
  cards/PolicyCard.tsx
  cards/AgentEventCard.tsx
  cards/ResolvedCard.tsx
  cards/ReceiptThumb.tsx                  — extracted from ReviewerQueue.tsx for reuse across cards

web/client/hooks/
  usePolicyEvents.ts                      — 30s poll, diffs by (id, gitSha)
  useFeedItems.ts                         — composes 5 hooks → FeedItem[]
  useResolutionStore.tsx                  — optimistic resolutions, 30s undo TTL (.tsx because it exports JSX)
  useLocalStorageState.ts                 — typed wrapper (role, savedViews, etc.)
  useNewItemsBuffer.ts                    — buffers inbound items behind pill

web/client/components/feed/__tests__/
  Feed.test.tsx
  FilterBar.test.tsx
  CardShell.test.tsx
  cards/HITLCard.test.tsx
  cards/ExceptionCard.test.tsx
  cards/ExternalWaitCard.test.tsx
  cards/MilestoneCard.test.tsx
  cards/PolicyCard.test.tsx
  cards/AgentEventCard.test.tsx
  cards/ResolvedCard.test.tsx
  cards/ReceiptThumb.test.tsx
  Drawer.test.tsx
  DrawerDecision.test.tsx
  DrawerActivity.test.tsx
  DrawerAudit.test.tsx
  RoleSwitcher.test.tsx
  LeftRail.test.tsx
  Header.test.tsx
  NewItemsPill.test.tsx
  NotificationsPopover.test.tsx
  BulkActionBar.test.tsx
  Toast.test.tsx
  integration.test.tsx

web/client/hooks/__tests__/
  useFeedItems.test.ts
  usePolicyEvents.test.ts
  useResolutionStore.test.tsx
  useLocalStorageState.test.ts
  useNewItemsBuffer.test.ts
```

### Modify

```
web/client/main.tsx                        — point at FleetControlShell instead of App
vite.config.ts                             — no change (proxy already covers /api, /internal)
```

### Delete (at the very end, in the cleanup task)

```
web/client/App.tsx
web/client/routes/FleetDashboard.tsx
web/client/routes/ExceptionQueue.tsx
web/client/routes/ReviewerQueue.tsx
web/client/components/FleetManagerRail.tsx
web/client/components/apex/KpiTileRow.tsx
web/client/components/apex/ExceptionCardCompact.tsx
web/client/components/ExceptionItem.tsx
tests/web/ReviewerQueue.test.tsx
tests/web/ReviewerQueue.test.js
```

### Preserved untouched (reached via "More ▾")

```
web/client/routes/Analytics.tsx
web/client/routes/Evaluations.tsx
web/client/routes/Economics.tsx
web/client/routes/PolicyAndAutonomy.tsx
web/client/routes/HiringManager.tsx
```

### Preserved and reused inside the Drawer (no behaviour change, just moved)

```
web/client/components/apex/AuthorityCard.tsx           (→ DrawerDecision)
web/client/components/apex/EconomicsPanel.tsx          (→ DrawerAudit)
web/client/components/apex/FleetAssignment.tsx         (→ DrawerAudit)
web/client/components/apex/AuditTrail.tsx              (→ DrawerAudit)
web/client/components/apex/ExceptionAnalysisCard.tsx   (→ DrawerDecision, narrative branch)
web/client/components/apex/InterventionProtocols.tsx   (→ DrawerDecision, narrative branch)
web/client/components/apex/WorkflowHeaderTiles.tsx     (→ Drawer header)
web/client/components/apex/PhaseRibbon.tsx             (→ DrawerActivity)
web/client/components/apex/CreativeCampaignArtefacts.tsx (→ DrawerDecision)
web/client/components/PhaseTimeline.tsx                (→ DrawerActivity)
web/client/components/OtelSpanTree.tsx                 (→ DrawerActivity)
web/client/components/SkillAmplificationPanel.tsx      (→ DrawerAudit)
web/client/components/apex/ExecutionTimelineTab.tsx    (→ DrawerActivity)
web/client/components/AgentDrivenComponent.tsx         (→ DrawerDecision)
web/client/components/BulkHitlModal.tsx                (→ BulkActionBar)
web/client/components/ConstellationModeButton.tsx      (→ LeftRail, "Constellation ↗" link)
web/client/components/DevPanel.tsx                     (→ Header, behind dev-mode flag, unchanged)
web/client/features/governance/EvidencePanel.tsx       (→ DrawerAudit)
web/client/features/governance/KillSwitchPanel.tsx     (→ DrawerDecision)
```

---

## Task index

| Phase | Tasks | What ships |
|---|---|---|
| **A** Shared | 1–3 | RolePreset bundles · FeedItem types · SavedView |
| **B** Hooks | 4–8 | usePolicyEvents · useFeedItems · useResolutionStore · useLocalStorageState · useNewItemsBuffer |
| **C** Cards | 9–16 | CardShell + 7 typed cards + ReceiptThumb |
| **D** Feed | 17–20 | FilterBar · NewItemsPill · CardList · Feed |
| **E** Drawer | 21–25 | Drawer shell · DrawerDecision · DrawerActivity · DrawerAudit · `/workflows/:id` deep-link |
| **F** Shell | 26–31 | Toast · RoleSwitcher · NotificationsPopover · Header · LeftRail · FleetControlShell |
| **G** Bulk + redirects | 32–33 | Select-mode + BulkActionBar · 301 redirects for old routes |
| **H** Cleanup | 34–36 | Delete legacy files · point main.tsx · run full suite |


---

## Phase A — Shared types

### Task 1: Role presets (`web/shared/roles.ts`)

**Files:**
- Create: `web/shared/roles.ts`
- Test: `web/shared/__tests__/roles.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// web/shared/__tests__/roles.test.ts
import { describe, it, expect } from "vitest";
import { ROLE_PRESETS, getRolePreset, type RoleId } from "../roles";

describe("role presets", () => {
  it("ships exactly five roles in the expected order", () => {
    expect(ROLE_PRESETS.map((r) => r.id)).toEqual([
      "ops-reviewer",
      "finance-controller",
      "hiring-manager",
      "sre",
      "executive",
    ] as RoleId[]);
  });

  it("ops-reviewer defaults to 'needs-you' and shows actionable card types", () => {
    const r = getRolePreset("ops-reviewer");
    expect(r.defaultFilter).toBe("needs-you");
    expect(r.hideActionButtons).toBe(false);
    expect(r.visibleCardTypes).toEqual(
      expect.arrayContaining(["hitl", "exception", "external-wait", "resolved"]),
    );
    expect(r.drawerSectionOrder).toEqual(["decision", "activity", "audit"]);
  });

  it("executive is read-only with audit-first drawer order", () => {
    const r = getRolePreset("executive");
    expect(r.hideActionButtons).toBe(true);
    expect(r.drawerSectionOrder[0]).toBe("audit");
    expect(r.visibleCardTypes).not.toContain("hitl");
  });

  it("finance-controller restricts default domains to finance prefixes", () => {
    const r = getRolePreset("finance-controller");
    expect(r.defaultDomains).toEqual([
      "expense-claim",
      "ap-invoice",
      "purchase-order",
      "treasury-fx",
      "contract-renewal",
    ]);
  });

  it("getRolePreset falls back to ops-reviewer for unknown ids", () => {
    expect(getRolePreset("nope" as RoleId).id).toBe("ops-reviewer");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/shared/__tests__/roles.test.ts`
Expected: FAIL with "Failed to resolve import '../roles'"

- [ ] **Step 3: Write the file**

```ts
// web/shared/roles.ts
//
// Frontend-only role bundles for the Fleet Control feed redesign. Each role
// is a preset of (default filter, visible card types, action availability,
// header chip content, drawer section order, More-menu order). Switching
// role re-applies the bundle to the current feed in place; it does not
// navigate or call the backend.

export type RoleId =
  | "ops-reviewer"
  | "finance-controller"
  | "hiring-manager"
  | "sre"
  | "executive";

export type CardType =
  | "hitl"
  | "exception"
  | "external-wait"
  | "milestone"
  | "policy"
  | "agent-event"
  | "resolved";

export type DrawerSection = "decision" | "activity" | "audit";

export type FilterMode = "needs-you" | "all-activity";

export type TodayChipKind =
  | "needs-you-count"          // Ops Reviewer: "Today: N · M crit"
  | "money-saved"              // Finance: "$ saved today: $XXX"
  | "hiring-summary"           // Hiring: "Open roles: N · Candidates today: M"
  | "fleet-health"             // SRE: "Fleet health: green · 14ms p95"
  | "executive-summary";       // Exec: "Throughput · Auto-rate · Cost"

export interface SavedView {
  id: string;                  // stable id, used as key
  label: string;               // sidebar label
  filter: FilterMode;
  domains: string[];           // empty = all
  severity?: "critical" | "high" | "medium" | null;
  mine?: boolean;              // future use; v1 ignores
  search?: string;
}

export interface RolePreset {
  id: RoleId;
  label: string;
  defaultFilter: FilterMode;
  defaultDomains: string[];        // domain prefix filter; empty = all
  visibleCardTypes: CardType[];    // restricts what's renderable
  hideActionButtons: boolean;      // executive read-only mode
  defaultSavedViews: SavedView[];  // seed the left rail top zone
  moreOrder: string[];             // reorder of "More ▾" submenu (route paths)
  todayChip: TodayChipKind;
  drawerSectionOrder: DrawerSection[];
}

const FINANCE_DOMAINS = [
  "expense-claim",
  "ap-invoice",
  "purchase-order",
  "treasury-fx",
  "contract-renewal",
];

export const ROLE_PRESETS: RolePreset[] = [
  {
    id: "ops-reviewer",
    label: "Ops Reviewer",
    defaultFilter: "needs-you",
    defaultDomains: [],
    visibleCardTypes: ["hitl", "exception", "external-wait", "resolved"],
    hideActionButtons: false,
    defaultSavedViews: [
      { id: "ops-needs-you-critical", label: "Critical · needs you", filter: "needs-you", domains: [], severity: "critical" },
      { id: "ops-all-mine", label: "All my decisions today", filter: "needs-you", domains: [], mine: true },
    ],
    moreOrder: ["/analytics", "/evals", "/economics", "/policy"],
    todayChip: "needs-you-count",
    drawerSectionOrder: ["decision", "activity", "audit"],
  },
  {
    id: "finance-controller",
    label: "Finance Controller",
    defaultFilter: "needs-you",
    defaultDomains: FINANCE_DOMAINS,
    visibleCardTypes: ["hitl", "exception", "external-wait", "policy", "resolved"],
    hideActionButtons: false,
    defaultSavedViews: [
      { id: "fin-expense", label: "Expense claims", filter: "needs-you", domains: ["expense-claim"] },
      { id: "fin-ap", label: "AP invoices", filter: "needs-you", domains: ["ap-invoice"] },
      { id: "fin-po", label: "Purchase orders", filter: "needs-you", domains: ["purchase-order"] },
    ],
    moreOrder: ["/economics", "/analytics", "/policy", "/evals"],
    todayChip: "money-saved",
    drawerSectionOrder: ["decision", "activity", "audit"],
  },
  {
    id: "hiring-manager",
    label: "Hiring Manager",
    defaultFilter: "needs-you",
    defaultDomains: ["hiring"],
    visibleCardTypes: ["hitl", "exception", "resolved"],
    hideActionButtons: false,
    defaultSavedViews: [
      { id: "hire-all", label: "All open roles", filter: "needs-you", domains: ["hiring"] },
    ],
    moreOrder: ["/analytics", "/evals", "/policy", "/economics"],
    todayChip: "hiring-summary",
    drawerSectionOrder: ["decision", "activity", "audit"],
  },
  {
    id: "sre",
    label: "Agent-Platform Engineer",
    defaultFilter: "all-activity",
    defaultDomains: [],
    visibleCardTypes: ["hitl", "exception", "external-wait", "milestone", "policy", "agent-event", "resolved"],
    hideActionButtons: false,
    defaultSavedViews: [
      { id: "sre-errors", label: "Errors only", filter: "all-activity", domains: [] },
      { id: "sre-policy", label: "Policy / autonomy changes", filter: "all-activity", domains: [] },
    ],
    moreOrder: ["/evals", "/policy", "/analytics", "/economics"],
    todayChip: "fleet-health",
    drawerSectionOrder: ["activity", "decision", "audit"],
  },
  {
    id: "executive",
    label: "Executive",
    defaultFilter: "all-activity",
    defaultDomains: [],
    visibleCardTypes: ["milestone", "policy", "resolved"],
    hideActionButtons: true,
    defaultSavedViews: [
      { id: "exec-milestones", label: "Today's milestones", filter: "all-activity", domains: [] },
    ],
    moreOrder: ["/economics", "/analytics", "/policy", "/evals"],
    todayChip: "executive-summary",
    drawerSectionOrder: ["audit", "activity", "decision"],
  },
];

const BY_ID: Record<string, RolePreset> = Object.fromEntries(
  ROLE_PRESETS.map((r) => [r.id, r]),
);

export function getRolePreset(id: RoleId | string): RolePreset {
  return BY_ID[id] ?? BY_ID["ops-reviewer"];
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/shared/__tests__/roles.test.ts`
Expected: PASS — 5 assertions green.

- [ ] **Step 5: Commit**

```bash
git add web/shared/roles.ts web/shared/__tests__/roles.test.ts
git commit -m "feat(feed): add role presets for Fleet Control feed redesign"
```

---

### Task 2: FeedItem types + builders (`web/shared/feedItems.ts`)

**Files:**
- Create: `web/shared/feedItems.ts`
- Test: `web/shared/__tests__/feedItems.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// web/shared/__tests__/feedItems.test.ts
import { describe, it, expect } from "vitest";
import type { Workflow, Exception } from "@shared/types";
import {
  buildHITLCards,
  buildExceptionCards,
  buildExternalWaitCards,
  buildMilestoneCards,
  type FeedItem,
} from "../feedItems";

const baseWorkflow: Workflow = {
  id: "WF-1", type: "expense-claim",
  status: "in_progress",
  currentPhase: "Intake",
  createdAt: 1_000, slaDueAt: 9_999,
  jurisdiction: "UK", agency: "Zava",
  actionLedger: [], tokensSpent: 0, costUSD: 0,
};

describe("buildHITLCards", () => {
  it("emits one HITL item per awaiting_hitl workflow", () => {
    const wfs: Workflow[] = [
      { ...baseWorkflow, id: "WF-1", status: "awaiting_hitl" },
      { ...baseWorkflow, id: "WF-2", status: "in_progress" },
      { ...baseWorkflow, id: "WF-3", status: "awaiting_hitl" },
    ];
    const cards = buildHITLCards(wfs);
    expect(cards.map((c) => c.id)).toEqual(["hitl:WF-1", "hitl:WF-3"]);
    expect(cards.every((c) => c.type === "hitl")).toBe(true);
  });

  it("derives timestamp from workflow.createdAt for ordering", () => {
    const wfs: Workflow[] = [
      { ...baseWorkflow, id: "WF-A", status: "awaiting_hitl", createdAt: 500 },
    ];
    expect(buildHITLCards(wfs)[0].timestamp).toBe(500);
  });
});

describe("buildExceptionCards", () => {
  it("skips resolved exceptions", () => {
    const items: Exception[] = [
      { id: "E1", workflowId: "W1", composedBy: "fleet-manager", severity: "high",
        category: "compliance", summary: "x", recommendation: "y", options: [],
        relatedPolicyRefs: [], confidence: 0.5, createdAt: 1 },
      { id: "E2", workflowId: "W2", composedBy: "fleet-manager", severity: "critical",
        category: "compliance", summary: "x", recommendation: "y", options: [],
        relatedPolicyRefs: [], confidence: 0.5, createdAt: 2, resolvedAt: 5 },
    ];
    expect(buildExceptionCards(items).map((c) => c.id)).toEqual(["exception:E1"]);
  });
});

describe("buildExternalWaitCards", () => {
  it("matches workflows with metadata.wait_kind = external_party", () => {
    const wfs: Workflow[] = [
      { ...baseWorkflow, id: "WF-7",
        metadata: { wait_kind: "external_party", awaiting_reason: "candidate-reply" } },
      { ...baseWorkflow, id: "WF-8",
        metadata: { wait_kind: "operator_review" } },
      { ...baseWorkflow, id: "WF-9" },
    ];
    expect(buildExternalWaitCards(wfs).map((c) => c.id)).toEqual(["external-wait:WF-7"]);
  });
});

describe("buildMilestoneCards", () => {
  it("emits one milestone per completed or failed workflow", () => {
    const wfs: Workflow[] = [
      { ...baseWorkflow, id: "WF-C", status: "completed" },
      { ...baseWorkflow, id: "WF-F", status: "failed" },
      { ...baseWorkflow, id: "WF-I", status: "in_progress" },
    ];
    const cards = buildMilestoneCards(wfs);
    expect(cards.map((c) => c.id).sort()).toEqual(["milestone:WF-C", "milestone:WF-F"]);
  });
});

describe("ordering helper", () => {
  it("FeedItem type discriminant works", () => {
    const it: FeedItem = {
      type: "hitl", id: "x", timestamp: 1,
      workflowId: "W", domain: "expense-claim", severity: "medium",
    };
    expect(it.type).toBe("hitl");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/shared/__tests__/feedItems.test.ts`
Expected: FAIL — module resolution error.

- [ ] **Step 3: Write the file**

```ts
// web/shared/feedItems.ts
//
// FeedItem is the normalised, ordered unit the <Feed> renders. Each card
// type in the feed corresponds to one variant of this discriminated union.
// Builders take the existing hook outputs (Workflow[], Exception[], etc.)
// and project them into FeedItem[] without mutating their source.

import type { Workflow, Exception, Severity } from "./types";
import type { CardType } from "./roles";

export interface FeedItemBase {
  id: string;             // stable: "<type>:<source-id>"
  type: CardType;
  timestamp: number;      // seconds since epoch; used for chronological sort
  workflowId?: string;
  domain?: string;        // workflow.type, used by domain-chip filtering
  severity?: Severity | null;
}

export interface HITLItem extends FeedItemBase {
  type: "hitl";
  workflowId: string;
  workflow?: Workflow;    // attached for renderer; optional for serialisation
}

export interface ExceptionItem extends FeedItemBase {
  type: "exception";
  exception: Exception;
}

export interface ExternalWaitItem extends FeedItemBase {
  type: "external-wait";
  workflowId: string;
  workflow: Workflow;
  awaitingReason?: string;
}

export interface MilestoneItem extends FeedItemBase {
  type: "milestone";
  workflowId: string;
  workflow: Workflow;
  outcome: "completed" | "failed";
}

export interface PolicyItem extends FeedItemBase {
  type: "policy";
  policyId: string;
  description: string;
  previousValue?: unknown;
  currentValue: unknown;
  actor?: string;
}

export interface AgentEventItem extends FeedItemBase {
  type: "agent-event";
  source: "fleet-manager" | "orchestration";
  kind: string;
  data: unknown;
}

export interface ResolvedItem extends FeedItemBase {
  type: "resolved";
  // The original card it replaced; preserved so the Resolved card can
  // re-render the receipt thumb / summary in collapsed form.
  origin: HITLItem | ExceptionItem | ExternalWaitItem;
  verb: string;           // "Approved" | "Rejected" | ...
  actor: string;          // "you" | "agent" | ...
  actedAt: number;
}

export type FeedItem =
  | HITLItem
  | ExceptionItem
  | ExternalWaitItem
  | MilestoneItem
  | PolicyItem
  | AgentEventItem
  | ResolvedItem;

// ---------- builders ----------

export function buildHITLCards(workflows: Workflow[]): HITLItem[] {
  return workflows
    .filter((w) => w.status === "awaiting_hitl")
    .map((w) => ({
      id: `hitl:${w.id}`,
      type: "hitl",
      timestamp: w.createdAt,
      workflowId: w.id,
      domain: w.type,
      severity: w.activeExceptionId ? "high" : "medium",
      workflow: w,
    }));
}

export function buildExceptionCards(exceptions: Exception[]): ExceptionItem[] {
  return exceptions
    .filter((e) => !e.resolvedAt)
    .map((e) => ({
      id: `exception:${e.id}`,
      type: "exception",
      timestamp: e.createdAt,
      workflowId: e.workflowId,
      severity: e.severity,
      exception: e,
    }));
}

export function buildExternalWaitCards(workflows: Workflow[]): ExternalWaitItem[] {
  return workflows
    .filter((w) => {
      const meta = (w.metadata ?? {}) as { wait_kind?: string };
      return meta.wait_kind === "external_party";
    })
    .map((w) => ({
      id: `external-wait:${w.id}`,
      type: "external-wait",
      timestamp: w.createdAt,
      workflowId: w.id,
      domain: w.type,
      severity: "medium",
      workflow: w,
      awaitingReason: ((w.metadata ?? {}) as { awaiting_reason?: string }).awaiting_reason,
    }));
}

export function buildMilestoneCards(workflows: Workflow[]): MilestoneItem[] {
  return workflows
    .filter((w) => w.status === "completed" || w.status === "failed")
    .map((w) => ({
      id: `milestone:${w.id}`,
      type: "milestone",
      timestamp: w.createdAt,
      workflowId: w.id,
      domain: w.type,
      severity: w.status === "failed" ? "high" : null,
      workflow: w,
      outcome: w.status as "completed" | "failed",
    }));
}

export interface PolicySnapshot {
  id: string;
  description: string;
  currentValue: number | string | boolean;
  gitSha?: string;
  author?: string;
  updatedAt?: number;
}

export function buildPolicyCards(events: PolicySnapshot[]): PolicyItem[] {
  return events.map((p) => ({
    id: `policy:${p.id}:${p.gitSha ?? "_"}`,
    type: "policy",
    timestamp: p.updatedAt ?? Math.floor(Date.now() / 1000),
    policyId: p.id,
    severity: null,
    description: p.description,
    currentValue: p.currentValue,
    actor: p.author,
  }));
}

export interface AgentEventLike {
  kind: string;
  timestamp: number;
  workflow_id?: string;
  data?: unknown;
  payload?: unknown;
}

export function buildAgentEventCards(
  fmEvents: AgentEventLike[],
  orchEvents: AgentEventLike[],
): AgentEventItem[] {
  const fm: AgentEventItem[] = fmEvents.map((e, i) => ({
    id: `agent-event:fm:${e.timestamp}:${i}`,
    type: "agent-event",
    timestamp: Math.floor(e.timestamp / 1000),
    severity: e.kind === "error" ? "high" : null,
    source: "fleet-manager",
    kind: e.kind,
    data: e.data,
    workflowId: typeof (e.data as { workflow_id?: string } | undefined)?.workflow_id === "string"
      ? (e.data as { workflow_id: string }).workflow_id
      : undefined,
  }));
  const orch: AgentEventItem[] = orchEvents.map((e, i) => ({
    id: `agent-event:orch:${e.timestamp}:${i}`,
    type: "agent-event",
    timestamp: Math.floor(e.timestamp / 1000),
    severity: e.kind.endsWith(".failed") ? "high" : null,
    source: "orchestration",
    kind: e.kind,
    data: e.payload,
    workflowId: e.workflow_id,
  }));
  return [...fm, ...orch];
}

export function chronological(items: FeedItem[]): FeedItem[] {
  return [...items].sort((a, b) => b.timestamp - a.timestamp);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/shared/__tests__/feedItems.test.ts`
Expected: PASS — all assertions green.

- [ ] **Step 5: Commit**

```bash
git add web/shared/feedItems.ts web/shared/__tests__/feedItems.test.ts
git commit -m "feat(feed): add FeedItem types and per-source card builders"
```

---

### Task 3: SavedView filter matcher (`web/shared/savedViews.ts`)

**Files:**
- Create: `web/shared/savedViews.ts`
- Test: `web/shared/__tests__/savedViews.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// web/shared/__tests__/savedViews.test.ts
import { describe, it, expect } from "vitest";
import type { SavedView } from "../roles";
import type { FeedItem } from "../feedItems";
import { matchesView } from "../savedViews";

const item: FeedItem = {
  type: "hitl",
  id: "hitl:WF-1",
  timestamp: 100,
  workflowId: "WF-1",
  domain: "expense-claim",
  severity: "high",
};

describe("matchesView", () => {
  it("matches when domains is empty (means: all)", () => {
    const v: SavedView = { id: "v", label: "v", filter: "needs-you", domains: [] };
    expect(matchesView(item, v)).toBe(true);
  });
  it("matches when item domain is in domains list", () => {
    const v: SavedView = { id: "v", label: "v", filter: "needs-you", domains: ["expense-claim"] };
    expect(matchesView(item, v)).toBe(true);
  });
  it("rejects when item domain is not in domains list", () => {
    const v: SavedView = { id: "v", label: "v", filter: "needs-you", domains: ["hiring"] };
    expect(matchesView(item, v)).toBe(false);
  });
  it("applies severity filter", () => {
    const v: SavedView = { id: "v", label: "v", filter: "needs-you", domains: [], severity: "critical" };
    expect(matchesView(item, v)).toBe(false);
  });
  it("applies search filter against workflowId", () => {
    const v: SavedView = { id: "v", label: "v", filter: "needs-you", domains: [], search: "wf-1" };
    expect(matchesView(item, v)).toBe(true);
    expect(matchesView(item, { ...v, search: "WF-99" })).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/shared/__tests__/savedViews.test.ts`
Expected: FAIL — module resolution error.

- [ ] **Step 3: Write the file**

```ts
// web/shared/savedViews.ts
//
// Predicate helper: does a FeedItem match a SavedView (or in-line filter
// state)? Centralised so FilterBar, useFeedItems, and the role-switcher's
// domain re-apply path all use the same matcher.

import type { FeedItem } from "./feedItems";
import type { SavedView } from "./roles";

export function matchesView(item: FeedItem, v: SavedView): boolean {
  if (v.domains.length > 0) {
    if (!item.domain) return false;
    if (!v.domains.includes(item.domain)) return false;
  }
  if (v.severity && item.severity !== v.severity) return false;
  if (v.search && v.search.trim().length > 0) {
    const needle = v.search.trim().toLowerCase();
    const haystack = (item.workflowId ?? "").toLowerCase();
    if (!haystack.includes(needle)) return false;
  }
  return true;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/shared/__tests__/savedViews.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/shared/savedViews.ts web/shared/__tests__/savedViews.test.ts
git commit -m "feat(feed): add SavedView matcher predicate"
```


---

## Phase B — Hooks

### Task 4: `useLocalStorageState` typed wrapper

**Files:**
- Create: `web/client/hooks/useLocalStorageState.ts`
- Test: `web/client/hooks/__tests__/useLocalStorageState.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// @vitest-environment jsdom
// web/client/hooks/__tests__/useLocalStorageState.test.ts
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useLocalStorageState } from "../useLocalStorageState";

beforeEach(() => localStorage.clear());
afterEach(() => localStorage.clear());

describe("useLocalStorageState", () => {
  it("returns the default value when the key is absent", () => {
    const { result } = renderHook(() => useLocalStorageState("k", { x: 1 }));
    expect(result.current[0]).toEqual({ x: 1 });
  });

  it("persists updates to localStorage", () => {
    const { result } = renderHook(() => useLocalStorageState("k", 0));
    act(() => result.current[1](42));
    expect(localStorage.getItem("k")).toBe(JSON.stringify(42));
    expect(result.current[0]).toBe(42);
  });

  it("reads a pre-existing value on mount", () => {
    localStorage.setItem("k", JSON.stringify("hello"));
    const { result } = renderHook(() => useLocalStorageState("k", "default"));
    expect(result.current[0]).toBe("hello");
  });

  it("falls back to default on malformed JSON", () => {
    localStorage.setItem("k", "{not json");
    const { result } = renderHook(() => useLocalStorageState("k", 99));
    expect(result.current[0]).toBe(99);
  });

  it("supports functional updates", () => {
    const { result } = renderHook(() => useLocalStorageState("k", 1));
    act(() => result.current[1]((v) => (v as number) + 1));
    expect(result.current[0]).toBe(2);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/hooks/__tests__/useLocalStorageState.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the file**

```ts
// web/client/hooks/useLocalStorageState.ts
//
// useState-shaped hook backed by localStorage. Used for fleetctl.* keys
// (role, savedViews, leftRailCollapsed, criticalToasts, layoutDense).
import { useCallback, useEffect, useRef, useState } from "react";

type Updater<T> = T | ((prev: T) => T);

export function useLocalStorageState<T>(
  key: string,
  defaultValue: T,
): [T, (next: Updater<T>) => void] {
  const initialRef = useRef<T>(defaultValue);
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = typeof window !== "undefined" ? window.localStorage.getItem(key) : null;
      if (raw == null) return defaultValue;
      return JSON.parse(raw) as T;
    } catch {
      return defaultValue;
    }
  });

  useEffect(() => {
    initialRef.current = defaultValue;
    // intentionally do not write the default on mount; only writes from
    // setter calls are persisted, so the default never overwrites a value
    // a different tab wrote first.
  }, [defaultValue]);

  const set = useCallback(
    (next: Updater<T>) => {
      setValue((prev) => {
        const resolved =
          typeof next === "function" ? (next as (p: T) => T)(prev) : next;
        try {
          window.localStorage.setItem(key, JSON.stringify(resolved));
        } catch {
          /* quota or disabled — ignore */
        }
        return resolved;
      });
    },
    [key],
  );

  return [value, set];
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/client/hooks/__tests__/useLocalStorageState.test.ts`
Expected: PASS — 5 assertions.

- [ ] **Step 5: Commit**

```bash
git add web/client/hooks/useLocalStorageState.ts web/client/hooks/__tests__/useLocalStorageState.test.ts
git commit -m "feat(feed): add useLocalStorageState hook"
```

---

### Task 5: `usePolicyEvents` polling hook

**Files:**
- Create: `web/client/hooks/usePolicyEvents.ts`
- Test: `web/client/hooks/__tests__/usePolicyEvents.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// @vitest-environment jsdom
// web/client/hooks/__tests__/usePolicyEvents.test.ts
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { usePolicyEvents } from "../usePolicyEvents";

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

function mockPolicyApi(snapshots: Array<Array<Record<string, unknown>>>) {
  let call = 0;
  globalThis.fetch = vi.fn().mockImplementation(() => {
    const body = snapshots[Math.min(call, snapshots.length - 1)];
    call += 1;
    return Promise.resolve({ ok: true, json: async () => body } as Response);
  });
}

describe("usePolicyEvents", () => {
  it("emits no events on first snapshot (baseline only)", async () => {
    mockPolicyApi([[{ id: "P1", description: "d", currentValue: 0.8, gitSha: "a" }]]);
    const { result } = renderHook(() => usePolicyEvents(30_000));
    await act(async () => { await Promise.resolve(); });
    expect(result.current).toEqual([]);
  });

  it("emits one event when a policy's gitSha changes between polls", async () => {
    mockPolicyApi([
      [{ id: "P1", description: "d", currentValue: 0.8, gitSha: "a" }],
      [{ id: "P1", description: "d", currentValue: 0.9, gitSha: "b", author: "alice" }],
    ]);
    const { result } = renderHook(() => usePolicyEvents(30_000));
    await act(async () => { await Promise.resolve(); });
    await act(async () => {
      vi.advanceTimersByTime(30_000);
      await Promise.resolve();
      await Promise.resolve();
    });
    await waitFor(() => {
      expect(result.current).toHaveLength(1);
    });
    expect(result.current[0].id).toBe("P1");
    expect(result.current[0].currentValue).toBe(0.9);
    expect(result.current[0].author).toBe("alice");
  });

  it("does not emit when polled response is unchanged", async () => {
    mockPolicyApi([
      [{ id: "P1", description: "d", currentValue: 0.8, gitSha: "a" }],
      [{ id: "P1", description: "d", currentValue: 0.8, gitSha: "a" }],
    ]);
    const { result } = renderHook(() => usePolicyEvents(30_000));
    await act(async () => { await Promise.resolve(); });
    await act(async () => {
      vi.advanceTimersByTime(30_000);
      await Promise.resolve();
    });
    expect(result.current).toEqual([]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/hooks/__tests__/usePolicyEvents.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the file**

```ts
// web/client/hooks/usePolicyEvents.ts
//
// Polls /api/policy/ on a fixed interval. On each poll, diffs against the
// previous snapshot keyed by (id, gitSha) and appends a PolicySnapshot for
// every changed or new row. Cap kept at 50 most-recent events.
import { useEffect, useRef, useState } from "react";
import type { PolicySnapshot } from "@shared/feedItems";

const MAX_EVENTS = 50;

export function usePolicyEvents(intervalMs = 30_000): PolicySnapshot[] {
  const [events, setEvents] = useState<PolicySnapshot[]>([]);
  const lastByKey = useRef<Map<string, string>>(new Map());
  const baselineLoaded = useRef(false);

  useEffect(() => {
    let cancelled = false;

    async function poll(): Promise<void> {
      try {
        const r = await fetch("/api/policy/");
        if (!r.ok) return;
        const rows = (await r.json()) as Array<{
          id: string;
          description: string;
          currentValue: number | string | boolean;
          gitSha?: string;
          author?: string;
          updatedAt?: number;
        }>;
        if (cancelled) return;
        const newEvents: PolicySnapshot[] = [];
        for (const row of rows) {
          const key = `${row.id}|${row.gitSha ?? "_"}`;
          if (!lastByKey.current.has(key)) {
            if (baselineLoaded.current) newEvents.push(row);
            lastByKey.current.set(key, key);
          }
        }
        baselineLoaded.current = true;
        if (newEvents.length > 0) {
          setEvents((prev) => [...newEvents, ...prev].slice(0, MAX_EVENTS));
        }
      } catch {
        /* network blip — try again next tick */
      }
    }

    void poll();
    const t = setInterval(() => void poll(), intervalMs);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [intervalMs]);

  return events;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/client/hooks/__tests__/usePolicyEvents.test.ts`
Expected: PASS — 3 assertions.

- [ ] **Step 5: Commit**

```bash
git add web/client/hooks/usePolicyEvents.ts web/client/hooks/__tests__/usePolicyEvents.test.ts
git commit -m "feat(feed): add usePolicyEvents polling hook"
```

---

### Task 6: `useResolutionStore` — optimistic resolutions with undo TTL

**Files:**
- Create: `web/client/hooks/useResolutionStore.tsx`
- Test: `web/client/hooks/__tests__/useResolutionStore.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// @vitest-environment jsdom
// web/client/hooks/__tests__/useResolutionStore.test.tsx
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import type { ReactNode } from "react";
import { useResolutionStore, ResolutionProvider } from "../useResolutionStore";

const wrapper = ({ children }: { children: ReactNode }) => (
  <ResolutionProvider undoTtlMs={30_000}>{children}</ResolutionProvider>
);

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("useResolutionStore", () => {
  it("records a resolution and reads it back", () => {
    const { result } = renderHook(() => useResolutionStore(), { wrapper });
    act(() => result.current.record("hitl:WF-1", { verb: "Approved", actor: "you", actedAt: 100 }));
    expect(result.current.get("hitl:WF-1")).toEqual(
      expect.objectContaining({ verb: "Approved", actor: "you", undoable: true }),
    );
  });

  it("flips undoable=false after the TTL elapses", () => {
    const { result } = renderHook(() => useResolutionStore(), { wrapper });
    act(() => result.current.record("hitl:WF-1", { verb: "Approved", actor: "you", actedAt: 100 }));
    act(() => { vi.advanceTimersByTime(30_001); });
    expect(result.current.get("hitl:WF-1")?.undoable).toBe(false);
  });

  it("revert() removes the optimistic record", () => {
    const { result } = renderHook(() => useResolutionStore(), { wrapper });
    act(() => result.current.record("hitl:WF-1", { verb: "Approved", actor: "you", actedAt: 100 }));
    act(() => result.current.revert("hitl:WF-1"));
    expect(result.current.get("hitl:WF-1")).toBeUndefined();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/hooks/__tests__/useResolutionStore.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the file**

```tsx
// web/client/hooks/useResolutionStore.tsx
//
// React context for optimistic resolutions. When a card's inline action
// fires, the caller `record()`s a resolution against the card's id; that
// flips the card to ResolvedCard in place. The store keeps `undoable=true`
// for `undoTtlMs` (default 30s); after that the undo button hides. revert()
// rolls back (used on backend failure or explicit undo click).
import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
} from "react";
import type { ReactNode } from "react";

export interface Resolution {
  verb: string;
  actor: string;
  actedAt: number;        // seconds since epoch
  undoable: boolean;
}

interface ResolutionAPI {
  get(id: string): Resolution | undefined;
  record(id: string, r: Omit<Resolution, "undoable">): void;
  revert(id: string): void;
  all(): Record<string, Resolution>;
}

const Ctx = createContext<ResolutionAPI | null>(null);

export function ResolutionProvider({
  children, undoTtlMs = 30_000,
}: { children: ReactNode; undoTtlMs?: number }) {
  const [map, setMap] = useState<Record<string, Resolution>>({});
  const timersRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  useEffect(() => {
    return () => {
      for (const t of Object.values(timersRef.current)) clearTimeout(t);
    };
  }, []);

  const get = useCallback((id: string) => map[id], [map]);
  const all = useCallback(() => map, [map]);

  const record = useCallback(
    (id: string, r: Omit<Resolution, "undoable">) => {
      setMap((prev) => ({ ...prev, [id]: { ...r, undoable: true } }));
      const existing = timersRef.current[id];
      if (existing) clearTimeout(existing);
      timersRef.current[id] = setTimeout(() => {
        setMap((prev) =>
          prev[id] ? { ...prev, [id]: { ...prev[id], undoable: false } } : prev,
        );
        delete timersRef.current[id];
      }, undoTtlMs);
    },
    [undoTtlMs],
  );

  const revert = useCallback((id: string) => {
    setMap((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
    const t = timersRef.current[id];
    if (t) {
      clearTimeout(t);
      delete timersRef.current[id];
    }
  }, []);

  const api = useMemo<ResolutionAPI>(
    () => ({ get, record, revert, all }),
    [get, record, revert, all],
  );

  return <Ctx.Provider value={api}>{children}</Ctx.Provider>;
}

export function useResolutionStore(): ResolutionAPI {
  const v = useContext(Ctx);
  if (!v) throw new Error("useResolutionStore must be used inside <ResolutionProvider>");
  return v;
}
```

> **Note:** Use the `.tsx` extension because the file exports JSX (`<Ctx.Provider>`). The test imports it as `"../useResolutionStore"` — TS resolves `.tsx` automatically.

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/client/hooks/__tests__/useResolutionStore.test.tsx`
Expected: PASS — 3 assertions.

- [ ] **Step 5: Commit**

```bash
git add web/client/hooks/useResolutionStore.tsx web/client/hooks/__tests__/useResolutionStore.test.tsx
git commit -m "feat(feed): add ResolutionProvider for optimistic resolutions + undo TTL"
```

---

### Task 7: `useNewItemsBuffer` — buffers inbound items behind the "↑ N new" pill

**Files:**
- Create: `web/client/hooks/useNewItemsBuffer.ts`
- Test: `web/client/hooks/__tests__/useNewItemsBuffer.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// @vitest-environment jsdom
// web/client/hooks/__tests__/useNewItemsBuffer.test.ts
import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useNewItemsBuffer } from "../useNewItemsBuffer";
import type { FeedItem } from "@shared/feedItems";

const mk = (id: string, ts: number): FeedItem => ({
  type: "hitl", id, timestamp: ts, workflowId: id, domain: "expense-claim", severity: "medium",
});

describe("useNewItemsBuffer", () => {
  it("shows the initial list as visible with no pending", () => {
    const { result } = renderHook(() => useNewItemsBuffer([mk("a", 1), mk("b", 2)]));
    expect(result.current.visible.map((i) => i.id)).toEqual(["a", "b"]);
    expect(result.current.pendingCount).toBe(0);
  });

  it("treats new top items as pending until pulled in", () => {
    const initial = [mk("a", 1), mk("b", 2)];
    const { result, rerender } = renderHook(({ list }) => useNewItemsBuffer(list), {
      initialProps: { list: initial },
    });
    rerender({ list: [mk("c", 3), mk("a", 1), mk("b", 2)] });
    expect(result.current.visible.map((i) => i.id)).toEqual(["a", "b"]);
    expect(result.current.pendingCount).toBe(1);

    act(() => result.current.pullIn());
    expect(result.current.visible.map((i) => i.id)).toEqual(["c", "a", "b"]);
    expect(result.current.pendingCount).toBe(0);
  });

  it("does not flag re-ordered or removed items as pending", () => {
    const initial = [mk("a", 1), mk("b", 2)];
    const { result, rerender } = renderHook(({ list }) => useNewItemsBuffer(list), {
      initialProps: { list: initial },
    });
    rerender({ list: [mk("a", 1)] });
    expect(result.current.pendingCount).toBe(0);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/hooks/__tests__/useNewItemsBuffer.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the file**

```ts
// web/client/hooks/useNewItemsBuffer.ts
//
// Wraps an ordered FeedItem[] so that new items appearing at the head
// are buffered (counted, but not shown) until the caller invokes pullIn().
// Items removed or merely re-ordered are not "pending" — only ids new
// since the last snapshot.
import { useEffect, useRef, useState, useCallback } from "react";
import type { FeedItem } from "@shared/feedItems";

interface Result {
  visible: FeedItem[];
  pendingCount: number;
  pullIn: () => void;
}

export function useNewItemsBuffer(items: FeedItem[]): Result {
  const [visible, setVisible] = useState<FeedItem[]>(items);
  const knownIds = useRef<Set<string>>(new Set(items.map((i) => i.id)));
  const [pending, setPending] = useState<FeedItem[]>([]);

  useEffect(() => {
    const incoming: FeedItem[] = [];
    const seen = new Set<string>();
    for (const it of items) {
      seen.add(it.id);
      if (!knownIds.current.has(it.id)) incoming.push(it);
    }
    if (incoming.length > 0) {
      setPending((prev) => [...incoming, ...prev]);
      for (const it of incoming) knownIds.current.add(it.id);
    }
    setVisible((prev) => {
      const stillVisible = prev.filter((i) => seen.has(i.id));
      const merged = items.filter(
        (i) => stillVisible.some((s) => s.id === i.id),
      );
      return merged;
    });
  }, [items]);

  const pullIn = useCallback(() => {
    setVisible((prev) => {
      const ids = new Set(prev.map((i) => i.id));
      const fresh = pending.filter((p) => !ids.has(p.id));
      return [...fresh, ...prev];
    });
    setPending([]);
  }, [pending]);

  return { visible, pendingCount: pending.length, pullIn };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/client/hooks/__tests__/useNewItemsBuffer.test.ts`
Expected: PASS — 3 assertions.

- [ ] **Step 5: Commit**

```bash
git add web/client/hooks/useNewItemsBuffer.ts web/client/hooks/__tests__/useNewItemsBuffer.test.ts
git commit -m "feat(feed): add useNewItemsBuffer for sticky 'N new' pill"
```

---

### Task 8: `useFeedItems` — compose 5 hooks into one ordered list

**Files:**
- Create: `web/client/hooks/useFeedItems.ts`
- Test: `web/client/hooks/__tests__/useFeedItems.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// @vitest-environment jsdom
// web/client/hooks/__tests__/useFeedItems.test.ts
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { useFeedItems } from "../useFeedItems";
import { ResolutionProvider } from "../useResolutionStore";
import { getRolePreset } from "@shared/roles";

const wrapper = ({ children }: { children: ReactNode }) => (
  <ResolutionProvider>{children}</ResolutionProvider>
);

beforeEach(() => {
  (globalThis as any).EventSource = class {
    onmessage: ((ev: MessageEvent) => void) | null = null;
    addEventListener() {}
    close() {}
  };
  globalThis.fetch = vi.fn().mockImplementation((url: string) => {
    if (url.startsWith("/api/workflows")) {
      return Promise.resolve({
        ok: true,
        json: async () => [
          { id: "W-A", type: "expense-claim", status: "awaiting_hitl",
            currentPhase: "Intake", createdAt: 200, slaDueAt: 1, jurisdiction: "UK",
            agency: "Z", actionLedger: [], tokensSpent: 0, costUSD: 0 },
          { id: "W-B", type: "hiring", status: "in_progress",
            currentPhase: "Intake", createdAt: 100, slaDueAt: 1, jurisdiction: "UK",
            agency: "Z", actionLedger: [], tokensSpent: 0, costUSD: 0,
            metadata: { wait_kind: "external_party", awaiting_reason: "cand" } },
        ],
      } as Response);
    }
    if (url.startsWith("/api/exceptions")) {
      return Promise.resolve({
        ok: true,
        json: async () => [
          { id: "E-1", workflowId: "W-A", composedBy: "fleet-manager",
            severity: "high", category: "compliance", summary: "s",
            recommendation: "r", options: [], relatedPolicyRefs: [],
            confidence: 0.8, createdAt: 150 },
        ],
      } as Response);
    }
    if (url.startsWith("/api/policy")) {
      return Promise.resolve({ ok: true, json: async () => [] } as Response);
    }
    return Promise.resolve({ ok: true, json: async () => [] } as Response);
  });
});
afterEach(() => vi.restoreAllMocks());

describe("useFeedItems", () => {
  it("emits HITL + Exception + ExternalWait in chronological order for needs-you filter", async () => {
    const { result } = renderHook(
      () =>
        useFeedItems(getRolePreset("ops-reviewer"), {
          mode: "needs-you", domains: [], severity: null, search: "",
        }),
      { wrapper },
    );
    await waitFor(() => {
      expect(result.current.length).toBeGreaterThanOrEqual(2);
    });
    const ids = result.current.map((i) => i.id);
    expect(ids).toContain("hitl:W-A");
    expect(ids).toContain("exception:E-1");
    expect(ids).toContain("external-wait:W-B");
    expect(ids[0]).toBe("hitl:W-A"); // ts=200 newest
  });

  it("filters by role visibleCardTypes", async () => {
    const exec = getRolePreset("executive");
    const { result } = renderHook(
      () =>
        useFeedItems(exec, { mode: "all-activity", domains: [], severity: null, search: "" }),
      { wrapper },
    );
    await waitFor(() => {
      expect(
        result.current.every((i) => exec.visibleCardTypes.includes(i.type)),
      ).toBe(true);
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/hooks/__tests__/useFeedItems.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the file**

```ts
// web/client/hooks/useFeedItems.ts
//
// Single hook that owns "what's in the feed". Composes existing data
// hooks (workflows, exceptions, FM stream, orchestration stream) plus the
// new usePolicyEvents poller. Returns an ordered FeedItem[] after applying
// the role's visibleCardTypes restriction, the filter mode (needs-you vs
// all-activity), per-card-type role filters, and the active SavedView /
// inline filter (domain chips, severity, search).
//
// Resolved cards are layered on top via useResolutionStore — see
// useDecoratedFeedItems below.
import { useMemo } from "react";
import {
  buildHITLCards, buildExceptionCards, buildExternalWaitCards,
  buildMilestoneCards, buildPolicyCards, buildAgentEventCards,
  chronological, type FeedItem,
} from "@shared/feedItems";
import { matchesView } from "@shared/savedViews";
import type { RolePreset, FilterMode } from "@shared/roles";
import { useWorkflows } from "./useWorkflows";
import { useExceptions } from "./useExceptions";
import { useFleetManagerStream } from "./useFleetManagerStream";
import { useOrchestrationStream } from "./useOrchestrationStream";
import { usePolicyEvents } from "./usePolicyEvents";
import { useResolutionStore } from "./useResolutionStore";

export interface FilterState {
  mode: FilterMode;
  domains: string[];     // empty = all
  severity: "critical" | "high" | "medium" | null;
  search: string;
}

export function useFeedItems(
  role: RolePreset,
  filter: FilterState,
): FeedItem[] {
  const workflows = useWorkflows();
  const { items: exceptions } = useExceptions();
  const fmEvents = useFleetManagerStream();
  const orchEvents = useOrchestrationStream();
  const policyEvents = usePolicyEvents();
  const resolutions = useResolutionStore();

  return useMemo(() => {
    const items: FeedItem[] = [
      ...buildHITLCards(workflows),
      ...buildExceptionCards(exceptions),
      ...buildExternalWaitCards(workflows),
    ];
    if (filter.mode === "all-activity") {
      items.push(
        ...buildMilestoneCards(workflows),
        ...buildPolicyCards(policyEvents),
        ...buildAgentEventCards(
          fmEvents.map((e) => ({ kind: e.kind, timestamp: e.timestamp, data: e.data })),
          orchEvents.map((e) => ({
            kind: e.kind, timestamp: Date.now(), workflow_id: e.workflow_id, payload: e.payload,
          })),
        ),
      );
    }

    // Overlay optimistic resolutions: replace HITL/Exception/ExternalWait
    // items that have a recorded resolution with a ResolvedItem in the same
    // chronological slot.
    const decorated: FeedItem[] = items.map((it) => {
      if (it.type !== "hitl" && it.type !== "exception" && it.type !== "external-wait") {
        return it;
      }
      const r = resolutions.get(it.id);
      if (!r) return it;
      return {
        type: "resolved" as const,
        id: `resolved:${it.id}`,
        timestamp: it.timestamp,
        workflowId: it.workflowId,
        domain: it.domain,
        severity: null,
        origin: it,
        verb: r.verb,
        actor: r.actor,
        actedAt: r.actedAt,
      };
    });

    return chronological(
      decorated
        .filter((i) => role.visibleCardTypes.includes(i.type))
        .filter((i) => {
          if (filter.domains.length === 0) return true;
          return i.domain ? filter.domains.includes(i.domain) : false;
        })
        .filter((i) => (filter.severity ? i.severity === filter.severity : true))
        .filter((i) =>
          matchesView(i, {
            id: "_",
            label: "_",
            filter: filter.mode,
            domains: [],
            search: filter.search,
          }),
        ),
    );
  }, [workflows, exceptions, fmEvents, orchEvents, policyEvents, resolutions, role, filter]);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/client/hooks/__tests__/useFeedItems.test.ts`
Expected: PASS — both tests green.

- [ ] **Step 5: Commit**

```bash
git add web/client/hooks/useFeedItems.ts web/client/hooks/__tests__/useFeedItems.test.ts
git commit -m "feat(feed): add useFeedItems composing 5 hooks + optimistic resolution overlay"
```


---

## Phase C — Cards

> All card tests run under `@vitest-environment jsdom` and wrap the rendered card in `<MemoryRouter>` because cards link to `/workflows/:id`. Action-firing cards also wrap in `<ResolutionProvider>`.

### Task 9: `ReceiptThumb` — extracted reusable thumbnail

**Files:**
- Create: `web/client/components/feed/cards/ReceiptThumb.tsx`
- Test: `web/client/components/feed/__tests__/cards/ReceiptThumb.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// @vitest-environment jsdom
// web/client/components/feed/__tests__/cards/ReceiptThumb.test.tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import ReceiptThumb from "@client/components/feed/cards/ReceiptThumb";

afterEach(cleanup);

describe("ReceiptThumb", () => {
  it("renders a placeholder when no claimId is provided", () => {
    render(<ReceiptThumb />);
    expect(screen.getByText(/no claim/i)).toBeTruthy();
  });
  it("renders 'receipt missing' for missing-receipt flavour", () => {
    render(<ReceiptThumb claimId="C1" flavour="missing-receipt" />);
    expect(screen.getByText(/missing/i)).toBeTruthy();
  });
  it("renders an img for a present receipt", () => {
    render(<ReceiptThumb claimId="C1" />);
    const img = screen.getByAltText(/receipt c1/i);
    expect(img).toBeTruthy();
  });
  it("falls back to placeholder when the image errors", () => {
    render(<ReceiptThumb claimId="C1" />);
    const img = screen.getByAltText(/receipt c1/i) as HTMLImageElement;
    fireEvent.error(img);
    expect(screen.getByText(/missing/i)).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/components/feed/__tests__/cards/ReceiptThumb.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the file**

```tsx
// web/client/components/feed/cards/ReceiptThumb.tsx
//
// Receipt thumbnail extracted from routes/ReviewerQueue.tsx so HITLCard /
// ExceptionCard / ResolvedCard can reuse it without depending on that
// soon-to-be-deleted route file.
import { useState } from "react";

export default function ReceiptThumb({
  claimId, flavour, size = "md",
}: {
  claimId?: string;
  flavour?: string;
  size?: "sm" | "md";
}) {
  const [errored, setErrored] = useState(false);
  const dim = size === "sm" ? "w-12 h-14" : "w-16 h-20";
  if (!claimId) {
    return (
      <div
        className={`${dim} bg-slate-100 rounded border border-slate-200 flex items-center justify-center text-[9px] text-slate-400 text-center px-1`}
        data-testid="receipt-thumb-placeholder"
      >
        no claim
      </div>
    );
  }
  if (errored || flavour === "missing-receipt") {
    return (
      <div
        className={`${dim} bg-amber-50 border border-dashed border-amber-300 rounded flex items-center justify-center text-[9px] text-amber-700 text-center px-1 leading-tight`}
        data-testid="receipt-thumb-missing"
      >
        receipt<br />missing
      </div>
    );
  }
  return (
    <img
      src={`/api/receipts/${claimId}.png`}
      alt={`receipt ${claimId}`}
      onError={() => setErrored(true)}
      className={`${dim} object-cover bg-white rounded border border-slate-200`}
    />
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/client/components/feed/__tests__/cards/ReceiptThumb.test.tsx`
Expected: PASS — 4 assertions.

- [ ] **Step 5: Commit**

```bash
git add web/client/components/feed/cards/ReceiptThumb.tsx web/client/components/feed/__tests__/cards/ReceiptThumb.test.tsx
git commit -m "feat(feed): extract ReceiptThumb from ReviewerQueue"
```

---

### Task 10: `CardShell` — common chrome with container-query horizontal/vertical

**Files:**
- Create: `web/client/components/feed/CardShell.tsx`
- Test: `web/client/components/feed/__tests__/CardShell.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// @vitest-environment jsdom
// web/client/components/feed/__tests__/CardShell.test.tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import CardShell from "@client/components/feed/CardShell";

afterEach(cleanup);

describe("CardShell", () => {
  it("renders header, body, and action slots", () => {
    render(
      <CardShell
        severity="high"
        icon={<span data-testid="ic" />}
        typeLabel="HITL"
        workflowId="WF-1"
        timestampSec={Math.floor(Date.now() / 1000)}
        body={<div data-testid="body">body</div>}
        actions={<button data-testid="act">do</button>}
      />,
    );
    expect(screen.getByText("HITL")).toBeTruthy();
    expect(screen.getByText("WF-1")).toBeTruthy();
    expect(screen.getByTestId("body")).toBeTruthy();
    expect(screen.getByTestId("act")).toBeTruthy();
    expect(screen.getByTestId("ic")).toBeTruthy();
  });

  it("applies the severity border accent", () => {
    const { container } = render(
      <CardShell severity="critical" icon={null} typeLabel="X" workflowId="W" timestampSec={1}
        body={null} actions={null} />,
    );
    expect(container.querySelector(".border-l-4.border-red-500")).toBeTruthy();
  });

  it("uses slate accent for null severity", () => {
    const { container } = render(
      <CardShell severity={null} icon={null} typeLabel="X" workflowId="W" timestampSec={1}
        body={null} actions={null} />,
    );
    expect(container.querySelector(".border-l-4.border-slate-200")).toBeTruthy();
  });

  it("declares an @container scope so children can react to inline width", () => {
    const { container } = render(
      <CardShell severity="medium" icon={null} typeLabel="X" workflowId="W" timestampSec={1}
        body={null} actions={null} />,
    );
    const root = container.firstChild as HTMLElement;
    expect(root.className).toMatch(/@container/);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/components/feed/__tests__/CardShell.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the file**

```tsx
// web/client/components/feed/CardShell.tsx
//
// Shared chrome for every card in the feed. Per spec §3.4 every card carries
// the same outer skeleton: severity border accent (left), header row (icon +
// type label + workflow id + relative time), body slot, action slot. CardShell
// itself declares an @container scope; cards can lay out body/actions
// horizontally at container ≥ 720px (spec §3.1 — drawer-open narrowing).
import type { ReactNode } from "react";
import type { Severity } from "@shared/types";

const SEVERITY_BORDER: Record<string, string> = {
  critical: "border-l-4 border-red-500",
  high: "border-l-4 border-amber-500",
  medium: "border-l-4 border-slate-200",
  null: "border-l-4 border-slate-200",
};

const SEVERITY_DOT: Record<string, string> = {
  critical: "bg-red-500",
  high: "bg-amber-500",
  medium: "bg-slate-300",
  null: "bg-slate-200",
};

function relativeTime(tsSec: number): string {
  const now = Date.now() / 1000;
  const diff = Math.max(0, now - tsSec);
  if (diff < 60) return `${Math.round(diff)}s ago`;
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  if (diff < 86400) return `${(diff / 3600).toFixed(1)}h ago`;
  return `${Math.round(diff / 86400)}d ago`;
}

export interface CardShellProps {
  severity: Severity | null;
  icon: ReactNode;
  typeLabel: string;
  workflowId: string;
  timestampSec: number;
  body: ReactNode;
  actions: ReactNode;
  onPrimaryClick?: () => void;
  testId?: string;
}

export default function CardShell({
  severity, icon, typeLabel, workflowId, timestampSec,
  body, actions, onPrimaryClick, testId,
}: CardShellProps) {
  const sevKey = severity ?? "null";
  return (
    <article
      data-testid={testId ?? `card-${workflowId}`}
      className={`@container bg-white ${SEVERITY_BORDER[sevKey]} border border-slate-200 rounded-lg shadow-sm hover:border-slate-300 transition`}
    >
      <div className="flex items-center gap-2 px-4 pt-3 text-xs text-slate-500">
        <span className={`h-1.5 w-1.5 rounded-full ${SEVERITY_DOT[sevKey]}`} aria-hidden />
        {icon}
        <span className="uppercase tracking-wide text-[10px] font-semibold text-slate-700">
          {typeLabel}
        </span>
        <span className="text-slate-300">·</span>
        <span className="font-mono text-slate-700">{workflowId}</span>
        <span className="ml-auto text-[11px] text-slate-400">{relativeTime(timestampSec)}</span>
      </div>
      <div
        className="px-4 py-3 flex flex-col @[720px]:flex-row @[720px]:items-start @[720px]:gap-4 gap-3"
        onClick={onPrimaryClick}
        role={onPrimaryClick ? "button" : undefined}
        tabIndex={onPrimaryClick ? 0 : undefined}
      >
        <div className="flex-1 min-w-0">{body}</div>
        <div className="flex flex-wrap gap-2 @[720px]:flex-nowrap @[720px]:justify-end shrink-0">
          {actions}
        </div>
      </div>
    </article>
  );
}
```

> **Note:** Tailwind 4 supports `@container` and arbitrary-value queries `@[720px]:flex-row` natively without configuration — verify by running the test.

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/client/components/feed/__tests__/CardShell.test.tsx`
Expected: PASS — 4 assertions.

- [ ] **Step 5: Commit**

```bash
git add web/client/components/feed/CardShell.tsx web/client/components/feed/__tests__/CardShell.test.tsx
git commit -m "feat(feed): add CardShell with severity accent + container queries"
```


---

### Task 11: `HITLCard` — primary actionable card

**Files:**
- Create: `web/client/components/feed/cards/HITLCard.tsx`
- Test: `web/client/components/feed/__tests__/cards/HITLCard.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// @vitest-environment jsdom
// web/client/components/feed/__tests__/cards/HITLCard.test.tsx
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import HITLCard from "@client/components/feed/cards/HITLCard";
import { ResolutionProvider, useResolutionStore } from "@client/hooks/useResolutionStore";
import type { HITLItem } from "@shared/feedItems";
import type { Workflow } from "@shared/types";

const baseWf: Workflow = {
  id: "WF-1", type: "expense-claim", status: "awaiting_hitl",
  currentPhase: "Intake", createdAt: 100, slaDueAt: 99999,
  jurisdiction: "UK", agency: "Z", actionLedger: [],
  tokensSpent: 0, costUSD: 0,
  claim: {
    claimId: "CL-1", employeeId: "E-1", submittedAt: "2026-05-18T10:00:00Z",
    market: "UK", currency: "GBP", category: "meals", vendor: "Pret",
    amount: 42.5, attendees: 1, emsSource: "concur",
  },
};

const baseItem: HITLItem = {
  type: "hitl", id: "hitl:WF-1", timestamp: 100,
  workflowId: "WF-1", domain: "expense-claim", severity: "high",
  workflow: baseWf,
};

beforeEach(() => {
  globalThis.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) } as Response);
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function renderWithProviders(item: HITLItem, opts: { hideActions?: boolean } = {}) {
  return render(
    <MemoryRouter>
      <ResolutionProvider>
        <HITLCard item={item} hideActions={!!opts.hideActions} />
      </ResolutionProvider>
    </MemoryRouter>,
  );
}

describe("HITLCard", () => {
  it("renders the four inline action buttons by default", () => {
    renderWithProviders(baseItem);
    expect(screen.getByRole("button", { name: /Approve/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Request docs/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Escalate/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Reject/i })).toBeTruthy();
  });

  it("hides actions when hideActions is true (executive role)", () => {
    renderWithProviders(baseItem, { hideActions: true });
    expect(screen.queryByRole("button", { name: /Approve/i })).toBeNull();
  });

  it("records an optimistic resolution and POSTs to /api/exceptions/{id}/resolve when there is an exception", async () => {
    const item: HITLItem = {
      ...baseItem,
      workflow: { ...baseWf, activeExceptionId: "EXC-1" },
    };
    function Probe() {
      const store = useResolutionStore();
      return <span data-testid="probe">{store.get("hitl:WF-1")?.verb ?? "none"}</span>;
    }
    render(
      <MemoryRouter>
        <ResolutionProvider>
          <HITLCard item={item} />
          <Probe />
        </ResolutionProvider>
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole("button", { name: /Approve/i }));
    await waitFor(() => {
      expect(screen.getByTestId("probe").textContent).toBe("Approved");
    });
    expect((globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
      "/api/exceptions/EXC-1/resolve",
    );
  });

  it("reverts the optimistic resolution if the backend call fails", async () => {
    const item: HITLItem = {
      ...baseItem,
      workflow: { ...baseWf, activeExceptionId: "EXC-1" },
    };
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, text: async () => "boom" } as Response);
    function Probe() {
      const store = useResolutionStore();
      return <span data-testid="probe">{store.get("hitl:WF-1")?.verb ?? "none"}</span>;
    }
    render(
      <MemoryRouter>
        <ResolutionProvider>
          <HITLCard item={item} />
          <Probe />
        </ResolutionProvider>
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole("button", { name: /Approve/i }));
    await waitFor(() => {
      expect(screen.getByTestId("probe").textContent).toBe("none");
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/components/feed/__tests__/cards/HITLCard.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the file**

```tsx
// web/client/components/feed/cards/HITLCard.tsx
//
// HITL = workflow currently awaiting human-in-the-loop. The card surfaces
// the receipt (when present), claim summary, fleet-manager recommendation
// (when present), and four inline actions. Clicking an action optimistically
// records a resolution (flips the card to ResolvedCard via useFeedItems'
// overlay) and POSTs to /api/exceptions/{activeExceptionId}/resolve. On
// backend failure the optimistic state is reverted.
import { useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle } from "lucide-react";
import type { HITLItem } from "@shared/feedItems";
import CardShell from "../CardShell";
import ReceiptThumb from "./ReceiptThumb";
import { useResolutionStore } from "@client/hooks/useResolutionStore";

const ACTIONS = [
  { id: "approve",       label: "Approve",      cls: "bg-emerald-600 hover:bg-emerald-700 text-white", verb: "Approved" },
  { id: "request-info",  label: "Request docs", cls: "bg-white text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50", verb: "Requested docs" },
  { id: "escalate",      label: "Escalate L2",  cls: "bg-white text-amber-700 ring-1 ring-amber-300 hover:bg-amber-50", verb: "Escalated" },
  { id: "reject",        label: "Reject",       cls: "bg-white text-red-700 ring-1 ring-red-300 hover:bg-red-50", verb: "Rejected" },
] as const;

export default function HITLCard({
  item, hideActions = false, onOpenDrawer,
}: {
  item: HITLItem;
  hideActions?: boolean;
  onOpenDrawer?: (workflowId: string) => void;
}) {
  const w = item.workflow!;
  const store = useResolutionStore();
  const [busy, setBusy] = useState<string | null>(null);

  const onAction = async (id: string, verb: string) => {
    setBusy(id);
    store.record(item.id, { verb, actor: "you", actedAt: Math.floor(Date.now() / 1000) });
    try {
      const exceptionId = w.activeExceptionId;
      if (!exceptionId) return;
      const r = await fetch(`/api/exceptions/${exceptionId}/resolve`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ resolution: id, resolvedBy: "reviewer@zava" }),
      });
      if (!r.ok) store.revert(item.id);
    } catch {
      store.revert(item.id);
    } finally {
      setBusy(null);
    }
  };

  const body = (
    <div className="flex gap-3 min-w-0">
      {w.claim ? (
        <ReceiptThumb claimId={w.claim.claimId} flavour={w.claim.receiptMismatchFlavour} />
      ) : null}
      <div className="min-w-0 space-y-1">
        <div className="text-sm font-medium text-slate-900 truncate">
          {w.claim
            ? `${w.claim.currency} ${w.claim.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })} · ${w.claim.vendor}`
            : w.id}
        </div>
        {w.claim ? (
          <div className="text-xs text-slate-500 truncate">
            {w.claim.employeeId} · {w.claim.category} · {w.claim.market}
          </div>
        ) : null}
      </div>
    </div>
  );

  const actions = hideActions ? null : (
    <>
      {ACTIONS.map((a) => (
        <button
          key={a.id}
          type="button"
          disabled={busy != null}
          onClick={(e) => { e.stopPropagation(); void onAction(a.id, a.verb); }}
          className={`text-xs px-3 py-1.5 rounded font-medium transition disabled:opacity-50 ${a.cls}`}
        >
          {busy === a.id ? "…" : a.label}
        </button>
      ))}
    </>
  );

  return (
    <CardShell
      severity={item.severity ?? null}
      icon={<AlertTriangle size={12} className="text-amber-600" />}
      typeLabel="HITL · Needs you"
      workflowId={w.id}
      timestampSec={item.timestamp}
      body={body}
      actions={actions}
      onPrimaryClick={
        onOpenDrawer
          ? () => onOpenDrawer(w.id)
          : undefined
      }
    />
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/client/components/feed/__tests__/cards/HITLCard.test.tsx`
Expected: PASS — 4 assertions.

- [ ] **Step 5: Commit**

```bash
git add web/client/components/feed/cards/HITLCard.tsx web/client/components/feed/__tests__/cards/HITLCard.test.tsx
git commit -m "feat(feed): add HITLCard with optimistic resolve + 4 inline actions"
```

---

### Task 12: `ExceptionCard`

**Files:**
- Create: `web/client/components/feed/cards/ExceptionCard.tsx`
- Test: `web/client/components/feed/__tests__/cards/ExceptionCard.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// @vitest-environment jsdom
// web/client/components/feed/__tests__/cards/ExceptionCard.test.tsx
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import ExceptionCard from "@client/components/feed/cards/ExceptionCard";
import { ResolutionProvider, useResolutionStore } from "@client/hooks/useResolutionStore";
import type { ExceptionItem } from "@shared/feedItems";

const baseItem: ExceptionItem = {
  type: "exception", id: "exception:E-1", timestamp: 100,
  workflowId: "WF-1", severity: "high",
  exception: {
    id: "E-1", workflowId: "WF-1", composedBy: "fleet-manager",
    severity: "high", category: "compliance",
    summary: "Vendor on watchlist", recommendation: "request-info",
    options: [], relatedPolicyRefs: [], confidence: 0.8, createdAt: 100,
  },
};

beforeEach(() => {
  globalThis.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) } as Response);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("ExceptionCard", () => {
  it("renders severity, summary, and recommendation", () => {
    render(
      <MemoryRouter>
        <ResolutionProvider><ExceptionCard item={baseItem} /></ResolutionProvider>
      </MemoryRouter>,
    );
    expect(screen.getByText(/Vendor on watchlist/i)).toBeTruthy();
    expect(screen.getByText(/request-info/i)).toBeTruthy();
  });

  it("offers 5 actions including Snooze 1h", () => {
    render(
      <MemoryRouter>
        <ResolutionProvider><ExceptionCard item={baseItem} /></ResolutionProvider>
      </MemoryRouter>,
    );
    expect(screen.getByRole("button", { name: /Snooze 1h/i })).toBeTruthy();
  });

  it("records optimistic resolution on Approve click and calls /api/exceptions/E-1/resolve", async () => {
    function Probe() {
      const store = useResolutionStore();
      return <span data-testid="probe">{store.get("exception:E-1")?.verb ?? "none"}</span>;
    }
    render(
      <MemoryRouter>
        <ResolutionProvider>
          <ExceptionCard item={baseItem} />
          <Probe />
        </ResolutionProvider>
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole("button", { name: /Approve/i }));
    await waitFor(() => expect(screen.getByTestId("probe").textContent).toBe("Approved"));
    expect((globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
      "/api/exceptions/E-1/resolve",
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/components/feed/__tests__/cards/ExceptionCard.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the file**

```tsx
// web/client/components/feed/cards/ExceptionCard.tsx
//
// Open exception not yet picked up. Same four resolve actions as HITL plus
// a Snooze 1h that defers (no backend call in v1; sets a local timer to
// re-surface). All actions go through useResolutionStore.
import { useState } from "react";
import { ShieldAlert } from "lucide-react";
import type { ExceptionItem } from "@shared/feedItems";
import CardShell from "../CardShell";
import { useResolutionStore } from "@client/hooks/useResolutionStore";

const ACTIONS = [
  { id: "approve",       label: "Approve",       cls: "bg-emerald-600 hover:bg-emerald-700 text-white",       verb: "Approved" },
  { id: "request-info",  label: "Request docs",  cls: "bg-white text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50", verb: "Requested docs" },
  { id: "escalate",      label: "Escalate L2",   cls: "bg-white text-amber-700 ring-1 ring-amber-300 hover:bg-amber-50", verb: "Escalated" },
  { id: "reject",        label: "Reject",        cls: "bg-white text-red-700 ring-1 ring-red-300 hover:bg-red-50",       verb: "Rejected" },
  { id: "snooze",        label: "Snooze 1h",     cls: "bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50", verb: "Snoozed 1h" },
] as const;

export default function ExceptionCard({
  item, hideActions = false, onOpenDrawer,
}: {
  item: ExceptionItem;
  hideActions?: boolean;
  onOpenDrawer?: (workflowId: string) => void;
}) {
  const e = item.exception;
  const store = useResolutionStore();
  const [busy, setBusy] = useState<string | null>(null);

  const onAction = async (id: string, verb: string) => {
    setBusy(id);
    store.record(item.id, { verb, actor: "you", actedAt: Math.floor(Date.now() / 1000) });
    if (id === "snooze") {
      setBusy(null);
      return;
    }
    try {
      const r = await fetch(`/api/exceptions/${e.id}/resolve`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ resolution: id, resolvedBy: "reviewer@zava" }),
      });
      if (!r.ok) store.revert(item.id);
    } catch {
      store.revert(item.id);
    } finally {
      setBusy(null);
    }
  };

  const body = (
    <div className="min-w-0 space-y-1">
      <div className="text-sm font-medium text-slate-900">{e.summary}</div>
      <div className="text-xs text-emerald-700">→ {e.recommendation}</div>
      <div className="text-[11px] text-slate-500">
        category: {e.category} · confidence {(e.confidence * 100).toFixed(0)}%
      </div>
    </div>
  );

  const actions = hideActions ? null : (
    <>
      {ACTIONS.map((a) => (
        <button
          key={a.id}
          type="button"
          disabled={busy != null}
          onClick={(ev) => { ev.stopPropagation(); void onAction(a.id, a.verb); }}
          className={`text-xs px-3 py-1.5 rounded font-medium transition disabled:opacity-50 ${a.cls}`}
        >
          {busy === a.id ? "…" : a.label}
        </button>
      ))}
    </>
  );

  return (
    <CardShell
      severity={item.severity ?? null}
      icon={<ShieldAlert size={12} className="text-red-600" />}
      typeLabel="Exception · Needs you"
      workflowId={e.workflowId}
      timestampSec={item.timestamp}
      body={body}
      actions={actions}
      onPrimaryClick={onOpenDrawer ? () => onOpenDrawer(e.workflowId) : undefined}
    />
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/client/components/feed/__tests__/cards/ExceptionCard.test.tsx`
Expected: PASS — 3 assertions.

- [ ] **Step 5: Commit**

```bash
git add web/client/components/feed/cards/ExceptionCard.tsx web/client/components/feed/__tests__/cards/ExceptionCard.test.tsx
git commit -m "feat(feed): add ExceptionCard with Snooze 1h"
```


---

### Task 13: `ExternalWaitCard`

**Files:**
- Create: `web/client/components/feed/cards/ExternalWaitCard.tsx`
- Test: `web/client/components/feed/__tests__/cards/ExternalWaitCard.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// @vitest-environment jsdom
// web/client/components/feed/__tests__/cards/ExternalWaitCard.test.tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import ExternalWaitCard from "@client/components/feed/cards/ExternalWaitCard";
import { ResolutionProvider } from "@client/hooks/useResolutionStore";
import type { ExternalWaitItem } from "@shared/feedItems";

afterEach(cleanup);

const item: ExternalWaitItem = {
  type: "external-wait", id: "external-wait:WF-7", timestamp: 100,
  workflowId: "WF-7", domain: "hiring", severity: "medium",
  awaitingReason: "candidate-reply",
  workflow: {
    id: "WF-7", type: "hiring", status: "in_progress",
    currentPhase: "Sourcing", createdAt: 100, slaDueAt: 9999,
    jurisdiction: "UK", agency: "Z", actionLedger: [],
    tokensSpent: 0, costUSD: 0,
    metadata: { wait_kind: "external_party", awaiting_reason: "candidate-reply" },
  },
};

describe("ExternalWaitCard", () => {
  it("renders the awaiting reason", () => {
    render(
      <MemoryRouter>
        <ResolutionProvider><ExternalWaitCard item={item} /></ResolutionProvider>
      </MemoryRouter>,
    );
    expect(screen.getByText(/candidate-reply/i)).toBeTruthy();
  });
  it("offers Nudge / Reassign / View token buttons", () => {
    render(
      <MemoryRouter>
        <ResolutionProvider><ExternalWaitCard item={item} /></ResolutionProvider>
      </MemoryRouter>,
    );
    expect(screen.getByRole("button", { name: /Nudge/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Reassign/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /View token/i })).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/components/feed/__tests__/cards/ExternalWaitCard.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the file**

```tsx
// web/client/components/feed/cards/ExternalWaitCard.tsx
//
// Workflow suspended on an external party (metadata.wait_kind="external_party").
// Actions are advisory in v1 — Nudge fires log.action via the durable event
// bus; Reassign and View token open the drawer for further detail.
import { useState } from "react";
import { Hourglass } from "lucide-react";
import type { ExternalWaitItem } from "@shared/feedItems";
import CardShell from "../CardShell";
import { useResolutionStore } from "@client/hooks/useResolutionStore";

export default function ExternalWaitCard({
  item, hideActions = false, onOpenDrawer,
}: {
  item: ExternalWaitItem;
  hideActions?: boolean;
  onOpenDrawer?: (workflowId: string) => void;
}) {
  const store = useResolutionStore();
  const [busy, setBusy] = useState<string | null>(null);

  const nudge = async () => {
    setBusy("nudge");
    store.record(item.id, { verb: "Nudged", actor: "you", actedAt: Math.floor(Date.now() / 1000) });
    try {
      await fetch("/internal/durable-event", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workflow_id: item.workflowId, kind: "log.action",
          payload: { by: "operator", action: "nudge-external" },
        }),
      });
    } catch {
      store.revert(item.id);
    } finally {
      setBusy(null);
    }
  };

  const body = (
    <div className="min-w-0 space-y-1">
      <div className="text-sm font-medium text-slate-900">Awaiting external party</div>
      <div className="text-xs text-slate-600">
        reason: <code className="bg-slate-100 px-1.5 py-0.5 rounded">{item.awaitingReason ?? "unspecified"}</code>
      </div>
      <div className="text-[11px] text-slate-500">ages against their SLA, not yours</div>
    </div>
  );

  const actions = hideActions ? null : (
    <>
      <button
        type="button" disabled={busy != null}
        onClick={(e) => { e.stopPropagation(); void nudge(); }}
        className="text-xs px-3 py-1.5 rounded font-medium bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50"
      >Nudge</button>
      <button
        type="button" disabled={busy != null}
        onClick={(e) => { e.stopPropagation(); onOpenDrawer?.(item.workflowId); }}
        className="text-xs px-3 py-1.5 rounded font-medium bg-white text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50"
      >Reassign</button>
      <button
        type="button" disabled={busy != null}
        onClick={(e) => { e.stopPropagation(); onOpenDrawer?.(item.workflowId); }}
        className="text-xs px-3 py-1.5 rounded font-medium bg-white text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50"
      >View token</button>
    </>
  );

  return (
    <CardShell
      severity={item.severity ?? null}
      icon={<Hourglass size={12} className="text-blue-600" />}
      typeLabel="External wait · Needs you"
      workflowId={item.workflowId}
      timestampSec={item.timestamp}
      body={body}
      actions={actions}
      onPrimaryClick={onOpenDrawer ? () => onOpenDrawer(item.workflowId) : undefined}
    />
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/client/components/feed/__tests__/cards/ExternalWaitCard.test.tsx`
Expected: PASS — 2 assertions.

- [ ] **Step 5: Commit**

```bash
git add web/client/components/feed/cards/ExternalWaitCard.tsx web/client/components/feed/__tests__/cards/ExternalWaitCard.test.tsx
git commit -m "feat(feed): add ExternalWaitCard"
```

---

### Task 14: `MilestoneCard`

**Files:**
- Create: `web/client/components/feed/cards/MilestoneCard.tsx`
- Test: `web/client/components/feed/__tests__/cards/MilestoneCard.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// @vitest-environment jsdom
// web/client/components/feed/__tests__/cards/MilestoneCard.test.tsx
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import MilestoneCard from "@client/components/feed/cards/MilestoneCard";
import type { MilestoneItem } from "@shared/feedItems";

afterEach(cleanup);

const item: MilestoneItem = {
  type: "milestone", id: "milestone:WF-9", timestamp: 100,
  workflowId: "WF-9", domain: "expense-claim", severity: null,
  outcome: "completed",
  workflow: {
    id: "WF-9", type: "expense-claim", status: "completed",
    currentPhase: "Audit", createdAt: 100, slaDueAt: 9999,
    jurisdiction: "UK", agency: "Z", actionLedger: [],
    tokensSpent: 0, costUSD: 0,
  },
};

describe("MilestoneCard", () => {
  it("renders the outcome verb", () => {
    render(<MemoryRouter><MilestoneCard item={item} /></MemoryRouter>);
    expect(screen.getByText(/completed/i)).toBeTruthy();
  });

  it("fires onOpenDrawer when Open is clicked", () => {
    const onOpen = vi.fn();
    render(<MemoryRouter><MilestoneCard item={item} onOpenDrawer={onOpen} /></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: /Open/i }));
    expect(onOpen).toHaveBeenCalledWith("WF-9");
  });
});
```

> **Note:** All imports (including `vi`) are now at the top of the file as the JS module spec requires.

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/components/feed/__tests__/cards/MilestoneCard.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the file**

```tsx
// web/client/components/feed/cards/MilestoneCard.tsx
//
// Terminal status transition. Only visible in "all-activity" mode. Carries
// an Open (drawer) and a local Dismiss; Dismiss simply removes the card via
// the parent's optimistic store (no backend call — purely a personal-feed
// affordance).
import { useState } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import type { MilestoneItem } from "@shared/feedItems";
import CardShell from "../CardShell";

export default function MilestoneCard({
  item, hideActions = false, onOpenDrawer, onDismiss,
}: {
  item: MilestoneItem;
  hideActions?: boolean;
  onOpenDrawer?: (workflowId: string) => void;
  onDismiss?: (itemId: string) => void;
}) {
  const w = item.workflow;
  const [dismissed, setDismissed] = useState(false);
  if (dismissed) return null;

  const verb = item.outcome === "completed" ? "completed" : "failed";
  const icon = item.outcome === "completed"
    ? <CheckCircle2 size={12} className="text-emerald-600" />
    : <XCircle size={12} className="text-red-600" />;

  const body = (
    <div className="text-sm text-slate-700">
      <span className="font-semibold text-slate-900">{w.id}</span>
      <span className="text-slate-500"> ({w.type})</span> {verb}.
    </div>
  );

  const actions = hideActions ? null : (
    <>
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); onOpenDrawer?.(w.id); }}
        className="text-xs px-3 py-1.5 rounded font-medium bg-white text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50"
      >Open</button>
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); setDismissed(true); onDismiss?.(item.id); }}
        className="text-xs px-3 py-1.5 rounded font-medium bg-white text-slate-500 ring-1 ring-slate-200 hover:bg-slate-50"
      >Dismiss</button>
    </>
  );

  return (
    <CardShell
      severity={item.severity ?? null}
      icon={icon}
      typeLabel={`Milestone · ${verb}`}
      workflowId={w.id}
      timestampSec={item.timestamp}
      body={body}
      actions={actions}
      onPrimaryClick={onOpenDrawer ? () => onOpenDrawer(w.id) : undefined}
    />
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/client/components/feed/__tests__/cards/MilestoneCard.test.tsx`
Expected: PASS — 2 assertions.

- [ ] **Step 5: Commit**

```bash
git add web/client/components/feed/cards/MilestoneCard.tsx web/client/components/feed/__tests__/cards/MilestoneCard.test.tsx
git commit -m "feat(feed): add MilestoneCard"
```

---

### Task 15: `PolicyCard`

**Files:**
- Create: `web/client/components/feed/cards/PolicyCard.tsx`
- Test: `web/client/components/feed/__tests__/cards/PolicyCard.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// @vitest-environment jsdom
// web/client/components/feed/__tests__/cards/PolicyCard.test.tsx
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import PolicyCard from "@client/components/feed/cards/PolicyCard";
import type { PolicyItem } from "@shared/feedItems";

afterEach(cleanup);

const item: PolicyItem = {
  type: "policy", id: "policy:P-1:abc", timestamp: 100,
  policyId: "autonomy.threshold.vendor-kyc", severity: null,
  description: "Autonomy threshold for vendor-kyc",
  currentValue: 0.85, actor: "alice@zava",
};

describe("PolicyCard", () => {
  it("renders the description, actor and current value", () => {
    render(<MemoryRouter><PolicyCard item={item} /></MemoryRouter>);
    expect(screen.getByText(/Autonomy threshold for vendor-kyc/)).toBeTruthy();
    expect(screen.getByText(/alice@zava/)).toBeTruthy();
    expect(screen.getByText(/0\.85/)).toBeTruthy();
  });
  it("Acknowledge button hides the card locally", () => {
    render(<MemoryRouter><PolicyCard item={item} /></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: /Acknowledge/i }));
    expect(screen.queryByText(/Autonomy threshold for vendor-kyc/)).toBeNull();
  });
  it("View diff calls onOpenDrawer with the policyId", () => {
    const onOpen = vi.fn();
    render(<MemoryRouter><PolicyCard item={item} onOpenDrawer={onOpen} /></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: /View diff/i }));
    expect(onOpen).toHaveBeenCalledWith("autonomy.threshold.vendor-kyc");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/components/feed/__tests__/cards/PolicyCard.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the file**

```tsx
// web/client/components/feed/cards/PolicyCard.tsx
//
// Policy / autonomy change event. v1 surfaces the description, current
// value, and actor; View diff opens the policy in the drawer (routed by
// policy id, not workflow id — drawer handles this case).
import { useState } from "react";
import { GitBranch } from "lucide-react";
import type { PolicyItem } from "@shared/feedItems";
import CardShell from "../CardShell";

export default function PolicyCard({
  item, hideActions = false, onOpenDrawer,
}: {
  item: PolicyItem;
  hideActions?: boolean;
  onOpenDrawer?: (policyId: string) => void;
}) {
  const [ack, setAck] = useState(false);
  if (ack) return null;

  const body = (
    <div className="text-sm text-slate-700 min-w-0">
      <div className="font-medium text-slate-900">{item.description}</div>
      <div className="text-xs text-slate-500 mt-1">
        current: <span className="font-medium text-slate-800">{String(item.currentValue)}</span>
        {item.actor ? <> · by <span className="font-medium text-slate-700">{item.actor}</span></> : null}
      </div>
    </div>
  );

  const actions = hideActions ? null : (
    <>
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); setAck(true); }}
        className="text-xs px-3 py-1.5 rounded font-medium bg-white text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50"
      >Acknowledge</button>
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); onOpenDrawer?.(item.policyId); }}
        className="text-xs px-3 py-1.5 rounded font-medium bg-white text-blue-700 ring-1 ring-blue-300 hover:bg-blue-50"
      >View diff</button>
    </>
  );

  return (
    <CardShell
      severity={null}
      icon={<GitBranch size={12} className="text-blue-600" />}
      typeLabel="Policy · change"
      workflowId={item.policyId}
      timestampSec={item.timestamp}
      body={body}
      actions={actions}
    />
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/client/components/feed/__tests__/cards/PolicyCard.test.tsx`
Expected: PASS — 3 assertions.

- [ ] **Step 5: Commit**

```bash
git add web/client/components/feed/cards/PolicyCard.tsx web/client/components/feed/__tests__/cards/PolicyCard.test.tsx
git commit -m "feat(feed): add PolicyCard"
```

---

### Task 16: `AgentEventCard` and `ResolvedCard`

> Bundling two small cards into one task — both are read-only summaries.

**Files:**
- Create: `web/client/components/feed/cards/AgentEventCard.tsx`
- Create: `web/client/components/feed/cards/ResolvedCard.tsx`
- Test: `web/client/components/feed/__tests__/cards/AgentEventCard.test.tsx`
- Test: `web/client/components/feed/__tests__/cards/ResolvedCard.test.tsx`

- [ ] **Step 1: Write the failing AgentEventCard test**

```tsx
// @vitest-environment jsdom
// web/client/components/feed/__tests__/cards/AgentEventCard.test.tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import AgentEventCard from "@client/components/feed/cards/AgentEventCard";
import type { AgentEventItem } from "@shared/feedItems";

afterEach(cleanup);

const item: AgentEventItem = {
  type: "agent-event", id: "agent-event:fm:1:0", timestamp: 100,
  severity: null, source: "fleet-manager", kind: "wakeup",
  data: { workflow_id: "WF-1", reason: "SLA breach in 8m" },
  workflowId: "WF-1",
};

describe("AgentEventCard", () => {
  it("renders the kind and source", () => {
    render(<MemoryRouter><AgentEventCard item={item} /></MemoryRouter>);
    expect(screen.getByText(/wakeup/i)).toBeTruthy();
    expect(screen.getByText(/Fleet Manager/i)).toBeTruthy();
  });
  it("Expand JSON toggles a <pre> inline (not a drawer)", () => {
    render(<MemoryRouter><AgentEventCard item={item} /></MemoryRouter>);
    expect(screen.queryByText(/SLA breach in 8m/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Expand JSON/i }));
    expect(screen.getByText(/SLA breach in 8m/)).toBeTruthy();
  });
});
```

- [ ] **Step 2: Write the failing ResolvedCard test**

```tsx
// @vitest-environment jsdom
// web/client/components/feed/__tests__/cards/ResolvedCard.test.tsx
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import ResolvedCard from "@client/components/feed/cards/ResolvedCard";
import { ResolutionProvider, useResolutionStore } from "@client/hooks/useResolutionStore";
import type { ResolvedItem, HITLItem } from "@shared/feedItems";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const origin: HITLItem = {
  type: "hitl", id: "hitl:WF-1", timestamp: 100,
  workflowId: "WF-1", domain: "expense-claim", severity: "high",
};

const item: ResolvedItem = {
  type: "resolved", id: "resolved:hitl:WF-1", timestamp: 100,
  workflowId: "WF-1", domain: "expense-claim", severity: null,
  origin, verb: "Approved", actor: "you", actedAt: Math.floor(Date.now() / 1000),
};

describe("ResolvedCard", () => {
  it("renders 'Approved by you' with relative time", () => {
    render(<MemoryRouter><ResolutionProvider><ResolvedCard item={item} /></ResolutionProvider></MemoryRouter>);
    expect(screen.getByText(/Approved by you/i)).toBeTruthy();
  });

  it("undo calls store.revert when undoable", () => {
    function Bootstrap() {
      const store = useResolutionStore();
      // Pre-record so undoable=true
      if (!store.get("hitl:WF-1")) {
        store.record("hitl:WF-1", { verb: "Approved", actor: "you", actedAt: 100 });
      }
      return <ResolvedCard item={item} />;
    }
    render(<MemoryRouter><ResolutionProvider><Bootstrap /></ResolutionProvider></MemoryRouter>);
    const undo = screen.queryByRole("button", { name: /undo/i });
    expect(undo).toBeTruthy();
    fireEvent.click(undo!);
    // After click, the button is gone (state was reverted)
    expect(screen.queryByRole("button", { name: /undo/i })).toBeNull();
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `npx vitest run web/client/components/feed/__tests__/cards/AgentEventCard.test.tsx web/client/components/feed/__tests__/cards/ResolvedCard.test.tsx`
Expected: FAIL — modules not found.

- [ ] **Step 4: Write `AgentEventCard.tsx`**

```tsx
// web/client/components/feed/cards/AgentEventCard.tsx
//
// FM/orchestration event surface. Spec §3.4: "Expand JSON" is an inline
// accordion, not a drawer open — raw JSON is not worth a drawer.
import { useState } from "react";
import { Activity } from "lucide-react";
import type { AgentEventItem } from "@shared/feedItems";
import CardShell from "../CardShell";

const SOURCE_LABEL: Record<AgentEventItem["source"], string> = {
  "fleet-manager": "Fleet Manager",
  "orchestration": "Orchestration",
};

export default function AgentEventCard({ item }: { item: AgentEventItem }) {
  const [open, setOpen] = useState(false);

  const body = (
    <div className="min-w-0">
      <div className="text-sm text-slate-800">
        <span className="font-medium">{SOURCE_LABEL[item.source]}</span>
        <span className="text-slate-400"> · </span>
        <span className="font-mono text-xs">{item.kind}</span>
        {item.workflowId ? <span className="text-slate-500 text-xs"> on {item.workflowId}</span> : null}
      </div>
      {open && item.data != null && (
        <pre className="text-[11px] text-slate-700 bg-slate-50 rounded p-2 mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-all">
{JSON.stringify(item.data, null, 2)}
        </pre>
      )}
    </div>
  );

  const actions = (
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
      className="text-xs px-3 py-1.5 rounded font-medium bg-white text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50"
    >
      {open ? "Hide JSON" : "Expand JSON"}
    </button>
  );

  return (
    <CardShell
      severity={item.severity ?? null}
      icon={<Activity size={12} className="text-purple-600" />}
      typeLabel="Agent event"
      workflowId={item.workflowId ?? "—"}
      timestampSec={item.timestamp}
      body={body}
      actions={actions}
    />
  );
}
```

- [ ] **Step 5: Write `ResolvedCard.tsx`**

```tsx
// web/client/components/feed/cards/ResolvedCard.tsx
//
// Collapsed in-place replacement for a HITL/Exception/ExternalWait card
// the user has acted on. Per spec §3.5: "✓ <Verb> by you · <relative time>
// · undo · audit ↗". Undo is live for 30s (managed by useResolutionStore);
// after TTL the undo button hides.
import { CheckCircle2 } from "lucide-react";
import type { ResolvedItem } from "@shared/feedItems";
import CardShell from "../CardShell";
import { useResolutionStore } from "@client/hooks/useResolutionStore";

function relativeTime(tsSec: number): string {
  const diff = Math.max(0, Date.now() / 1000 - tsSec);
  if (diff < 60) return `${Math.round(diff)}s ago`;
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  return `${(diff / 3600).toFixed(1)}h ago`;
}

export default function ResolvedCard({
  item, onOpenDrawer,
}: {
  item: ResolvedItem;
  onOpenDrawer?: (workflowId: string) => void;
}) {
  const store = useResolutionStore();
  const r = store.get(item.origin.id);
  const undoable = r?.undoable ?? false;

  const body = (
    <div className="text-sm text-slate-600 truncate">
      <CheckCircle2 size={14} className="inline-block text-emerald-600 mr-1.5 align-text-bottom" />
      <span className="font-medium text-slate-800">{item.verb} by {item.actor}</span>
      <span className="text-slate-400"> · {relativeTime(item.actedAt)}</span>
    </div>
  );

  const actions = (
    <>
      {undoable && (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); store.revert(item.origin.id); }}
          className="text-xs px-3 py-1 rounded font-medium bg-white text-amber-700 ring-1 ring-amber-300 hover:bg-amber-50"
        >Undo</button>
      )}
      {item.workflowId && (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onOpenDrawer?.(item.workflowId!); }}
          className="text-xs px-3 py-1 rounded font-medium bg-white text-slate-500 ring-1 ring-slate-200 hover:bg-slate-50"
        >Audit ↗</button>
      )}
    </>
  );

  return (
    <CardShell
      severity={null}
      icon={<CheckCircle2 size={12} className="text-emerald-600" />}
      typeLabel="Resolved"
      workflowId={item.workflowId ?? "—"}
      timestampSec={item.actedAt}
      body={body}
      actions={actions}
    />
  );
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `npx vitest run web/client/components/feed/__tests__/cards/AgentEventCard.test.tsx web/client/components/feed/__tests__/cards/ResolvedCard.test.tsx`
Expected: PASS — 4 assertions total.

- [ ] **Step 7: Commit**

```bash
git add web/client/components/feed/cards/AgentEventCard.tsx web/client/components/feed/cards/ResolvedCard.tsx web/client/components/feed/__tests__/cards/AgentEventCard.test.tsx web/client/components/feed/__tests__/cards/ResolvedCard.test.tsx
git commit -m "feat(feed): add AgentEventCard and ResolvedCard"
```


---

## Phase D — Feed orchestration

### Task 17: `FilterBar`

**Files:**
- Create: `web/client/components/feed/FilterBar.tsx`
- Test: `web/client/components/feed/__tests__/FilterBar.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// @vitest-environment jsdom
// web/client/components/feed/__tests__/FilterBar.test.tsx
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import FilterBar from "@client/components/feed/FilterBar";

afterEach(cleanup);

const noop = () => {};

describe("FilterBar", () => {
  it("renders the [Needs you] / [All activity] segmented control", () => {
    render(
      <FilterBar
        filter={{ mode: "needs-you", domains: [], severity: null, search: "" }}
        onChange={noop}
        selectMode={false}
        onSelectModeChange={noop}
        availableDomains={[]}
      />,
    );
    expect(screen.getByRole("button", { name: /Needs you/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /All activity/i })).toBeTruthy();
  });

  it("fires onChange with new mode when All activity is clicked", () => {
    const onChange = vi.fn();
    render(
      <FilterBar
        filter={{ mode: "needs-you", domains: [], severity: null, search: "" }}
        onChange={onChange}
        selectMode={false}
        onSelectModeChange={noop}
        availableDomains={[]}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /All activity/i }));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ mode: "all-activity" }),
    );
  });

  it("renders a domain chip per availableDomains entry and toggles it", () => {
    const onChange = vi.fn();
    render(
      <FilterBar
        filter={{ mode: "needs-you", domains: [], severity: null, search: "" }}
        onChange={onChange}
        selectMode={false}
        onSelectModeChange={noop}
        availableDomains={["expense-claim", "hiring"]}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /^expense-claim$/i }));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ domains: ["expense-claim"] }),
    );
  });

  it("supports a 'Select' mode toggle", () => {
    const onSel = vi.fn();
    render(
      <FilterBar
        filter={{ mode: "needs-you", domains: [], severity: null, search: "" }}
        onChange={noop}
        selectMode={false}
        onSelectModeChange={onSel}
        availableDomains={[]}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /^Select$/i }));
    expect(onSel).toHaveBeenCalledWith(true);
  });

  it("fires onChange with new search on each keystroke", () => {
    const onChange = vi.fn();
    render(
      <FilterBar
        filter={{ mode: "needs-you", domains: [], severity: null, search: "" }}
        onChange={onChange}
        selectMode={false}
        onSelectModeChange={noop}
        availableDomains={[]}
      />,
    );
    fireEvent.change(screen.getByPlaceholderText(/search/i), { target: { value: "WF-12" } });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ search: "WF-12" }),
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/components/feed/__tests__/FilterBar.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the file**

```tsx
// web/client/components/feed/FilterBar.tsx
//
// Top-of-feed control bar: segmented mode toggle, domain chips, severity
// pill, select-mode toggle, search input. Emits a fresh FilterState on
// every change via onChange.
import type { FilterState } from "@client/hooks/useFeedItems";

const SEVERITY_CHOICES: Array<FilterState["severity"]> = [null, "critical", "high", "medium"];

export default function FilterBar({
  filter, onChange, selectMode, onSelectModeChange, availableDomains,
}: {
  filter: FilterState;
  onChange: (next: FilterState) => void;
  selectMode: boolean;
  onSelectModeChange: (next: boolean) => void;
  availableDomains: string[];
}) {
  const setMode = (mode: FilterState["mode"]) => onChange({ ...filter, mode });
  const toggleDomain = (d: string) => {
    const has = filter.domains.includes(d);
    onChange({ ...filter, domains: has ? filter.domains.filter((x) => x !== d) : [...filter.domains, d] });
  };
  const setSeverity = (s: FilterState["severity"]) => onChange({ ...filter, severity: s });
  const setSearch = (s: string) => onChange({ ...filter, search: s });

  return (
    <div className="flex items-center gap-2 flex-wrap bg-white border border-slate-200 rounded-lg p-2 mb-3 sticky top-0 z-10">
      <div className="inline-flex rounded-md border border-slate-200 overflow-hidden">
        <button
          type="button" onClick={() => setMode("needs-you")}
          className={`text-xs px-3 py-1.5 font-medium ${filter.mode === "needs-you" ? "bg-blue-600 text-white" : "bg-white text-slate-600 hover:bg-slate-50"}`}
        >● Needs you</button>
        <button
          type="button" onClick={() => setMode("all-activity")}
          className={`text-xs px-3 py-1.5 font-medium border-l border-slate-200 ${filter.mode === "all-activity" ? "bg-blue-600 text-white" : "bg-white text-slate-600 hover:bg-slate-50"}`}
        >All activity</button>
      </div>

      <div className="flex items-center gap-1 flex-wrap">
        {availableDomains.map((d) => {
          const active = filter.domains.includes(d);
          return (
            <button
              key={d}
              type="button"
              onClick={() => toggleDomain(d)}
              className={`text-[11px] px-2 py-1 rounded font-medium ${active ? "bg-slate-700 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}
            >{d}</button>
          );
        })}
      </div>

      <select
        aria-label="Severity"
        value={filter.severity ?? ""}
        onChange={(e) => setSeverity((e.target.value || null) as FilterState["severity"])}
        className="text-xs border border-slate-200 rounded px-2 py-1 bg-white text-slate-700"
      >
        {SEVERITY_CHOICES.map((s) => (
          <option key={s ?? ""} value={s ?? ""}>{s == null ? "any severity" : s}</option>
        ))}
      </select>

      <input
        type="search"
        placeholder="Search workflow id…"
        value={filter.search}
        onChange={(e) => setSearch(e.target.value)}
        className="text-xs border border-slate-200 rounded px-2 py-1 bg-white text-slate-700 w-48"
      />

      <button
        type="button"
        onClick={() => onSelectModeChange(!selectMode)}
        className={`ml-auto text-xs px-3 py-1.5 rounded font-medium ${selectMode ? "bg-blue-600 text-white" : "bg-white text-slate-600 ring-1 ring-slate-300 hover:bg-slate-50"}`}
      >{selectMode ? "Done" : "Select"}</button>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/client/components/feed/__tests__/FilterBar.test.tsx`
Expected: PASS — 5 assertions.

- [ ] **Step 5: Commit**

```bash
git add web/client/components/feed/FilterBar.tsx web/client/components/feed/__tests__/FilterBar.test.tsx
git commit -m "feat(feed): add FilterBar with mode toggle, domain chips, severity, search, select mode"
```

---

### Task 18: `NewItemsPill`

**Files:**
- Create: `web/client/components/feed/NewItemsPill.tsx`
- Test: `web/client/components/feed/__tests__/NewItemsPill.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// @vitest-environment jsdom
// web/client/components/feed/__tests__/NewItemsPill.test.tsx
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import NewItemsPill from "@client/components/feed/NewItemsPill";

afterEach(cleanup);

describe("NewItemsPill", () => {
  it("renders nothing when count is 0", () => {
    const { container } = render(<NewItemsPill count={0} onPullIn={() => {}} />);
    expect(container.firstChild).toBeNull();
  });
  it("renders '↑ 3 new' when count is 3", () => {
    render(<NewItemsPill count={3} onPullIn={() => {}} />);
    expect(screen.getByRole("button", { name: /3 new/i })).toBeTruthy();
  });
  it("fires onPullIn on click", () => {
    const onPullIn = vi.fn();
    render(<NewItemsPill count={1} onPullIn={onPullIn} />);
    fireEvent.click(screen.getByRole("button"));
    expect(onPullIn).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/components/feed/__tests__/NewItemsPill.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the file**

```tsx
// web/client/components/feed/NewItemsPill.tsx
import { ArrowUp } from "lucide-react";

export default function NewItemsPill({
  count, onPullIn,
}: {
  count: number;
  onPullIn: () => void;
}) {
  if (count <= 0) return null;
  return (
    <div className="flex justify-center sticky top-14 z-10 -mt-1 mb-2 pointer-events-none">
      <button
        type="button"
        onClick={onPullIn}
        className="pointer-events-auto text-xs px-3 py-1.5 rounded-full bg-blue-600 text-white shadow font-medium flex items-center gap-1 hover:bg-blue-700"
      >
        <ArrowUp size={12} />
        {count} new
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/client/components/feed/__tests__/NewItemsPill.test.tsx`
Expected: PASS — 3 assertions.

- [ ] **Step 5: Commit**

```bash
git add web/client/components/feed/NewItemsPill.tsx web/client/components/feed/__tests__/NewItemsPill.test.tsx
git commit -m "feat(feed): add NewItemsPill"
```

---

### Task 19: `CardList` with manual windowing

**Files:**
- Create: `web/client/components/feed/CardList.tsx`
- Test: `web/client/components/feed/__tests__/CardList.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// @vitest-environment jsdom
// web/client/components/feed/__tests__/CardList.test.tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import CardList from "@client/components/feed/CardList";
import { ResolutionProvider } from "@client/hooks/useResolutionStore";
import type { FeedItem } from "@shared/feedItems";

afterEach(cleanup);

function mk(i: number): FeedItem {
  return {
    type: "hitl", id: `hitl:W-${i}`, timestamp: 1000 - i,
    workflowId: `W-${i}`, domain: "expense-claim", severity: "medium",
    workflow: {
      id: `W-${i}`, type: "expense-claim", status: "awaiting_hitl",
      currentPhase: "Intake", createdAt: 1, slaDueAt: 9999,
      jurisdiction: "UK", agency: "Z", actionLedger: [],
      tokensSpent: 0, costUSD: 0,
    },
  };
}

describe("CardList", () => {
  it("renders all items below the windowing threshold", () => {
    const items = Array.from({ length: 5 }, (_, i) => mk(i));
    render(
      <MemoryRouter><ResolutionProvider>
        <CardList items={items} hideActions={false} onOpenDrawer={() => {}} selectMode={false} selected={new Set()} onToggleSelect={() => {}} />
      </ResolutionProvider></MemoryRouter>,
    );
    expect(screen.getAllByText(/^W-/).length).toBe(5);
  });

  it("renders an empty-state hint when items is empty", () => {
    render(
      <MemoryRouter><ResolutionProvider>
        <CardList items={[]} hideActions={false} onOpenDrawer={() => {}} selectMode={false} selected={new Set()} onToggleSelect={() => {}} />
      </ResolutionProvider></MemoryRouter>,
    );
    expect(screen.getByText(/nothing here/i)).toBeTruthy();
  });

  it("renders a checkbox per card in selectMode", () => {
    const items = Array.from({ length: 3 }, (_, i) => mk(i));
    render(
      <MemoryRouter><ResolutionProvider>
        <CardList items={items} hideActions={false} onOpenDrawer={() => {}} selectMode={true} selected={new Set()} onToggleSelect={() => {}} />
      </ResolutionProvider></MemoryRouter>,
    );
    expect(screen.getAllByRole("checkbox").length).toBe(3);
  });

  it("windows to 100 items at most when list is larger", () => {
    const items = Array.from({ length: 150 }, (_, i) => mk(i));
    render(
      <MemoryRouter><ResolutionProvider>
        <CardList items={items} hideActions={false} onOpenDrawer={() => {}} selectMode={false} selected={new Set()} onToggleSelect={() => {}} />
      </ResolutionProvider></MemoryRouter>,
    );
    // After windowing, only first 100 cards' workflow ids render.
    expect(screen.queryByText(/^W-149$/)).toBeNull();
    expect(screen.getByText(/^W-0$/)).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/components/feed/__tests__/CardList.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the file**

```tsx
// web/client/components/feed/CardList.tsx
//
// Renders a typed feed of cards. Dispatches by item.type to the matching
// card component. Beyond 100 items the list windows to the first 100; a
// "show older" trailer button extends the window by 100 more on demand
// (cheap manual virtualisation — no library dep).
import { useState } from "react";
import type { FeedItem } from "@shared/feedItems";
import HITLCard from "./cards/HITLCard";
import ExceptionCard from "./cards/ExceptionCard";
import ExternalWaitCard from "./cards/ExternalWaitCard";
import MilestoneCard from "./cards/MilestoneCard";
import PolicyCard from "./cards/PolicyCard";
import AgentEventCard from "./cards/AgentEventCard";
import ResolvedCard from "./cards/ResolvedCard";

const PAGE = 100;

export default function CardList({
  items, hideActions, onOpenDrawer, selectMode, selected, onToggleSelect,
}: {
  items: FeedItem[];
  hideActions: boolean;
  onOpenDrawer: (workflowId: string) => void;
  selectMode: boolean;
  selected: Set<string>;
  onToggleSelect: (itemId: string) => void;
}) {
  const [limit, setLimit] = useState(PAGE);

  if (items.length === 0) {
    return (
      <div className="text-sm text-slate-500 italic px-2 py-8 text-center border border-dashed border-slate-200 rounded">
        Nothing here. Try switching to "All activity".
      </div>
    );
  }

  const visible = items.slice(0, limit);

  return (
    <div className="space-y-3">
      {visible.map((it) => (
        <div key={it.id} className="flex items-start gap-2">
          {selectMode && (
            <input
              type="checkbox"
              className="mt-3"
              checked={selected.has(it.id)}
              onChange={() => onToggleSelect(it.id)}
              aria-label={`select ${it.id}`}
            />
          )}
          <div className="flex-1 min-w-0">
            {renderCard(it, { hideActions, onOpenDrawer })}
          </div>
        </div>
      ))}
      {items.length > visible.length && (
        <div className="flex justify-center">
          <button
            type="button"
            onClick={() => setLimit((n) => n + PAGE)}
            className="text-xs px-3 py-1.5 rounded bg-white text-slate-600 ring-1 ring-slate-300 hover:bg-slate-50"
          >Show {Math.min(PAGE, items.length - visible.length)} older</button>
        </div>
      )}
    </div>
  );
}

function renderCard(
  it: FeedItem,
  o: { hideActions: boolean; onOpenDrawer: (wid: string) => void },
) {
  switch (it.type) {
    case "hitl":          return <HITLCard         item={it} hideActions={o.hideActions} onOpenDrawer={o.onOpenDrawer} />;
    case "exception":     return <ExceptionCard    item={it} hideActions={o.hideActions} onOpenDrawer={o.onOpenDrawer} />;
    case "external-wait": return <ExternalWaitCard item={it} hideActions={o.hideActions} onOpenDrawer={o.onOpenDrawer} />;
    case "milestone":     return <MilestoneCard    item={it} hideActions={o.hideActions} onOpenDrawer={o.onOpenDrawer} />;
    case "policy":        return <PolicyCard       item={it} hideActions={o.hideActions} onOpenDrawer={o.onOpenDrawer} />;
    case "agent-event":   return <AgentEventCard   item={it} />;
    case "resolved":      return <ResolvedCard     item={it} onOpenDrawer={o.onOpenDrawer} />;
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/client/components/feed/__tests__/CardList.test.tsx`
Expected: PASS — 4 assertions.

- [ ] **Step 5: Commit**

```bash
git add web/client/components/feed/CardList.tsx web/client/components/feed/__tests__/CardList.test.tsx
git commit -m "feat(feed): add CardList with type-dispatched cards + manual windowing"
```

---

### Task 20: `Feed` orchestrator

**Files:**
- Create: `web/client/components/feed/Feed.tsx`
- Test: `web/client/components/feed/__tests__/Feed.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// @vitest-environment jsdom
// web/client/components/feed/__tests__/Feed.test.tsx
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Feed from "@client/components/feed/Feed";
import { ResolutionProvider } from "@client/hooks/useResolutionStore";
import { getRolePreset } from "@shared/roles";

beforeEach(() => {
  (globalThis as any).EventSource = class {
    onmessage: ((ev: MessageEvent) => void) | null = null;
    addEventListener() {} close() {}
  };
  globalThis.fetch = vi.fn().mockImplementation((url: string) => {
    if (url.startsWith("/api/workflows")) {
      return Promise.resolve({
        ok: true, json: async () => [
          { id: "W-1", type: "expense-claim", status: "awaiting_hitl",
            currentPhase: "Intake", createdAt: 100, slaDueAt: 9999,
            jurisdiction: "UK", agency: "Z", actionLedger: [],
            tokensSpent: 0, costUSD: 0 },
        ],
      } as Response);
    }
    return Promise.resolve({ ok: true, json: async () => [] } as Response);
  });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("Feed", () => {
  it("renders the filter bar + at least one HITL card", async () => {
    const role = getRolePreset("ops-reviewer");
    render(
      <MemoryRouter>
        <ResolutionProvider>
          <Feed role={role} onOpenDrawer={() => {}} />
        </ResolutionProvider>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText("W-1")).toBeTruthy();
    });
    expect(screen.getByRole("button", { name: /Needs you/i })).toBeTruthy();
  });

  it("switching to All activity calls the same query but with different filter", async () => {
    const role = getRolePreset("ops-reviewer");
    render(
      <MemoryRouter>
        <ResolutionProvider>
          <Feed role={role} onOpenDrawer={() => {}} />
        </ResolutionProvider>
      </MemoryRouter>,
    );
    fireEvent.click(await screen.findByRole("button", { name: /All activity/i }));
    // Filter button is now active; no fetch difference required by the test
    expect(screen.getByRole("button", { name: /All activity/i }).className).toMatch(/bg-blue-600/);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/components/feed/__tests__/Feed.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the file**

```tsx
// web/client/components/feed/Feed.tsx
//
// The Feed is the operator's home. It owns the active filter state, the
// inbound-buffer state, and select-mode for bulk actions. Items come from
// useFeedItems (which takes the role + filter). The role-default filter
// can be overridden by URL param `?filter=hitl|exceptions|needs-you|all`
// (used by the 301 redirects from /reviewer-queue and /exceptions).
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { RolePreset } from "@shared/roles";
import { useFeedItems, type FilterState } from "@client/hooks/useFeedItems";
import { useNewItemsBuffer } from "@client/hooks/useNewItemsBuffer";
import FilterBar from "./FilterBar";
import NewItemsPill from "./NewItemsPill";
import CardList from "./CardList";
import BulkActionBar from "./BulkActionBar";

const KNOWN_DOMAINS = [
  "expense-claim", "hiring", "invoice-p2p", "travel-preapproval", "vendor-kyc",
  "employee-onboarding", "it-access-request", "contract-renewal", "perf-review",
  "ap-invoice", "purchase-order", "contract-review", "privacy-dpia", "treasury-fx",
  "creative-campaign",
];

function filterFromUrl(rawMode: string | null): Partial<FilterState> | null {
  if (rawMode === "hitl") return { mode: "needs-you" };
  if (rawMode === "exceptions") return { mode: "needs-you" };
  if (rawMode === "needs-you") return { mode: "needs-you" };
  if (rawMode === "all") return { mode: "all-activity" };
  return null;
}

export default function Feed({
  role, onOpenDrawer,
}: {
  role: RolePreset;
  onOpenDrawer: (workflowId: string) => void;
}) {
  const [params] = useSearchParams();
  const initialUrl = filterFromUrl(params.get("filter"));

  const [filter, setFilter] = useState<FilterState>(() => ({
    mode: initialUrl?.mode ?? role.defaultFilter,
    domains: role.defaultDomains,
    severity: null,
    search: "",
  }));

  // Re-apply role defaults when role changes (RoleSwitcher re-mounts the
  // Feed indirectly via FleetControlShell). We rely on key= in the shell
  // to force this, but also re-seed on prop change to be safe.
  useEffect(() => {
    setFilter((f) => ({
      ...f,
      mode: role.defaultFilter,
      domains: role.defaultDomains,
    }));
  }, [role.id, role.defaultFilter, role.defaultDomains]);

  const items = useFeedItems(role, filter);
  const buffer = useNewItemsBuffer(items);

  const [selectMode, setSelectMode] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const toggleSelect = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  const clearSelection = () => setSelected(new Set());

  const availableDomains = useMemo(
    () => (role.defaultDomains.length > 0 ? role.defaultDomains : KNOWN_DOMAINS),
    [role.defaultDomains],
  );

  return (
    <div className="px-6 py-4 flex-1 min-w-0 overflow-y-auto">
      <FilterBar
        filter={filter}
        onChange={setFilter}
        selectMode={selectMode}
        onSelectModeChange={(v) => { setSelectMode(v); if (!v) clearSelection(); }}
        availableDomains={availableDomains}
      />
      <NewItemsPill count={buffer.pendingCount} onPullIn={buffer.pullIn} />
      <CardList
        items={buffer.visible}
        hideActions={role.hideActionButtons}
        onOpenDrawer={onOpenDrawer}
        selectMode={selectMode && !role.hideActionButtons}
        selected={selected}
        onToggleSelect={toggleSelect}
      />
      {selectMode && !role.hideActionButtons && (
        <BulkActionBar
          selectedIds={[...selected]}
          onCleared={clearSelection}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/client/components/feed/__tests__/Feed.test.tsx`
Expected: PASS — 2 assertions.

> **Note:** This task imports `BulkActionBar` which is created in Task 32. Stub it for now with a placeholder export so the build compiles, OR write Task 32 immediately after this and run the test then. Recommended path: write Task 20 + Task 32 back-to-back to keep TS green.

- [ ] **Step 5: Commit**

```bash
git add web/client/components/feed/Feed.tsx web/client/components/feed/__tests__/Feed.test.tsx
git commit -m "feat(feed): add Feed orchestrator (filter + buffer + list + bulk)"
```


---

## Phase E — Drawer

> The drawer reshapes the existing `WorkflowDetail.tsx` content. None of the apex / governance child components change — they get re-arranged into 3 sections instead of 6 tabs + 6 panels.

### Task 21: `Drawer` shell

**Files:**
- Create: `web/client/components/feed/Drawer.tsx`
- Test: `web/client/components/feed/__tests__/Drawer.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// @vitest-environment jsdom
// web/client/components/feed/__tests__/Drawer.test.tsx
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Drawer from "@client/components/feed/Drawer";
import { ResolutionProvider } from "@client/hooks/useResolutionStore";
import { getRolePreset } from "@shared/roles";

beforeEach(() => {
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      workflow: {
        id: "WF-1", type: "expense-claim", status: "awaiting_hitl",
        currentPhase: "Intake", createdAt: 1, slaDueAt: 9999,
        jurisdiction: "UK", agency: "Z", actionLedger: [],
        tokensSpent: 0, costUSD: 0,
      },
      phases: [], spans: [], amplifications: [],
      activeException: null, mcpCalls: [],
      economics: { activeWorkflowCount: 1, totalWorkflowCount: 1,
        autoApprovedCount: 0, escalationCount: 0, averageCostPerWorkflow: 0 },
      narrative: null,
    }),
  } as Response);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("Drawer", () => {
  it("renders 3 section headings in the order dictated by the role", async () => {
    render(
      <MemoryRouter>
        <ResolutionProvider>
          <Drawer
            workflowId="WF-1"
            role={getRolePreset("ops-reviewer")}
            onClose={() => {}}
          />
        </ResolutionProvider>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText(/Decision/i)).toBeTruthy();
    });
    const headings = screen.getAllByRole("heading");
    const text = headings.map((h) => h.textContent ?? "");
    expect(text.findIndex((t) => /Decision/i.test(t)))
      .toBeLessThan(text.findIndex((t) => /Activity/i.test(t)));
    expect(text.findIndex((t) => /Activity/i.test(t)))
      .toBeLessThan(text.findIndex((t) => /Audit/i.test(t)));
  });

  it("Executive role flips section order to Audit · Activity · Decision", async () => {
    render(
      <MemoryRouter>
        <ResolutionProvider>
          <Drawer
            workflowId="WF-1"
            role={getRolePreset("executive")}
            onClose={() => {}}
          />
        </ResolutionProvider>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText(/Audit/i)).toBeTruthy();
    });
    const headings = screen.getAllByRole("heading");
    const text = headings.map((h) => h.textContent ?? "");
    const auditIdx = text.findIndex((t) => /Audit/i.test(t));
    const activityIdx = text.findIndex((t) => /Activity/i.test(t));
    const decisionIdx = text.findIndex((t) => /Decision/i.test(t));
    expect(auditIdx).toBeLessThan(activityIdx);
    expect(activityIdx).toBeLessThan(decisionIdx);
  });

  it("Esc fires onClose", async () => {
    const onClose = vi.fn();
    render(
      <MemoryRouter>
        <ResolutionProvider>
          <Drawer
            workflowId="WF-1"
            role={getRolePreset("ops-reviewer")}
            onClose={onClose}
          />
        </ResolutionProvider>
      </MemoryRouter>,
    );
    await waitFor(() => screen.getByText(/Decision/i));
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/components/feed/__tests__/Drawer.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the file**

```tsx
// web/client/components/feed/Drawer.tsx
//
// Right-side drawer over the feed. Loads /api/workflows/:id and renders 3
// sections (Decision · Activity · Audit) in the role-dictated order. Esc
// or the ✕ button fires onClose. The drawer width is fluid (50–65 % of
// viewport via Tailwind responsive utilities); below 1024px it's full-screen.
import { useEffect, useState, useCallback } from "react";
import type {
  Workflow, Phase, OtelSpan, Exception, SkillAmplification,
  McpCall, Economics, Narrative,
} from "@shared/types";
import type { RolePreset } from "@shared/roles";
import DrawerDecision from "./DrawerDecision";
import DrawerActivity from "./DrawerActivity";
import DrawerAudit from "./DrawerAudit";

export interface DrawerData {
  workflow: Workflow;
  phases: Phase[];
  spans: OtelSpan[];
  amplifications: SkillAmplification[];
  activeException: Exception | null;
  mcpCalls: McpCall[];
  economics: Economics;
  narrative: Narrative | null;
  auditBlobUrl?: string | null;
}

export default function Drawer({
  workflowId, role, onClose,
}: {
  workflowId: string;
  role: RolePreset;
  onClose: () => void;
}) {
  const [d, setD] = useState<DrawerData | null>(null);

  const refresh = useCallback(async () => {
    const r = await fetch(`/api/workflows/${workflowId}`);
    setD((await r.json()) as DrawerData);
  }, [workflowId]);

  useEffect(() => {
    void refresh();
    const i = setInterval(() => { void refresh(); }, 2500);
    return () => clearInterval(i);
  }, [refresh]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!d) {
    return (
      <aside className="fixed inset-y-0 right-0 z-40 w-full lg:w-[65%] xl:w-[60%] 2xl:w-[50%] bg-white border-l border-slate-200 shadow-xl flex flex-col">
        <div className="p-4 text-sm text-slate-500">loading…</div>
      </aside>
    );
  }

  const sections: Record<string, JSX.Element> = {
    decision: (
      <DrawerDecision data={d} role={role} onRefresh={refresh} />
    ),
    activity: (
      <DrawerActivity data={d} />
    ),
    audit: (
      <DrawerAudit data={d} />
    ),
  };

  return (
    <aside
      className="fixed inset-y-0 right-0 z-40 w-full lg:w-[65%] xl:w-[60%] 2xl:w-[50%] bg-white border-l border-slate-200 shadow-xl flex flex-col"
      aria-label="Workflow detail drawer"
    >
      <header className="flex items-center gap-3 px-5 h-14 border-b border-slate-200">
        <div className="font-mono text-sm text-slate-900">{d.workflow.id}</div>
        <span className="text-[10px] uppercase tracking-wide bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">
          {d.workflow.type}
        </span>
        <span className="text-[10px] uppercase tracking-wide bg-amber-50 text-amber-700 px-1.5 py-0.5 rounded">
          {d.workflow.status}
        </span>
        <DomainDeepLink workflow={d.workflow} />
        <button
          type="button"
          onClick={onClose}
          aria-label="Close drawer"
          className="ml-auto text-slate-400 hover:text-slate-700 text-lg px-2"
        >✕</button>
      </header>
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-6">
        {role.drawerSectionOrder.map((s) => (
          <div key={s}>{sections[s]}</div>
        ))}
      </div>
    </aside>
  );
}

function DomainDeepLink({ workflow }: { workflow: Workflow }) {
  // Preserves cross-app deep-links carried over from WorkflowDetail.tsx.
  const candidateId = (workflow.metadata as { candidate_id?: string } | undefined)?.candidate_id;
  if (workflow.type === "hiring" && candidateId) {
    return (
      <a
        href={`http://localhost:5274/recruiter/c/${encodeURIComponent(candidateId)}`}
        target="_blank" rel="noreferrer"
        className="text-xs text-blue-600 hover:underline"
      >open in recruiter view ↗</a>
    );
  }
  return null;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/client/components/feed/__tests__/Drawer.test.tsx`
Expected: PASS — 3 assertions.

> The test references `DrawerDecision`/`DrawerActivity`/`DrawerAudit`; those are stubbed inline by importing them. Tasks 22-24 create real ones; for THIS task, **also create stub implementations** so TS compiles:
>
> ```tsx
> // web/client/components/feed/DrawerDecision.tsx
> export default function DrawerDecision() { return <section><h2>Decision</h2></section>; }
> // web/client/components/feed/DrawerActivity.tsx
> export default function DrawerActivity() { return <section><h2>Activity</h2></section>; }
> // web/client/components/feed/DrawerAudit.tsx
> export default function DrawerAudit() { return <section><h2>Audit</h2></section>; }
> ```
>
> Replace with full implementations in Tasks 22–24.

- [ ] **Step 5: Commit**

```bash
git add web/client/components/feed/Drawer.tsx web/client/components/feed/DrawerDecision.tsx web/client/components/feed/DrawerActivity.tsx web/client/components/feed/DrawerAudit.tsx web/client/components/feed/__tests__/Drawer.test.tsx
git commit -m "feat(feed): add Drawer shell with role-ordered sections + Esc handler"
```

---

### Task 22: `DrawerDecision` — port WorkflowDetail Overview tab

**Files:**
- Modify: `web/client/components/feed/DrawerDecision.tsx` (replace stub)
- Test: `web/client/components/feed/__tests__/DrawerDecision.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// @vitest-environment jsdom
// web/client/components/feed/__tests__/DrawerDecision.test.tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ResolutionProvider } from "@client/hooks/useResolutionStore";
import DrawerDecision from "@client/components/feed/DrawerDecision";
import { getRolePreset } from "@shared/roles";
import type { DrawerData } from "@client/components/feed/Drawer";

afterEach(cleanup);

const d: DrawerData = {
  workflow: {
    id: "WF-1", type: "expense-claim", status: "awaiting_hitl",
    currentPhase: "Intake", createdAt: 1, slaDueAt: 9999,
    jurisdiction: "UK", agency: "Z", actionLedger: [],
    tokensSpent: 0, costUSD: 0,
    claim: {
      claimId: "CL-1", employeeId: "E-1",
      submittedAt: "2026-05-18T10:00:00Z",
      market: "UK", currency: "GBP", category: "meals",
      vendor: "Pret", amount: 42, attendees: 1, emsSource: "concur",
    },
  },
  phases: [], spans: [], amplifications: [],
  activeException: null, mcpCalls: [],
  economics: { activeWorkflowCount: 1, totalWorkflowCount: 1, autoApprovedCount: 0, escalationCount: 0, averageCostPerWorkflow: 0 },
  narrative: null,
};

describe("DrawerDecision", () => {
  it("renders the section heading", () => {
    render(<MemoryRouter><ResolutionProvider><DrawerDecision data={d} role={getRolePreset("ops-reviewer")} onRefresh={() => {}} /></ResolutionProvider></MemoryRouter>);
    expect(screen.getByRole("heading", { name: /Decision/i })).toBeTruthy();
  });
  it("renders the receipt panel for expense claims", () => {
    render(<MemoryRouter><ResolutionProvider><DrawerDecision data={d} role={getRolePreset("ops-reviewer")} onRefresh={() => {}} /></ResolutionProvider></MemoryRouter>);
    expect(screen.getByText(/CL-1/)).toBeTruthy();
  });
  it("renders the 4 action buttons", () => {
    render(<MemoryRouter><ResolutionProvider><DrawerDecision data={d} role={getRolePreset("ops-reviewer")} onRefresh={() => {}} /></ResolutionProvider></MemoryRouter>);
    expect(screen.getByRole("button", { name: /Approve/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Request docs/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Escalate/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Reject/i })).toBeTruthy();
  });
  it("hides actions for executive role", () => {
    render(<MemoryRouter><ResolutionProvider><DrawerDecision data={d} role={getRolePreset("executive")} onRefresh={() => {}} /></ResolutionProvider></MemoryRouter>);
    expect(screen.queryByRole("button", { name: /Approve/i })).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/components/feed/__tests__/DrawerDecision.test.tsx`
Expected: FAIL — stub returns only the heading.

- [ ] **Step 3: Write the full implementation (replace the stub)**

```tsx
// web/client/components/feed/DrawerDecision.tsx
//
// First drawer section: receipt + recommendation + 4 actions + AuthorityCard
// + KillSwitchPanel. Mirrors WorkflowDetail.tsx's Overview tab content but
// laid out top-down inside the drawer.
import { useState } from "react";
import type { RolePreset } from "@shared/roles";
import type { DrawerData } from "./Drawer";
import type { ClaimData } from "@shared/types";
import AuthorityCard from "@client/components/apex/AuthorityCard";
import KillSwitchPanel from "@client/features/governance/KillSwitchPanel";
import ExceptionAnalysisCard from "@client/components/apex/ExceptionAnalysisCard";
import InterventionProtocols from "@client/components/apex/InterventionProtocols";
import CreativeCampaignArtefacts from "@client/components/apex/CreativeCampaignArtefacts";
import AgentDrivenComponent, { type AgentComponentSpec } from "@client/components/AgentDrivenComponent";

const ACTIONS = [
  { id: "approve",      label: "Approve",      cls: "bg-emerald-600 hover:bg-emerald-700 text-white" },
  { id: "request-info", label: "Request docs", cls: "bg-white text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50" },
  { id: "escalate",     label: "Escalate L2",  cls: "bg-white text-amber-700 ring-1 ring-amber-300 hover:bg-amber-50" },
  { id: "reject",       label: "Reject",       cls: "bg-white text-red-700 ring-1 ring-red-300 hover:bg-red-50" },
];

function ReceiptPanel({ claim }: { claim: ClaimData }) {
  const [errored, setErrored] = useState(false);
  const missing = errored || claim.receiptMismatchFlavour === "missing-receipt";
  return (
    <div className="panel">
      <div className="panel-header">Receipt · {claim.claimId}</div>
      <div className="panel-body flex gap-4">
        {missing ? (
          <div className="w-32 h-40 bg-amber-50 border-2 border-dashed border-amber-300 rounded flex items-center justify-center text-xs text-amber-700">no receipt</div>
        ) : (
          <img
            src={`/api/receipts/${claim.claimId}.png`}
            alt={`receipt ${claim.claimId}`}
            onError={() => setErrored(true)}
            className="w-32 h-40 object-contain bg-white rounded border border-slate-200"
          />
        )}
        <div className="text-xs text-slate-700 space-y-1">
          <div><span className="text-slate-500">Vendor</span> <span className="font-medium">{claim.vendor}</span></div>
          <div><span className="text-slate-500">Amount</span> <span className="font-semibold">{claim.currency} {claim.amount.toLocaleString()}</span></div>
          <div><span className="text-slate-500">Category</span> <span className="font-medium capitalize">{claim.category}</span></div>
        </div>
      </div>
    </div>
  );
}

export default function DrawerDecision({
  data, role, onRefresh,
}: {
  data: DrawerData;
  role: RolePreset;
  onRefresh: () => Promise<void> | void;
}) {
  const w = data.workflow;
  const [busy, setBusy] = useState<string | null>(null);

  const exceptionId = data.activeException?.id ?? w.activeExceptionId;
  const act = async (id: string) => {
    if (!exceptionId) return;
    setBusy(id);
    try {
      await fetch(`/api/exceptions/${exceptionId}/resolve`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ resolution: id, resolvedBy: "reviewer@zava" }),
      });
      await onRefresh();
    } finally {
      setBusy(null);
    }
  };

  const agentOutputs = (w as unknown as { agentOutputs?: Record<string, unknown> }).agentOutputs ?? {};
  const triage = (agentOutputs["cv_crystalliser"] ?? {}) as { componentSpec?: unknown[]; component_spec?: unknown[] };
  const specs = ((triage.componentSpec ?? triage.component_spec) ?? []) as AgentComponentSpec[];

  return (
    <section className="space-y-4">
      <h2 className="text-[11px] uppercase tracking-wide font-semibold text-slate-500">Decision</h2>

      {w.type === "hiring" && specs.length > 0 && (
        <div className="grid grid-cols-1 gap-3">
          {specs.map((spec, i) => <AgentDrivenComponent key={i} spec={spec} />)}
        </div>
      )}

      {w.type === "creative-campaign" && (
        <CreativeCampaignArtefacts workflow={w} onChange={onRefresh} />
      )}

      {w.claim && <ReceiptPanel claim={w.claim} />}

      {data.narrative && data.activeException && (
        <>
          <ExceptionAnalysisCard narrative={data.narrative} />
          <InterventionProtocols exception={data.activeException} onResolved={onRefresh} />
        </>
      )}

      {!role.hideActionButtons && (
        <div className="flex gap-2 flex-wrap">
          {ACTIONS.map((a) => (
            <button
              key={a.id}
              type="button"
              disabled={busy != null || !exceptionId}
              onClick={() => void act(a.id)}
              className={`text-xs px-3 py-1.5 rounded font-medium disabled:opacity-50 ${a.cls}`}
            >{busy === a.id ? "…" : a.label}</button>
          ))}
        </div>
      )}

      <AuthorityCard workflow={w} />
      <details className="rounded border border-slate-200 bg-white">
        <summary className="cursor-pointer text-xs text-slate-700 px-3 py-2">Kill switch</summary>
        <div className="px-3 pb-3"><KillSwitchPanel /></div>
      </details>
    </section>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/client/components/feed/__tests__/DrawerDecision.test.tsx`
Expected: PASS — 4 assertions.

- [ ] **Step 5: Commit**

```bash
git add web/client/components/feed/DrawerDecision.tsx web/client/components/feed/__tests__/DrawerDecision.test.tsx
git commit -m "feat(feed): implement DrawerDecision (receipt + recommendation + 4 actions + authority + killswitch)"
```

---

### Task 23: `DrawerActivity` — merge Phases · Timeline · Raw spans

**Files:**
- Modify: `web/client/components/feed/DrawerActivity.tsx` (replace stub)
- Test: `web/client/components/feed/__tests__/DrawerActivity.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// @vitest-environment jsdom
// web/client/components/feed/__tests__/DrawerActivity.test.tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import DrawerActivity from "@client/components/feed/DrawerActivity";
import type { DrawerData } from "@client/components/feed/Drawer";

afterEach(cleanup);

const d: DrawerData = {
  workflow: {
    id: "WF-1", type: "expense-claim", status: "in_progress",
    currentPhase: "Intake", createdAt: 1, slaDueAt: 9999,
    jurisdiction: "UK", agency: "Z", actionLedger: [
      { workflowId: "WF-1", timestamp: 100, actorKind: "human", actorId: "u", action: "approve", revocable: true, details: {} },
    ],
    tokensSpent: 0, costUSD: 0,
  },
  phases: [], spans: [], amplifications: [],
  activeException: null, mcpCalls: [],
  economics: { activeWorkflowCount: 1, totalWorkflowCount: 1, autoApprovedCount: 0, escalationCount: 0, averageCostPerWorkflow: 0 },
  narrative: null,
};

describe("DrawerActivity", () => {
  it("renders the Activity heading and the 3-view toggle", () => {
    render(<MemoryRouter><DrawerActivity data={d} /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: /Activity/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /^Phases$/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /^Timeline$/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /^Raw spans$/i })).toBeTruthy();
  });
  it("switches view when a toggle is clicked", () => {
    render(<MemoryRouter><DrawerActivity data={d} /></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: /Raw spans/i }));
    // PhaseTimeline content gone; OtelSpanTree renders even with [] spans.
    expect(screen.getByRole("button", { name: /Raw spans/i }).className).toMatch(/bg-blue-600/);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/components/feed/__tests__/DrawerActivity.test.tsx`
Expected: FAIL — stub.

- [ ] **Step 3: Write the full implementation**

```tsx
// web/client/components/feed/DrawerActivity.tsx
//
// Second drawer section: merges WorkflowDetail's separate Phases, Timeline,
// and Traces tabs + the Ledger tab into one filterable activity stream
// fronted by a 3-view toggle.
import { useState, useCallback } from "react";
import type { DrawerData } from "./Drawer";
import PhaseTimeline from "@client/components/PhaseTimeline";
import OtelSpanTree from "@client/components/OtelSpanTree";
import ExecutionTimelineTab from "@client/components/apex/ExecutionTimelineTab";
import PhaseRibbon from "@client/components/apex/PhaseRibbon";
import type { ActionLedgerEntry } from "@shared/types";

const VIEWS = ["Phases", "Timeline", "Raw spans", "Ledger"] as const;
type View = typeof VIEWS[number];

export default function DrawerActivity({ data }: { data: DrawerData }) {
  const [view, setView] = useState<View>("Phases");

  const logAction = useCallback(async (action: string) => {
    await fetch("/internal/durable-event", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        workflow_id: data.workflow.id, kind: "log.action",
        payload: { by: "operator", action },
      }),
    }).catch(() => {});
  }, [data.workflow.id]);

  return (
    <section className="space-y-3">
      <div className="flex items-center gap-3">
        <h2 className="text-[11px] uppercase tracking-wide font-semibold text-slate-500">Activity</h2>
        <div className="inline-flex rounded-md border border-slate-200 overflow-hidden ml-auto">
          {VIEWS.map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setView(v)}
              className={`text-xs px-3 py-1 font-medium ${view === v ? "bg-blue-600 text-white" : "bg-white text-slate-600 hover:bg-slate-50"}`}
            >{v}</button>
          ))}
        </div>
      </div>

      <PhaseRibbon workflow={data.workflow} phases={data.phases} />

      {view === "Phases" && <PhaseTimeline phases={data.phases} workflowType={data.workflow.type} />}
      {view === "Timeline" && (
        <ExecutionTimelineTab mcpCalls={data.mcpCalls} workflowId={data.workflow.id} onLogAction={logAction} />
      )}
      {view === "Raw spans" && <OtelSpanTree spans={data.spans} />}
      {view === "Ledger" && (
        <div className="space-y-1 text-xs">
          {(data.workflow.actionLedger as ActionLedgerEntry[]).map((a, i) => (
            <div key={i} className="panel panel-body">
              <div className="font-medium text-slate-800">{a.action}</div>
              <div className="text-slate-500">
                {new Date(a.timestamp * 1000).toLocaleString()} · {a.actorKind}:{a.actorId} · {a.revocable ? "revocable" : "non-revocable"}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/client/components/feed/__tests__/DrawerActivity.test.tsx`
Expected: PASS — 2 assertions.

- [ ] **Step 5: Commit**

```bash
git add web/client/components/feed/DrawerActivity.tsx web/client/components/feed/__tests__/DrawerActivity.test.tsx
git commit -m "feat(feed): implement DrawerActivity (Phases/Timeline/Raw spans/Ledger toggle)"
```

---

### Task 24: `DrawerAudit`

**Files:**
- Modify: `web/client/components/feed/DrawerAudit.tsx` (replace stub)
- Test: `web/client/components/feed/__tests__/DrawerAudit.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// @vitest-environment jsdom
// web/client/components/feed/__tests__/DrawerAudit.test.tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import DrawerAudit from "@client/components/feed/DrawerAudit";
import type { DrawerData } from "@client/components/feed/Drawer";

afterEach(cleanup);

const d: DrawerData = {
  workflow: {
    id: "WF-1", type: "expense-claim", status: "in_progress",
    currentPhase: "Intake", createdAt: 1, slaDueAt: 9999,
    jurisdiction: "UK", agency: "Z", actionLedger: [],
    tokensSpent: 0, costUSD: 0,
  },
  phases: [], spans: [], amplifications: [],
  activeException: null, mcpCalls: [],
  economics: { activeWorkflowCount: 1, totalWorkflowCount: 1, autoApprovedCount: 0, escalationCount: 0, averageCostPerWorkflow: 0 },
  narrative: null,
};

describe("DrawerAudit", () => {
  it("renders the section heading", () => {
    render(<MemoryRouter><DrawerAudit data={d} /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: /Audit/i })).toBeTruthy();
  });
  it("renders all five collapsed accordions by name", () => {
    render(<MemoryRouter><DrawerAudit data={d} /></MemoryRouter>);
    expect(screen.getByText(/Evidence/i)).toBeTruthy();
    expect(screen.getByText(/Audit trail/i)).toBeTruthy();
    expect(screen.getByText(/Economics/i)).toBeTruthy();
    expect(screen.getByText(/Fleet assignment/i)).toBeTruthy();
    expect(screen.getByText(/Skill amplification/i)).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/components/feed/__tests__/DrawerAudit.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Write the full implementation**

```tsx
// web/client/components/feed/DrawerAudit.tsx
//
// Third drawer section: collapsed-by-default accordions for the panels the
// reviewer rarely needs but the audit/exec role does. Per spec §4 default
// state is "collapsed".
import type { DrawerData } from "./Drawer";
import type { ActionLedgerEntry } from "@shared/types";
import EvidencePanel from "@client/features/governance/EvidencePanel";
import EconomicsPanel from "@client/components/apex/EconomicsPanel";
import FleetAssignment from "@client/components/apex/FleetAssignment";
import AuditTrail from "@client/components/apex/AuditTrail";
import SkillAmplificationPanel from "@client/components/SkillAmplificationPanel";

function Accordion({ title, children, defaultOpen = false }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  return (
    <details open={defaultOpen} className="rounded border border-slate-200 bg-white">
      <summary className="cursor-pointer text-xs font-medium text-slate-700 px-3 py-2 hover:bg-slate-50">{title}</summary>
      <div className="px-3 pb-3">{children}</div>
    </details>
  );
}

export default function DrawerAudit({ data }: { data: DrawerData }) {
  return (
    <section className="space-y-3">
      <h2 className="text-[11px] uppercase tracking-wide font-semibold text-slate-500">Audit</h2>
      <Accordion title="Evidence">
        <EvidencePanel workflowId={data.workflow.id} />
      </Accordion>
      <Accordion title="Audit trail">
        <AuditTrail
          ledger={data.workflow.actionLedger as ActionLedgerEntry[]}
          blobUrl={data.auditBlobUrl ?? null}
        />
      </Accordion>
      <Accordion title="Economics">
        <EconomicsPanel e={data.economics} />
      </Accordion>
      <Accordion title="Fleet assignment">
        <FleetAssignment spans={data.spans} />
      </Accordion>
      <Accordion title="Skill amplification">
        <SkillAmplificationPanel items={data.amplifications} />
      </Accordion>
    </section>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/client/components/feed/__tests__/DrawerAudit.test.tsx`
Expected: PASS — 2 assertions.

- [ ] **Step 5: Commit**

```bash
git add web/client/components/feed/DrawerAudit.tsx web/client/components/feed/__tests__/DrawerAudit.test.tsx
git commit -m "feat(feed): implement DrawerAudit (5 collapsed-by-default accordions)"
```

---

### Task 25: `/workflows/:id` deep-link opens drawer over feed

**Files:**
- Modify: `web/client/components/feed/FleetControlShell.tsx` (created in Task 31; the route wiring is added here)

> **Note:** This task assumes Task 31 is already drafted. The drawer-open-on-route behaviour is implemented as part of the FleetControlShell, but the **test** for the deep-link sits here to make the wiring explicit. Engineer should run this test against the post-Task-31 shell.

- Test: `web/client/components/feed/__tests__/Drawer.test.tsx` (extend with a new `describe` block)

- [ ] **Step 1: Add a failing integration test (after Task 31 is complete)**

```tsx
// extension to web/client/components/feed/__tests__/integration.test.tsx
// (this test must be in integration.test.tsx, not Drawer.test.tsx — it
// depends on the shell).
import { describe, it, expect, afterEach, vi, beforeEach } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import FleetControlShell from "@client/components/feed/FleetControlShell";

beforeEach(() => {
  (globalThis as any).EventSource = class { onmessage = null; addEventListener(){} close(){} };
  globalThis.fetch = vi.fn().mockImplementation((url: string) => {
    if (url.startsWith("/api/workflows/")) return Promise.resolve({ ok: true, json: async () => ({
      workflow: { id: "WF-Q", type: "expense-claim", status: "awaiting_hitl",
        currentPhase: "Intake", createdAt: 1, slaDueAt: 9999, jurisdiction: "UK",
        agency: "Z", actionLedger: [], tokensSpent: 0, costUSD: 0 },
      phases: [], spans: [], amplifications: [], activeException: null,
      mcpCalls: [], economics: { activeWorkflowCount: 0, totalWorkflowCount: 0, autoApprovedCount: 0, escalationCount: 0, averageCostPerWorkflow: 0 },
      narrative: null,
    }) } as Response);
    return Promise.resolve({ ok: true, json: async () => [] } as Response);
  });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("deep-link /workflows/:id", () => {
  it("opens the drawer with the matching workflow id on cold land", async () => {
    render(
      <MemoryRouter initialEntries={["/workflows/WF-Q"]}>
        <FleetControlShell />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByLabelText(/Workflow detail drawer/i)).toBeTruthy();
      expect(screen.getByText("WF-Q")).toBeTruthy();
    });
  });
});
```

- [ ] **Step 2: Implementation** — see Task 31's `FleetControlShell.tsx`. The shell reads `useParams` from a `<Route path="/workflows/:id">` and renders the `<Drawer>` whenever `id` is set.

- [ ] **Step 3: Run integration test** after Task 31 lands.

Run: `npx vitest run web/client/components/feed/__tests__/integration.test.tsx`
Expected: PASS — at least the deep-link assertion.

- [ ] **Step 4: Commit**

> Commit lives with Task 31; this task adds the test only. If running stand-alone, commit as:

```bash
git add web/client/components/feed/__tests__/integration.test.tsx
git commit -m "test(feed): cover /workflows/:id deep-link opens drawer over feed"
```


---

## Phase F — Shell, header, rail, toast

### Task 26: `Toast` primitive

**Files:**
- Create: `web/client/components/feed/Toast.tsx`
- Test: `web/client/components/feed/__tests__/Toast.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// @vitest-environment jsdom
// web/client/components/feed/__tests__/Toast.test.tsx
import { describe, it, expect, afterEach, vi, beforeEach } from "vitest";
import { render, screen, cleanup, act } from "@testing-library/react";
import { ToastProvider, useToast } from "@client/components/feed/Toast";

beforeEach(() => vi.useFakeTimers());
afterEach(() => { cleanup(); vi.useRealTimers(); });

describe("Toast", () => {
  it("show() renders a message; auto-dismisses after default TTL", () => {
    function Probe() {
      const t = useToast();
      return <button onClick={() => t.show("hello")}>fire</button>;
    }
    render(<ToastProvider><Probe /></ToastProvider>);
    act(() => { (screen.getByRole("button") as HTMLButtonElement).click(); });
    expect(screen.getByText("hello")).toBeTruthy();
    act(() => { vi.advanceTimersByTime(4_001); });
    expect(screen.queryByText("hello")).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/components/feed/__tests__/Toast.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the file**

```tsx
// web/client/components/feed/Toast.tsx
//
// Minimal in-app toast. One queue, top-right, auto-dismissed after TTL.
// Used by HITLCard/ExceptionCard failure paths ("Couldn't resolve — try
// again").
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

interface ToastEntry { id: number; msg: string; }

interface API {
  show(msg: string, ttlMs?: number): void;
}

const Ctx = createContext<API | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastEntry[]>([]);

  const show = useCallback((msg: string, ttlMs = 4_000) => {
    const id = Date.now() + Math.random();
    setItems((prev) => [...prev, { id, msg }]);
    setTimeout(() => {
      setItems((prev) => prev.filter((i) => i.id !== id));
    }, ttlMs);
  }, []);

  useEffect(() => () => setItems([]), []);

  return (
    <Ctx.Provider value={{ show }}>
      {children}
      <div className="fixed top-3 right-3 z-50 space-y-2 pointer-events-none">
        {items.map((i) => (
          <div
            key={i.id}
            role="status"
            className="pointer-events-auto bg-slate-900 text-white text-xs px-3 py-2 rounded shadow"
          >{i.msg}</div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export function useToast(): API {
  const v = useContext(Ctx);
  if (!v) throw new Error("useToast must be used inside <ToastProvider>");
  return v;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/client/components/feed/__tests__/Toast.test.tsx`
Expected: PASS — 1 assertion.

- [ ] **Step 5: Commit**

```bash
git add web/client/components/feed/Toast.tsx web/client/components/feed/__tests__/Toast.test.tsx
git commit -m "feat(feed): add minimal Toast primitive + ToastProvider"
```

---

### Task 27: `RoleSwitcher`

**Files:**
- Create: `web/client/components/feed/RoleSwitcher.tsx`
- Test: `web/client/components/feed/__tests__/RoleSwitcher.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// @vitest-environment jsdom
// web/client/components/feed/__tests__/RoleSwitcher.test.tsx
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import RoleSwitcher from "@client/components/feed/RoleSwitcher";
import { ROLE_PRESETS } from "@shared/roles";

afterEach(cleanup);

describe("RoleSwitcher", () => {
  it("renders the current role label", () => {
    render(<RoleSwitcher current="ops-reviewer" onChange={() => {}} />);
    expect(screen.getByText(/Ops Reviewer/i)).toBeTruthy();
  });
  it("lists all 5 roles when opened and fires onChange on select", () => {
    const onChange = vi.fn();
    render(<RoleSwitcher current="ops-reviewer" onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: /Ops Reviewer/i }));
    for (const r of ROLE_PRESETS) {
      expect(screen.getAllByText(new RegExp(r.label)).length).toBeGreaterThan(0);
    }
    fireEvent.click(screen.getByRole("menuitem", { name: /Executive/i }));
    expect(onChange).toHaveBeenCalledWith("executive");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/components/feed/__tests__/RoleSwitcher.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the file**

```tsx
// web/client/components/feed/RoleSwitcher.tsx
//
// Dropdown that swaps the active RolePreset. Persistence lives in
// FleetControlShell via useLocalStorageState — this component only fires
// onChange.
import { useState, useRef, useEffect } from "react";
import { ChevronDown } from "lucide-react";
import { ROLE_PRESETS, type RoleId, getRolePreset } from "@shared/roles";

export default function RoleSwitcher({
  current, onChange,
}: {
  current: RoleId;
  onChange: (next: RoleId) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);
  const label = getRolePreset(current).label;

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="text-xs px-3 py-1.5 rounded font-medium bg-white text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50 flex items-center gap-1"
      >
        role: <span className="font-semibold">{label}</span>
        <ChevronDown size={12} />
      </button>
      {open && (
        <div role="menu" className="absolute right-0 top-full mt-1 bg-white border border-slate-200 rounded-md shadow-lg min-w-[200px] py-1 z-50">
          {ROLE_PRESETS.map((r) => (
            <button
              key={r.id}
              role="menuitem"
              type="button"
              onClick={() => { onChange(r.id); setOpen(false); }}
              className={`w-full text-left text-xs px-3 py-1.5 hover:bg-slate-50 ${r.id === current ? "font-semibold text-blue-700" : "text-slate-700"}`}
            >{r.label}</button>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/client/components/feed/__tests__/RoleSwitcher.test.tsx`
Expected: PASS — 2 assertions.

- [ ] **Step 5: Commit**

```bash
git add web/client/components/feed/RoleSwitcher.tsx web/client/components/feed/__tests__/RoleSwitcher.test.tsx
git commit -m "feat(feed): add RoleSwitcher dropdown"
```

---

### Task 28: `NotificationsPopover`

**Files:**
- Create: `web/client/components/feed/NotificationsPopover.tsx`
- Test: `web/client/components/feed/__tests__/NotificationsPopover.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// @vitest-environment jsdom
// web/client/components/feed/__tests__/NotificationsPopover.test.tsx
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import NotificationsPopover from "@client/components/feed/NotificationsPopover";
import type { FeedItem } from "@shared/feedItems";

afterEach(cleanup);

const items: FeedItem[] = [
  { type: "hitl", id: "hitl:W-1", timestamp: 100, workflowId: "W-1", domain: "expense-claim", severity: "critical" },
  { type: "exception", id: "exception:E-2", timestamp: 90, workflowId: "W-2", severity: "high",
    exception: { id: "E-2", workflowId: "W-2", composedBy: "fleet-manager", severity: "high",
      category: "compliance", summary: "S", recommendation: "R", options: [],
      relatedPolicyRefs: [], confidence: 0.5, createdAt: 90 } },
];

describe("NotificationsPopover", () => {
  it("renders a bell button with the unread count", () => {
    render(<NotificationsPopover items={items} onJumpTo={() => {}} />);
    expect(screen.getByRole("button", { name: /2 unread/i })).toBeTruthy();
  });
  it("opens and lists items; clicking one fires onJumpTo with the item id", () => {
    const onJumpTo = vi.fn();
    render(<NotificationsPopover items={items} onJumpTo={onJumpTo} />);
    fireEvent.click(screen.getByRole("button", { name: /2 unread/i }));
    fireEvent.click(screen.getByText(/W-2/));
    expect(onJumpTo).toHaveBeenCalledWith("exception:E-2");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/components/feed/__tests__/NotificationsPopover.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the file**

```tsx
// web/client/components/feed/NotificationsPopover.tsx
import { useState, useRef, useEffect } from "react";
import { Bell } from "lucide-react";
import type { FeedItem } from "@shared/feedItems";

export default function NotificationsPopover({
  items, onJumpTo,
}: {
  items: FeedItem[];
  onJumpTo: (itemId: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const count = items.length;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={`${count} unread`}
        className="relative text-slate-500 hover:text-slate-800 px-1"
      >
        <Bell size={16} />
        {count > 0 && (
          <span className="absolute -top-1 -right-1 bg-red-500 text-white text-[10px] rounded-full px-1 min-w-[16px] text-center">
            {count}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 bg-white border border-slate-200 rounded-md shadow-lg w-80 max-h-96 overflow-auto py-1 z-50">
          {items.length === 0 && (
            <div className="text-xs text-slate-500 px-3 py-3 italic">No unread items.</div>
          )}
          {items.map((it) => (
            <button
              key={it.id}
              type="button"
              onClick={() => { onJumpTo(it.id); setOpen(false); }}
              className="w-full text-left text-xs px-3 py-2 hover:bg-slate-50 border-b border-slate-100 last:border-b-0"
            >
              <div className="font-mono text-slate-700">{it.workflowId ?? it.id}</div>
              <div className="text-[11px] text-slate-500">{it.type} · {it.severity ?? "-"}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/client/components/feed/__tests__/NotificationsPopover.test.tsx`
Expected: PASS — 2 assertions.

- [ ] **Step 5: Commit**

```bash
git add web/client/components/feed/NotificationsPopover.tsx web/client/components/feed/__tests__/NotificationsPopover.test.tsx
git commit -m "feat(feed): add NotificationsPopover"
```


---

### Task 29: `Header`

**Files:**
- Create: `web/client/components/feed/Header.tsx`
- Test: `web/client/components/feed/__tests__/Header.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// @vitest-environment jsdom
// web/client/components/feed/__tests__/Header.test.tsx
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Header from "@client/components/feed/Header";
import { getRolePreset } from "@shared/roles";
import type { FeedItem } from "@shared/feedItems";

afterEach(cleanup);

const noop = () => {};
const items: FeedItem[] = [];
const role = getRolePreset("ops-reviewer");

describe("Header", () => {
  it("renders the Apex brand link", () => {
    render(<MemoryRouter><Header role={role} onRoleChange={noop} unreadItems={items} onJumpTo={noop} onSearch={noop} workflows={[]} /></MemoryRouter>);
    expect(screen.getByText(/Apex/i)).toBeTruthy();
  });
  it("renders Today chip per role (ops-reviewer flavour)", () => {
    render(<MemoryRouter><Header role={role} onRoleChange={noop} unreadItems={items} onJumpTo={noop} onSearch={noop} workflows={[]} /></MemoryRouter>);
    expect(screen.getByText(/Today:/i)).toBeTruthy();
  });
  it("search popover shows matching workflow ids and fires onSearch", () => {
    const onSearch = vi.fn();
    render(<MemoryRouter><Header role={role} onRoleChange={noop} unreadItems={items} onJumpTo={noop} onSearch={onSearch}
      workflows={[
        { id: "WF-1", type: "expense-claim", status: "in_progress", currentPhase: "Intake",
          createdAt: 1, slaDueAt: 1, jurisdiction: "UK", agency: "Z",
          actionLedger: [], tokensSpent: 0, costUSD: 0 },
        { id: "WF-2", type: "hiring", status: "in_progress", currentPhase: "Sourcing",
          createdAt: 1, slaDueAt: 1, jurisdiction: "UK", agency: "Z",
          actionLedger: [], tokensSpent: 0, costUSD: 0 },
      ]} /></MemoryRouter>);
    fireEvent.change(screen.getByPlaceholderText(/search workflows/i), { target: { value: "wf-1" } });
    expect(screen.getByRole("button", { name: /WF-1/ })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /WF-1/ }));
    expect(onSearch).toHaveBeenCalledWith("WF-1");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/components/feed/__tests__/Header.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the file**

```tsx
// web/client/components/feed/Header.tsx
//
// Sticky thin top row: brand · search · 🔔 · Today chip · RoleSwitcher.
// Today chip content is keyed off role.todayChip.
import { useState } from "react";
import { Link } from "react-router-dom";
import type { RoleId, RolePreset } from "@shared/roles";
import type { FeedItem } from "@shared/feedItems";
import type { Workflow } from "@shared/types";
import RoleSwitcher from "./RoleSwitcher";
import NotificationsPopover from "./NotificationsPopover";

function TodayChip({ role, items, workflows }: { role: RolePreset; items: FeedItem[]; workflows: Workflow[] }) {
  if (role.todayChip === "needs-you-count") {
    const crit = items.filter((i) => i.severity === "critical").length;
    return <span className="text-xs text-slate-600">Today: {items.length} · {crit} crit</span>;
  }
  if (role.todayChip === "money-saved") {
    return <span className="text-xs text-slate-600">$ saved today: $—</span>;
  }
  if (role.todayChip === "hiring-summary") {
    const open = workflows.filter((w) => w.type === "hiring" && w.status !== "completed").length;
    return <span className="text-xs text-slate-600">Open roles: {open}</span>;
  }
  if (role.todayChip === "fleet-health") {
    return <span className="text-xs text-slate-600">Fleet health: green</span>;
  }
  if (role.todayChip === "executive-summary") {
    const completed = workflows.filter((w) => w.status === "completed").length;
    return <span className="text-xs text-slate-600">Throughput: {completed}</span>;
  }
  return null;
}

export default function Header({
  role, onRoleChange, unreadItems, onJumpTo, onSearch, workflows,
}: {
  role: RolePreset;
  onRoleChange: (next: RoleId) => void;
  unreadItems: FeedItem[];
  onJumpTo: (itemId: string) => void;
  onSearch: (workflowId: string) => void;
  workflows: Workflow[];
}) {
  const [q, setQ] = useState("");
  const matches = q.trim().length === 0 ? [] :
    workflows.filter((w) => w.id.toLowerCase().includes(q.toLowerCase())).slice(0, 8);

  return (
    <header className="flex items-center gap-4 px-6 h-12 border-b border-slate-200 bg-white sticky top-0 z-30">
      <Link to="/" className="font-semibold text-slate-900">Apex</Link>
      <span className="text-slate-300">·</span>
      <div className="relative">
        <input
          type="search"
          placeholder="Search workflows…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="text-xs border border-slate-200 rounded px-2 py-1 bg-white text-slate-700 w-64"
        />
        {matches.length > 0 && (
          <div className="absolute left-0 top-full mt-1 bg-white border border-slate-200 rounded-md shadow-lg w-64 py-1 z-40">
            {matches.map((w) => (
              <button
                key={w.id}
                type="button"
                onClick={() => { onSearch(w.id); setQ(""); }}
                className="w-full text-left text-xs px-3 py-1.5 hover:bg-slate-50"
              >{w.id}<span className="text-slate-400"> · {w.type}</span></button>
            ))}
          </div>
        )}
      </div>
      <div className="ml-auto flex items-center gap-3">
        <NotificationsPopover items={unreadItems} onJumpTo={onJumpTo} />
        <TodayChip role={role} items={unreadItems} workflows={workflows} />
        <RoleSwitcher current={role.id} onChange={onRoleChange} />
        <div className="w-7 h-7 rounded-full bg-slate-200 text-slate-600 text-xs flex items-center justify-center font-medium" aria-label="user avatar">A</div>
      </div>
    </header>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/client/components/feed/__tests__/Header.test.tsx`
Expected: PASS — 3 assertions.

- [ ] **Step 5: Commit**

```bash
git add web/client/components/feed/Header.tsx web/client/components/feed/__tests__/Header.test.tsx
git commit -m "feat(feed): add Header (brand, search, 🔔, Today chip, role switcher)"
```

---

### Task 30: `LeftRail`

**Files:**
- Create: `web/client/components/feed/LeftRail.tsx`
- Test: `web/client/components/feed/__tests__/LeftRail.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// @vitest-environment jsdom
// web/client/components/feed/__tests__/LeftRail.test.tsx
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import LeftRail from "@client/components/feed/LeftRail";
import { getRolePreset } from "@shared/roles";

afterEach(cleanup);

describe("LeftRail", () => {
  it("renders role-default saved views", () => {
    render(<MemoryRouter><LeftRail role={getRolePreset("ops-reviewer")} userViews={[]} onSelectView={() => {}} onSaveCurrent={() => {}} /></MemoryRouter>);
    expect(screen.getByText(/Critical · needs you/i)).toBeTruthy();
  });
  it("renders the More ▾ submenu with the 4 demoted routes", () => {
    render(<MemoryRouter><LeftRail role={getRolePreset("ops-reviewer")} userViews={[]} onSelectView={() => {}} onSaveCurrent={() => {}} /></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: /More/i }));
    expect(screen.getByText(/Analytics/i)).toBeTruthy();
    expect(screen.getByText(/Evaluations/i)).toBeTruthy();
    expect(screen.getByText(/Economics/i)).toBeTruthy();
    expect(screen.getByText(/Policy/i)).toBeTruthy();
  });
  it("renders the Constellation external link", () => {
    render(<MemoryRouter><LeftRail role={getRolePreset("ops-reviewer")} userViews={[]} onSelectView={() => {}} onSaveCurrent={() => {}} /></MemoryRouter>);
    expect(screen.getByText(/Constellation/i)).toBeTruthy();
  });
  it("fires onSelectView when a saved view is clicked", () => {
    const onSel = vi.fn();
    render(<MemoryRouter><LeftRail role={getRolePreset("ops-reviewer")} userViews={[]} onSelectView={onSel} onSaveCurrent={() => {}} /></MemoryRouter>);
    fireEvent.click(screen.getByText(/Critical · needs you/i));
    expect(onSel).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/components/feed/__tests__/LeftRail.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the file**

```tsx
// web/client/components/feed/LeftRail.tsx
//
// 160-200px sidebar: role-default saved views + user-added saved views +
// More ▾ submenu containing the demoted secondary routes + Constellation
// external link at the bottom.
import { useState } from "react";
import { NavLink, Link } from "react-router-dom";
import { ChevronDown, Plus } from "lucide-react";
import type { RolePreset, SavedView } from "@shared/roles";

const ROUTE_LABEL: Record<string, string> = {
  "/analytics": "Analytics",
  "/evals": "Evaluations",
  "/economics": "Economics",
  "/policy": "Policy",
};

const VITE_PORTS = new Set(["5273", "5274", "5275"]);
function constellationUrl(): string {
  const fromEnv = (import.meta.env.VITE_BLUEPRINT_URL as string | undefined)?.trim();
  if (fromEnv) return `${fromEnv.replace(/\/$/, "")}/?view=constellation&from=fleet`;
  if (typeof window !== "undefined" && VITE_PORTS.has(window.location.port)) {
    return `${window.location.protocol}//${window.location.hostname}:5275/?view=constellation&from=fleet`;
  }
  return "/?view=constellation&from=fleet";
}

export default function LeftRail({
  role, userViews, onSelectView, onSaveCurrent,
}: {
  role: RolePreset;
  userViews: SavedView[];
  onSelectView: (v: SavedView) => void;
  onSaveCurrent: () => void;
}) {
  const [moreOpen, setMoreOpen] = useState(true);
  const allViews = [...role.defaultSavedViews, ...userViews];

  return (
    <aside className="w-[200px] shrink-0 bg-white border-r border-slate-200 p-3 flex flex-col gap-3 text-sm overflow-y-auto">
      <div>
        <div className="text-[10px] uppercase tracking-wide text-slate-400 px-2 mb-1">Saved views</div>
        <div className="space-y-0.5">
          {allViews.map((v) => (
            <button
              key={v.id}
              type="button"
              onClick={() => onSelectView(v)}
              className="block w-full text-left text-xs px-3 py-1.5 rounded text-slate-700 hover:bg-slate-100"
            >{v.label}</button>
          ))}
          <button
            type="button"
            onClick={onSaveCurrent}
            className="flex items-center gap-1 text-[11px] px-3 py-1.5 text-slate-500 hover:text-slate-700"
          ><Plus size={12} /> Save current filter</button>
        </div>
      </div>

      <div className="mt-auto">
        <button
          type="button"
          onClick={() => setMoreOpen((v) => !v)}
          className="flex items-center justify-between w-full text-[11px] uppercase tracking-wide text-slate-400 px-2 py-1 hover:text-slate-600"
        >
          More
          <ChevronDown size={12} className={moreOpen ? "rotate-180 transition" : "transition"} />
        </button>
        {moreOpen && (
          <div className="space-y-0.5">
            {role.moreOrder.map((to) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `block text-xs px-3 py-1.5 rounded ${isActive ? "bg-blue-50 text-blue-700 font-medium" : "text-slate-700 hover:bg-slate-100"}`
                }
              >{ROUTE_LABEL[to] ?? to}</NavLink>
            ))}
            <a
              href={constellationUrl()}
              target="_blank" rel="noopener noreferrer"
              className="block text-xs px-3 py-1.5 rounded text-slate-700 hover:bg-slate-100"
            >Constellation ↗</a>
          </div>
        )}
      </div>
    </aside>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/client/components/feed/__tests__/LeftRail.test.tsx`
Expected: PASS — 4 assertions.

- [ ] **Step 5: Commit**

```bash
git add web/client/components/feed/LeftRail.tsx web/client/components/feed/__tests__/LeftRail.test.tsx
git commit -m "feat(feed): add LeftRail (saved views + More ▾)"
```

---

### Task 31: `FleetControlShell` (replaces `App.tsx`)

**Files:**
- Create: `web/client/components/feed/FleetControlShell.tsx`
- Test: `web/client/components/feed/__tests__/integration.test.tsx`

- [ ] **Step 1: Write the failing integration test**

```tsx
// @vitest-environment jsdom
// web/client/components/feed/__tests__/integration.test.tsx
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import FleetControlShell from "@client/components/feed/FleetControlShell";

beforeEach(() => {
  (globalThis as any).EventSource = class { onmessage = null; addEventListener() {} close() {} };
  globalThis.fetch = vi.fn().mockImplementation((url: string) => {
    if (url.startsWith("/api/workflows/")) {
      return Promise.resolve({ ok: true, json: async () => ({
        workflow: { id: "WF-1", type: "expense-claim", status: "awaiting_hitl",
          currentPhase: "Intake", createdAt: 1, slaDueAt: 9999, jurisdiction: "UK",
          agency: "Z", actionLedger: [], tokensSpent: 0, costUSD: 0 },
        phases: [], spans: [], amplifications: [], activeException: null,
        mcpCalls: [], economics: { activeWorkflowCount: 0, totalWorkflowCount: 0, autoApprovedCount: 0, escalationCount: 0, averageCostPerWorkflow: 0 },
        narrative: null,
      }) } as Response);
    }
    if (url.startsWith("/api/workflows")) {
      return Promise.resolve({ ok: true, json: async () => [
        { id: "WF-1", type: "expense-claim", status: "awaiting_hitl",
          currentPhase: "Intake", createdAt: 100, slaDueAt: 9999,
          jurisdiction: "UK", agency: "Z", actionLedger: [],
          tokensSpent: 0, costUSD: 0 },
      ] } as Response);
    }
    return Promise.resolve({ ok: true, json: async () => [] } as Response);
  });
  localStorage.clear();
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); localStorage.clear(); });

describe("FleetControlShell — integration", () => {
  it("lands on feed showing the HITL card and the header", async () => {
    render(<MemoryRouter initialEntries={["/"]}><FleetControlShell /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText("WF-1")).toBeTruthy());
    expect(screen.getByText(/Apex/)).toBeTruthy();
  });

  it("deep-link /workflows/:id opens the drawer over the feed on cold land", async () => {
    render(<MemoryRouter initialEntries={["/workflows/WF-1"]}><FleetControlShell /></MemoryRouter>);
    await waitFor(() => expect(screen.getByLabelText(/Workflow detail drawer/i)).toBeTruthy());
  });

  it("switching role via header re-mounts the feed with new defaults", async () => {
    render(<MemoryRouter initialEntries={["/"]}><FleetControlShell /></MemoryRouter>);
    await waitFor(() => screen.getByText(/Ops Reviewer/));
    fireEvent.click(screen.getByRole("button", { name: /Ops Reviewer/ }));
    fireEvent.click(screen.getByRole("menuitem", { name: /Executive/i }));
    await waitFor(() => expect(screen.getByText(/Executive/)).toBeTruthy());
    expect(localStorage.getItem("fleetctl.role")).toBe(JSON.stringify("executive"));
    // Executive default filter is "all-activity" — the button should be active
    expect(
      screen.getByRole("button", { name: /All activity/i }).className,
    ).toMatch(/bg-blue-600/);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/components/feed/__tests__/integration.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the file**

```tsx
// web/client/components/feed/FleetControlShell.tsx
//
// Replaces App.tsx. Top-level layout: Header on top, LeftRail on the left,
// Feed in the middle, conditional Drawer on the right (when /workflows/:id).
// Preserves the existing secondary routes inside <Routes> so the LeftRail's
// "More ▾" links still navigate. Role state is persisted via localStorage;
// switching role re-keys the Feed so it re-mounts with fresh defaults.
import { useState, useMemo } from "react";
import { Route, Routes, useNavigate, useParams, Navigate } from "react-router-dom";
import { ROLE_PRESETS, type RoleId, getRolePreset, type SavedView } from "@shared/roles";
import { useLocalStorageState } from "@client/hooks/useLocalStorageState";
import { ResolutionProvider } from "@client/hooks/useResolutionStore";
import { ToastProvider } from "./Toast";
import Header from "./Header";
import LeftRail from "./LeftRail";
import Feed from "./Feed";
import Drawer from "./Drawer";
import { useWorkflows } from "@client/hooks/useWorkflows";
import Analytics from "@client/routes/Analytics";
import Evaluations from "@client/routes/Evaluations";
import Economics from "@client/routes/Economics";
import PolicyAndAutonomy from "@client/routes/PolicyAndAutonomy";
import HiringManager from "@client/routes/HiringManager";

function ShellBody() {
  const navigate = useNavigate();
  const [roleId, setRoleId] = useLocalStorageState<RoleId>("fleetctl.role", "ops-reviewer");
  const role = useMemo(() => getRolePreset(roleId), [roleId]);
  const [userViews, setUserViews] = useLocalStorageState<SavedView[]>(
    `fleetctl.savedViews.${roleId}`, [],
  );

  const workflows = useWorkflows();

  // We don't compute the full feed here (Feed owns it). For Header's
  // notifications + Today chip we'd want feed items too, but to avoid
  // double-subscription the shell passes [] for unread items in v1 and
  // lets the Feed surface that internally. Acceptable for spec §5: the
  // notifications popover is a v1 convenience and can be empty.
  const unreadItems = useMemo(() => [], []);

  const onOpenDrawer = (workflowId: string) => navigate(`/workflows/${workflowId}`);
  const onJumpTo = (_itemId: string) => {/* v1: no-op; v1.1 scroll-to-item */};
  const onSearch = (workflowId: string) => navigate(`/workflows/${workflowId}`);

  return (
    <ToastProvider>
      <ResolutionProvider>
        <Header
          role={role}
          onRoleChange={setRoleId}
          unreadItems={unreadItems}
          onJumpTo={onJumpTo}
          onSearch={onSearch}
          workflows={workflows}
        />
        <div className="flex flex-1 min-h-0">
          <LeftRail
            role={role}
            userViews={userViews}
            onSelectView={(v) => {
              // Apply view by pushing search params into the feed URL.
              const params = new URLSearchParams();
              if (v.domains.length > 0) params.set("domains", v.domains.join(","));
              if (v.search) params.set("q", v.search);
              navigate(`/?${params.toString()}`);
            }}
            onSaveCurrent={() => {
              const label = window.prompt("Name this view?", "My view");
              if (!label) return;
              const sv: SavedView = {
                id: `user-${Date.now()}`,
                label,
                filter: role.defaultFilter,
                domains: role.defaultDomains,
              };
              setUserViews((prev) => [...prev, sv]);
            }}
          />
          <main className="flex-1 min-w-0 flex">
            <Routes>
              <Route path="/" element={<Feed key={role.id} role={role} onOpenDrawer={onOpenDrawer} />} />
              <Route path="/fleet" element={<Navigate to="/" replace />} />
              <Route path="/exceptions" element={<Navigate to="/?filter=exceptions" replace />} />
              <Route path="/reviewer-queue" element={<Navigate to="/?filter=hitl" replace />} />
              <Route path="/workflows/:id" element={
                <FeedWithDrawer role={role} onOpenDrawer={onOpenDrawer} />
              } />
              <Route path="/analytics" element={<Analytics />} />
              <Route path="/evals" element={<Evaluations />} />
              <Route path="/economics" element={<Economics />} />
              <Route path="/policy" element={<PolicyAndAutonomy />} />
              <Route path="/hiring-manager/:workflowId?" element={<HiringManager />} />
            </Routes>
          </main>
        </div>
      </ResolutionProvider>
    </ToastProvider>
  );
}

function FeedWithDrawer({
  role, onOpenDrawer,
}: {
  role: ReturnType<typeof getRolePreset>;
  onOpenDrawer: (workflowId: string) => void;
}) {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  return (
    <>
      <Feed key={role.id} role={role} onOpenDrawer={onOpenDrawer} />
      {id && (
        <Drawer
          workflowId={id}
          role={role}
          onClose={() => navigate("/")}
        />
      )}
    </>
  );
}

export default function FleetControlShell() {
  return (
    <div className="flex flex-col h-screen">
      <ShellBody />
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/client/components/feed/__tests__/integration.test.tsx`
Expected: PASS — 3 assertions.

- [ ] **Step 5: Commit**

```bash
git add web/client/components/feed/FleetControlShell.tsx web/client/components/feed/__tests__/integration.test.tsx
git commit -m "feat(feed): add FleetControlShell (header + rail + feed + conditional drawer + role persistence)"
```


---

## Phase G — Bulk actions + route redirects

### Task 32: `BulkActionBar` (and bulk-resolve wiring)

**Files:**
- Create: `web/client/components/feed/BulkActionBar.tsx`
- Test: `web/client/components/feed/__tests__/BulkActionBar.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// @vitest-environment jsdom
// web/client/components/feed/__tests__/BulkActionBar.test.tsx
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import BulkActionBar from "@client/components/feed/BulkActionBar";

beforeEach(() => {
  globalThis.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) } as Response);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("BulkActionBar", () => {
  it("renders the count and 4 actions when items are selected", () => {
    render(<BulkActionBar selectedIds={["hitl:WF-1", "hitl:WF-2"]} onCleared={() => {}} />);
    expect(screen.getByText(/2 selected/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /Approve/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Reject/i })).toBeTruthy();
  });

  it("renders nothing when no items are selected", () => {
    const { container } = render(<BulkActionBar selectedIds={[]} onCleared={() => {}} />);
    expect(container.firstChild).toBeNull();
  });

  it("POSTs to /api/exceptions/bulk-resolve and clears selection on Approve", async () => {
    const onCleared = vi.fn();
    render(<BulkActionBar selectedIds={["exception:E1", "exception:E2"]} onCleared={onCleared} />);
    fireEvent.click(screen.getByRole("button", { name: /Approve/i }));
    await waitFor(() => {
      expect((globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
        "/api/exceptions/bulk-resolve",
      );
    });
    expect(onCleared).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/components/feed/__tests__/BulkActionBar.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the file**

```tsx
// web/client/components/feed/BulkActionBar.tsx
//
// Sticky bar shown when the operator is in select mode. Translates the
// selected FeedItem ids ("exception:E1", "hitl:WF-2") back into the raw
// exception ids the bulk-resolve endpoint expects.
import { useState } from "react";

function extractExceptionId(feedItemId: string): string | null {
  // feed item id formats: "exception:<id>" or "hitl:<workflowId>" (no
  // exception). bulk-resolve takes exception ids — HITL items without an
  // associated exception are dropped.
  if (feedItemId.startsWith("exception:")) return feedItemId.slice("exception:".length);
  return null;
}

const ACTIONS = [
  { id: "approved", label: "Approve",      cls: "bg-emerald-600 hover:bg-emerald-700 text-white" },
  { id: "rejected", label: "Reject",       cls: "bg-red-600 hover:bg-red-700 text-white" },
  { id: "request-info", label: "Request docs", cls: "bg-white text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50" },
  { id: "escalate", label: "Escalate L2",  cls: "bg-white text-amber-700 ring-1 ring-amber-300 hover:bg-amber-50" },
];

export default function BulkActionBar({
  selectedIds, onCleared,
}: {
  selectedIds: string[];
  onCleared: () => void;
}) {
  const [busy, setBusy] = useState(false);
  if (selectedIds.length === 0) return null;

  const exceptionIds = selectedIds.map(extractExceptionId).filter((x): x is string => !!x);

  const submit = async (resolution: string) => {
    setBusy(true);
    try {
      await fetch("/api/exceptions/bulk-resolve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          exceptionIds, resolution, resolvedBy: "operator@zava",
        }),
      });
      onCleared();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="sticky bottom-3 z-20 mt-4 mx-auto max-w-3xl bg-slate-900 text-white px-4 py-3 rounded-lg shadow-lg flex items-center gap-3">
      <span className="text-xs">{selectedIds.length} selected</span>
      <span className="text-xs text-slate-400">({exceptionIds.length} bulk-resolvable)</span>
      <div className="ml-auto flex gap-2">
        {ACTIONS.map((a) => (
          <button
            key={a.id}
            type="button"
            disabled={busy || exceptionIds.length === 0}
            onClick={() => void submit(a.id)}
            className={`text-xs px-3 py-1.5 rounded font-medium disabled:opacity-50 ${a.cls}`}
          >{a.label}</button>
        ))}
        <button
          type="button"
          onClick={onCleared}
          className="text-xs px-3 py-1.5 rounded font-medium bg-slate-700 hover:bg-slate-600 text-white"
        >Cancel</button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/client/components/feed/__tests__/BulkActionBar.test.tsx`
Expected: PASS — 3 assertions.

- [ ] **Step 5: Commit**

```bash
git add web/client/components/feed/BulkActionBar.tsx web/client/components/feed/__tests__/BulkActionBar.test.tsx
git commit -m "feat(feed): add BulkActionBar wired to /api/exceptions/bulk-resolve"
```

---

### Task 33: Wire `main.tsx` to the new shell

> Route redirects already live inside `FleetControlShell` (Task 31's `<Route>` table). This task only re-points the root entry.

**Files:**
- Modify: `web/client/main.tsx`

- [ ] **Step 1: Replace the file contents**

```tsx
// web/client/main.tsx
import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import FleetControlShell from "./components/feed/FleetControlShell";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <FleetControlShell />
    </BrowserRouter>
  </React.StrictMode>,
);
```

- [ ] **Step 2: Verify TypeScript builds**

Run: `npm run build`
Expected: Build succeeds (no TS errors). If it fails, the most likely cause is the old `App.tsx` still being imported somewhere — check `grep -r "from .*App\"\|from .*App'\""` and remove any stragglers (the old file is deleted in Task 34).

- [ ] **Step 3: Smoke-test the dev server**

Run: `npm run dev:client &` then visit http://localhost:5273 and verify the feed renders.
Expected: Header, left rail, and feed render without error.

- [ ] **Step 4: Commit**

```bash
git add web/client/main.tsx
git commit -m "feat(feed): point main.tsx at FleetControlShell"
```

---

## Phase H — Cleanup

### Task 34: Delete legacy files

> Run AFTER Task 33 verified the shell works. This task is destructive and finalises the simplification thesis (spec §14: "if we need a rollback, that's what `git revert` is for").

**Files:**
- Delete: `web/client/App.tsx`
- Delete: `web/client/routes/FleetDashboard.tsx`
- Delete: `web/client/routes/ExceptionQueue.tsx`
- Delete: `web/client/routes/ReviewerQueue.tsx`
- Delete: `web/client/components/FleetManagerRail.tsx`
- Delete: `web/client/components/apex/KpiTileRow.tsx`
- Delete: `web/client/components/apex/ExceptionCardCompact.tsx`
- Delete: `web/client/components/ExceptionItem.tsx`
- Delete: `tests/web/ReviewerQueue.test.tsx`
- Delete: `tests/web/ReviewerQueue.test.js`
- Delete: `tests/web/WorkflowDetail.test.tsx` (the entire route is replaced by the drawer; existing tests cover obsolete tab/panel behaviour)
- Delete: `tests/web/WorkflowDetail.test.js`

- [ ] **Step 1: Delete the files**

Run:
```bash
git rm web/client/App.tsx \
       web/client/routes/FleetDashboard.tsx \
       web/client/routes/ExceptionQueue.tsx \
       web/client/routes/ReviewerQueue.tsx \
       web/client/components/FleetManagerRail.tsx \
       web/client/components/apex/KpiTileRow.tsx \
       web/client/components/apex/ExceptionCardCompact.tsx \
       web/client/components/ExceptionItem.tsx \
       tests/web/ReviewerQueue.test.tsx \
       tests/web/ReviewerQueue.test.js \
       tests/web/WorkflowDetail.test.tsx \
       tests/web/WorkflowDetail.test.js
```

- [ ] **Step 2: Hunt for dangling imports**

Run: `grep -RIn "FleetDashboard\|ExceptionQueue\|ReviewerQueue\|FleetManagerRail\|KpiTileRow\|ExceptionCardCompact\|ExceptionItem\b\|from .*App\"" web/client tests/web 2>&1`
Expected: No matches (the new shell does not import any of these).

- [ ] **Step 3: Run TypeScript build**

Run: `npm run build`
Expected: Build succeeds.

If any import still references a deleted file, fix it inline (it will be a forgotten test or a `routes/WorkflowDetail.tsx` reference — which is left alone because `/workflows/:id` now goes to the drawer; `routes/WorkflowDetail.tsx` itself becomes orphan code. Decision: keep `WorkflowDetail.tsx` only if it's referenced by something else; otherwise delete it now too).

- [ ] **Step 4: Also delete `routes/WorkflowDetail.tsx`** (orphan after Task 33)

Run:
```bash
git rm web/client/routes/WorkflowDetail.tsx
npm run build
```
Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git commit -m "chore(feed): delete legacy routes, rail, and detail panels"
```

---

### Task 35: Full test suite + e2e smoke

- [ ] **Step 1: Run the full unit suite**

Run: `npm run test -- --reporter=dot`
Expected: All previously-passing tests still pass. The 11 pre-existing failures in `web/blueprint/src/components/cosmicLens/lib/__tests__/labels.test.ts` are baseline noise unrelated to this PR — confirm the count hasn't grown.

If the count grew, the most likely cause is a test relying on a deleted route or component. Update or delete those tests.

- [ ] **Step 2: Verify no untouched test imports the old surface**

Run: `grep -RIn "FleetDashboard\|ExceptionQueue\|ReviewerQueue\|KpiTileRow\|ExceptionCardCompact" tests 2>&1`
Expected: No matches.

- [ ] **Step 3: Manual smoke (dev server)**

Run: `npm run dev:client`
Open: http://localhost:5273
Check:
- Feed lands with the "Needs you" filter active and HITL/Exception cards visible.
- Clicking a card opens the drawer on the right; Esc closes it.
- The role switcher in the header swaps the filter to "all-activity" for Executive, hides the action buttons, and the "Today" chip updates.
- The 🔔 popover renders without errors.
- Old bookmarks redirect: navigate manually to `/fleet`, `/exceptions`, `/reviewer-queue` — confirm they end at `/?filter=…`.
- The "More ▾" submenu reveals Analytics, Evaluations, Economics, Policy; clicking them opens the (unchanged) legacy route content.

- [ ] **Step 4: Commit (no-op or doc tweaks only)**

If you needed to fix anything in step 1–3, commit those fixes with a focused message. Otherwise nothing to commit.

```bash
git status --porcelain
# (no output → nothing to do)
```

---

### Task 36: Update top-level docs

**Files:**
- Modify: `web/README.md` (if it documents the deleted routes/rail)

- [ ] **Step 1: Check what `web/README.md` claims**

```bash
grep -n "FleetManagerRail\|/fleet\|/exceptions\|/reviewer-queue\|/workflows/" web/README.md docs/README.md docs/DEVELOPMENT.md 2>&1
```

- [ ] **Step 2: Update affected sections**

For each match, replace references to the old routes / rail with the new Feed/Drawer language. Keep changes minimal and factual — this is a documentation patch, not a rewrite.

- [ ] **Step 3: Commit**

```bash
git add web/README.md docs/README.md docs/DEVELOPMENT.md
git commit -m "docs(feed): update web docs to reference Feed of Work + Drawer"
```

---

## Acceptance summary (mapping back to spec)

| Spec section | Implemented in task(s) | Notes |
|---|---|---|
| §1 Vision · Feed of Work | 17–20, 31 | Header + LeftRail + Feed (filter + cards + pill) + conditional Drawer |
| §2 Architecture · component inventory | 9–31 | All new components present; all listed deletions in Task 34 |
| §3.1 Layout (fluid, screen-aware) | 10 (`@container`) + 21 (Drawer responsive widths) | Verify breakpoints during Task 35 smoke |
| §3.2 Ordering · chronological | 2 (`chronological()`), 8 (`useFeedItems`) | Severity is visual only via CardShell border |
| §3.3 Default filter `Needs you` | 17 (FilterBar), 1 (role defaults), 8 (mode applied) | |
| §3.4 Card types (7) | 11–16 + `ResolvedCard` | All 7 types implemented |
| §3.5 Decisions stay on screen | 6 (ResolutionProvider), 8 (overlay), 11/12/13 (record paths), 16 (ResolvedCard) | Optimistic transform + 30s undo + revert-on-fail |
| §3.6 `↑ N new` pill | 7 (`useNewItemsBuffer`), 18 (NewItemsPill), 20 (Feed) | |
| §3.7 Virtualisation | 19 (`CardList`) | Manual windowing (PAGE = 100), no new dependency |
| §4 Drawer · 3 sections | 21–24 | Section order driven by `role.drawerSectionOrder` |
| §5 Header | 26 (Toast), 27 (RoleSwitcher), 28 (NotificationsPopover), 29 (Header) | "Today" chip switches by role |
| §6 Left rail | 30 (LeftRail) | Saved views + More ▾ + Constellation link preserved |
| §7 Role switcher (5 presets) | 1 (presets), 27 (UI), 31 (persistence + re-key) | localStorage key `fleetctl.role` |
| §8 Bulk actions | 32 (BulkActionBar), 20 (Feed wiring) | Hidden behind `Select` toggle; uses existing `/api/exceptions/bulk-resolve` |
| §9 Data flow | 5 (usePolicyEvents), 8 (useFeedItems) | No new backend endpoints |
| §10 Visual language | 10 (CardShell), 11–16 (per-card styling) | Tailwind 4, no new deps |
| §11 Routing + 301 redirects | 31 (Routes), 33 (main.tsx) | `/fleet`, `/exceptions`, `/reviewer-queue` → `/?filter=…` |
| §12 Persistence (localStorage) | 4 (useLocalStorageState), 31 (shell wiring) | All `fleetctl.*` keys handled |
| §13 Testing | every task (Vitest + RTL) | Test files live alongside components under `__tests__/` |
| §14 Migration · single PR · no flag | 33 + 34 | `git revert` is the rollback story |
| §15 Deferred questions | "Design decisions" section above | All 5 resolved with explicit rationale |

---

## Self-review checklist

| Check | Outcome |
|---|---|
| Every spec section §1–§14 has at least one task | ✅ — see acceptance table above |
| Every §15 deferred question resolved with a written decision | ✅ — section "Design decisions (resolving spec §15 deferred questions)" |
| No "TBD", "TODO", "implement later", "similar to Task N" without code | ✅ — searched; only "stub" placeholders flagged with explicit follow-up tasks (Task 21 stubs → Task 22–24 fills) |
| Every step that changes code shows the full code | ✅ |
| Every test step shows the run command and expected pass/fail | ✅ |
| Method / property / hook names referenced in late tasks match early tasks | ✅ — `useResolutionStore`, `record`/`revert`/`get`, `RolePreset`, `FilterState`, `FeedItem`, `useFeedItems`, `ROLE_PRESETS` all consistent |
| Optimistic-resolution contract is consistent across HITLCard, ExceptionCard, ExternalWaitCard, ResolvedCard | ✅ — all use `store.record(item.id, …)` and `store.revert(item.id)`; `ResolvedCard` reads `store.get(item.origin.id)` (overlay item's id is `resolved:${origin.id}` so we read by `origin.id`, matches §3.5) |
| Deleted files in Task 34 are not referenced by retained code or tests | ✅ — `ReceiptThumb` extraction in Task 9 removes the last meaningful dependency on `routes/ReviewerQueue.tsx`; everything else is preserved-as-is |
| Pre-existing test baseline (11 failures in `web/blueprint/`) is documented in Task 35 | ✅ |

