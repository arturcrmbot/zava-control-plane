# Fleet Control — Feed Redesign Design Spec

**Status:** Approved · ready for implementation plan
**Date:** 2026-05-18
**Scope:** `web/client/` (operator console served from repo-root Vite on port 5273). Pure frontend redesign — backend APIs and event streams unchanged.
**Predecessor surface:** today's 7-route operator console (Dashboard, Exceptions, Reviewer queue, Policy, Analytics, Evaluations, Economics) plus the always-on `FleetManagerRail` and per-workflow detail page with 6 tabs + 6 stacked panels.

---

## 1. Vision

Today's Fleet Control is a console with eight surfaces. An ops reviewer who comes here to clear exceptions has to navigate twice before they can act on anything, while an always-on event rail eats 300px of screen real-estate they don't read. Three different routes show overlapping slices of the same exception data. The workflow detail page stacks 12 panels for a job that needs four.

This spec replaces the console with a **Feed of Work**: one chronological stream of cards modelled on Facebook's News Feed structure, with Linear's visual cleanliness. The reviewer opens one screen, sees what needs them, acts inline from the card, and watches the card transform in place to a calm "✓ Approved by you · undo" line they can scroll back to later. Detail lives in a Gmail-style right-side drawer. Everything secondary moves behind a "More" menu.

A role-switcher in the header lets the same screen reshape itself for Ops Reviewer, Finance Controller, Hiring Manager, Agent-Platform Engineer, or Executive — same feed, different defaults, different visible card types.

### What the user sees

| Moment | Today | After |
|---|---|---|
| First load | Land on `/fleet` dashboard. KPI tiles, top-3 exceptions strip, active-workflows grid, two sidebar panels, always-on event rail. Three places to look. | Land on the Feed. One column of cards, newest first, filtered to "Needs you". Eyes go to the first card. |
| Acting on a HITL | Click WorkflowCard → land on `/workflows/:id` → scroll through 6 tabs and 6 right-rail panels → find the action → resolve | Click action button on the card. Card shrinks in place to "✓ Approved by you · 2m ago · undo". Next card scrolls into view. |
| Switching persona for a demo | Manually navigate between `/exceptions`, `/reviewer-queue`, `/economics`, `/policy` to tell different stories | One click in the header role switcher. Feed reshapes: filters, visible card types, header chip, left-rail saved views all swap. |
| Deep audit | Open `/workflows/:id` page, lose feed context | Click card → drawer slides over feed at 50–65% width. Feed stays visible on left. Close drawer → exact same scroll position. |

### Out of scope (deliberately)

- Backend changes. All current APIs (`/api/workflows`, `/api/exceptions`, `/api/policy`, `/api/fleet/economics`, the two SSE streams) work unchanged.
- RBAC. The role switcher is a frontend preset bundle, demo-first. Real role-gating is a separate concern.
- Mobile. The console is desktop-only; responsive rules below stop at small-laptop widths.
- The `web/blueprint/` constellation app — out of `web/client/`'s scope, still opens in a new tab.
- The `web/portal/` candidate/recruiter flow — separate audience, separate app.

---

## 2. Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                       <FleetControlShell>  (replaces today's App.tsx)        │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ <Header>  brand · search · 🔔 · "Today" chip · <RoleSwitcher> · avatar  │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│ ┌──────────┬──────────────────────────────────────┬──────────────────────┐  │
│ │          │                                      │                      │  │
│ │ <Left    │   <Feed>                             │  <Drawer>            │  │
│ │  Rail>   │   ├ <FilterBar>                      │  (conditional;       │  │
│ │  saved   │   │   • [● Needs you] [All activity] │   slides in when     │  │
│ │  views + │   │   • domain chips · search        │   a card is opened)  │  │
│ │  More ▾  │   │                                  │                      │  │
│ │          │   ├ <CardList>                       │  ├ Decision          │  │
│ │ role-    │   │   ┌ HITLCard ─────────────┐      │  ├ Activity         │  │
│ │ scoped   │   │   │ inline actions        │      │  └ Audit            │  │
│ │ presets  │   │   └───────────────────────┘      │                      │  │
│ │          │   │   ┌ ResolvedCard (transformed)┐  │                      │  │
│ │          │   │   └───────────────────────────┘  │                      │  │
│ │          │   │   ┌ ExceptionCard ──────────┐    │                      │  │
│ │          │   │   └─────────────────────────┘    │                      │  │
│ │          │   │   …                              │                      │  │
│ │          │   └ "↑ N new" pill (top, sticky)     │                      │  │
│ │          │                                      │                      │  │
│ └──────────┴──────────────────────────────────────┴──────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
       ▲                       ▲                              ▲
       │                       │                              │
       └ role preset ──────────┴ filter state ────────────────┘
                               │
                               ▼
                   useFeedItems()  (single hook)
                               │
       ┌───────────────────────┼─────────────────────────┐
       ▼                       ▼                         ▼
   useWorkflows()      useExceptions()         useFleetManagerStream()
   useOrchestrationStream()    /api/policy events    /api/fleet/economics
       (existing hooks — composed, not replaced)
```

### Component inventory (new / changed / removed)

**New components** (all under `web/client/components/feed/`):
- `FleetControlShell.tsx` — replaces `App.tsx`'s layout. Renders header + left rail + feed + conditional drawer.
- `Header.tsx` — brand, search, notifications, "Today" chip, role switcher, avatar.
- `RoleSwitcher.tsx` — dropdown that swaps role preset; persists choice to `localStorage`.
- `LeftRail.tsx` — saved views + collapsible "More ▾" submenu. Collapsible to icon-only on narrow screens.
- `Feed.tsx` — orchestrates `FilterBar` + `CardList` + "↑ N new" pill.
- `FilterBar.tsx` — segmented `[● Needs you] [All activity]` + domain chips + "Select" mode toggle + search.
- `CardList.tsx` — chronological list with virtualisation for >100 items.
- `CardShell.tsx` — common chrome (severity border, header row, action row); accepts typed slot content.
- `cards/HITLCard.tsx`, `cards/ExceptionCard.tsx`, `cards/ExternalWaitCard.tsx`, `cards/MilestoneCard.tsx`, `cards/PolicyCard.tsx`, `cards/AgentEventCard.tsx`, `cards/ResolvedCard.tsx` — one per card type.
- `Drawer.tsx` — right-side panel; renders `DrawerDecision` / `DrawerActivity` / `DrawerAudit`.
- `NewItemsPill.tsx` — sticky pill above the feed listing inbound items behind a user-controlled pull-down.
- `NotificationsPopover.tsx` — bell dropdown listing unread feed items.

**Changed (reshaped, not deleted):**
- `web/client/routes/WorkflowDetail.tsx` → moved into `web/client/components/feed/Drawer.tsx` with 3 sections instead of 6 tabs + 6 panels. The route `/workflows/:id` is preserved as a deep-link that opens the drawer over the feed.
- `web/client/components/WorkflowCard.tsx` → repurposed as `cards/HITLCard.tsx` content (the card shell + horizontal/vertical layout switching are new; the receipt thumbnail + verdict badge + SLA logic survives).
- `web/client/components/ExceptionItem.tsx` → repurposed as `cards/ExceptionCard.tsx`.
- `web/client/hooks/useExceptions.ts`, `useWorkflows.ts`, `useFleetManagerStream.ts`, `useOrchestrationStream.ts` → kept; composed by new `useFeedItems.ts`.
- `web/client/App.tsx` → replaced by `FleetControlShell.tsx`. The old file is deleted.

**Removed (routes + their components):**
- `web/client/routes/FleetDashboard.tsx`
- `web/client/routes/ExceptionQueue.tsx`
- `web/client/routes/ReviewerQueue.tsx`
- `web/client/components/apex/KpiTileRow.tsx` (its value moves into the header "Today" chip)
- `web/client/components/apex/ExceptionCardCompact.tsx` (the "top-3" panel is gone — those items are just at the top of the feed)
- `web/client/components/FleetManagerRail.tsx` (the always-on 300px rail; its events become a card type)

**Preserved as-is (reachable via "More ▾"):**
- `web/client/routes/Analytics.tsx`
- `web/client/routes/Evaluations.tsx`
- `web/client/routes/Economics.tsx`
- `web/client/routes/PolicyAndAutonomy.tsx`
- `web/client/routes/HiringManager.tsx`

---

## 3. The feed

### 3.1 Layout (fluid, screen-aware)

| Viewport | Left rail | Feed centre width | Card internal layout | Drawer width |
|---|---|---|---|---|
| < 1024px | 160px (icon-only) | viewport − 160px − 16px gutters | **Vertical** (receipt above, actions below) | full-screen overlay |
| 1024–1280px | 160px (full labels) | viewport − 160px − 32px gutters | **Vertical** | 65% |
| 1280–1600px | 200px | viewport − 200px − 48px gutters | **Horizontal** (receipt · summary · recommendation · actions all in one row) | 60% |
| > 1600px | 200px | viewport − 200px − 64px gutters; option to flip into a **two-column masonry** if the user enables `?layout=dense` | **Horizontal**, packed | 50% |

No artificial reading-column cap. The principle is *use the screen the user paid for*. Cards adapt their internal layout to the available width via CSS container queries, not viewport media queries, so opening the drawer narrows the feed and cards automatically re-stack vertically without page reload.

The drawer is also fluid (50–65% depending on viewport, full-screen below 1024px) — not a fixed pixel width.

### 3.2 Ordering

Strict chronological, newest first. Severity is visual only (left-border accent: red-l-4 / amber-l-4 / slate-l-4) and never reorders. New items arrive at the top behind a sticky `<NewItemsPill>` (`↑ 3 new`); items are not inserted until the user clicks the pill, so the feed never jumps under them mid-action. Items the user is currently interacting with (focus inside the card, action in-flight) are locked from re-ordering or transformation until interaction ends.

### 3.3 Default filter — "Needs you"

The filter bar's top-left shows a segmented control:

```
[● Needs you]  [ Show all activity ]
```

"Needs you" is the loud default state. It includes: `HITLCard`, `ExceptionCard`, `ExternalWaitCard`. Items the operator has already acted on transform to `ResolvedCard` and **remain in the feed** in their chronological position (see §3.5) — they are not filtered out by "Needs you".

"Show all activity" additionally exposes: `MilestoneCard` (workflow completed / failed), `PolicyCard` (autonomy change, policy edit), `AgentEventCard` (FM/orchestration events).

### 3.4 Card types

All cards share `CardShell.tsx` chrome: severity border accent (left), header row (icon + type label + workflow id + timestamp), body slot, action slot, optional expand chevron. Card type only affects what fills the body and action slots.

| Type | Triggered by | Body slot | Action slot | "Needs you"? |
|---|---|---|---|---|
| `HITLCard` | Workflow with `status: awaiting_hitl` | Receipt thumbnail + claim/candidate summary + fleet-manager recommendation + verdict badge | `Approve` · `Request docs` · `Escalate` · `Reject` (re-uses `/api/exceptions/:id/resolve`) | yes |
| `ExceptionCard` | Open exception not yet picked up | Severity badge + summary + suggested resolution | Same 4 + `Snooze 1h` | yes |
| `ExternalWaitCard` | Workflow with `metadata.wait_kind = "external_party"` | "Awaiting *<party>* for *<reason>* · token issued at *<time>*" | `Nudge` · `Reassign` · `View token` | yes |
| `MilestoneCard` | Workflow status transition (`in_progress → completed`/`failed`) | "WF-1234 (expense) completed in 12s · saved $18 vs manual" | `Open` (drawer) · `Dismiss` | only in "Show all activity" |
| `PolicyCard` | `/api/policy` events / autonomy changes | "Autonomy threshold raised to 0.85 on vendor-kyc by alice@" | `Acknowledge` · `View diff` (drawer) | only in "Show all activity" |
| `AgentEventCard` | `useFleetManagerStream` / `useOrchestrationStream` events | "Fleet Manager woke up on WF-1234 · reason: SLA breach in 8m" | `Expand JSON` (inline accordion) | only in "Show all activity" |
| `ResolvedCard` | A card the user acted on (any of the above) | One-line collapsed state with action verb + timestamp; receipt thumb + verdict badge preserved | `Undo` (30s TTL) · `Audit ↗` (opens drawer at Audit section) | yes (it stays in chronological place) |

All cards expand into the drawer (right side, 50–65%) on primary click. The "Expand JSON" affordance on `AgentEventCard` is an inline accordion *instead of* a drawer open, because raw JSON is not worth a drawer.

### 3.5 Post-action behaviour ("decisions stay on screen")

When the user clicks an inline action on `HITLCard` / `ExceptionCard` / `ExternalWaitCard`:

1. Optimistic transform: card animates in place to its `ResolvedCard` form (~150ms). Chronological slot is preserved.
2. Backend call fires (`POST /api/exceptions/:id/resolve` or equivalent).
3. On success: `ResolvedCard` reads "✓ *<Verb>* by you · *<relative time>* · undo · audit ↗". The receipt thumbnail and verdict badge remain visible. Severity accent fades to slate.
4. On failure: card reverts to its actionable form with a toast "Couldn't resolve — try again".
5. The "undo" affordance is live for 30 seconds (configurable via `VITE_UNDO_TTL_MS`). After it expires the line shrinks further to a minimal `✓ Approved by you · 14:02 · audit ↗`.
6. The card is never removed from the feed by an action; only an explicit `Dismiss` (on `MilestoneCard`) or filter change can hide it.

This gives the reviewer a scroll-back timeline of their day, in context, with the original card content visible enough to re-evaluate.

### 3.6 The "↑ N new" pill

A sticky pill at the top of the feed listing inbound items the user hasn't pulled in yet. Clicking the pill inserts the items at the top, fades the pill, and gently scrolls the focused card (if any) to maintain its viewport position. New items arriving while a card is in mid-action (action in flight, drawer open and unsaved) are buffered until the next idle moment.

### 3.7 Virtualisation

`CardList` virtualises beyond 100 items (windowed render). The chronological position of `ResolvedCard`s is preserved across virtualisation by storing the canonical ordered list in the hook, not in the DOM.

---

## 4. The drawer

`Drawer.tsx` slides in from the right when a card is opened. It reshapes today's `WorkflowDetail.tsx` from `[6 tabs] + [6 stacked right panels]` into **3 ordered sections** that scroll vertically inside the drawer.

| Section | Contents | Default state |
|---|---|---|
| **Decision** | Receipt panel (`ReceiptPanel`) + fleet-manager recommendation + 4 action buttons + `AuthorityCard` + `KillSwitchPanel` (collapsed by default unless severity ≥ high) | expanded |
| **Activity** | **Merge** of today's `Phases` + `Timeline` + `Traces` + `Ledger` into one filterable activity stream. View toggle: `Phases` · `Timeline` · `Raw spans`. Single list of events with type filter chips at the top. | expanded |
| **Audit** | `EvidencePanel` + `AuditTrail` + `EconomicsPanel` + `FleetAssignment` + `SkillAmplificationPanel`. All accordions, default-collapsed. | collapsed |

For role = `Executive`, section order flips to Audit / Activity / Decision and the action buttons are hidden. For role = `Agent-Platform Engineer`, Activity is expanded first and Decision collapses.

The drawer header carries: workflow id, type chip, status badge, "Open in *<domain>* view ↗" deep-link (preserves the existing hiring → portal and expense → reviewer-queue cross-links), and a close (`Esc` or `✕`).

Closing the drawer returns the feed to the exact scroll position it was at, with the previously-opened card highlighted (subtle ring) for 1 second so the eye finds it again.

`/workflows/:id` URLs become drawer permalinks: arriving cold at the URL opens the feed with that drawer pre-open.

---

## 5. Header

Single thin sticky row, 48px tall:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Apex   [ 🔍 search ]            🔔 3   Today: 12 · 3 crit   role: Ops Reviewer ▾   avatar │
└─────────────────────────────────────────────────────────────────────────┘
```

- **Apex** — brand text, links to feed root (`/`).
- **Search** — global search across workflow ids, employee ids, vendor names. Opens a popover with results that, when clicked, open the relevant drawer over the feed.
- **🔔 Notifications** — popover listing recent unread feed items (mirrors the feed filtered to `unread`). Real-time toast for `critical` severity only (opt-in, persisted preference). Click an item → scrolls the feed to it (and opens drawer if applicable).
- **"Today" chip** — content depends on role:
  - Ops Reviewer: `Today: <N> · <M> crit` (N = open needs-you items; M = critical of those)
  - Finance Controller: `$ saved today: $XXX`
  - Hiring Manager: `Open roles: N · Candidates today: M`
  - SRE: `Fleet health: green · 14ms p95`
  - Executive: `Throughput: N/h · Auto-rate: 84% · Cost: $X`
- **Role switcher** (§7) — dropdown showing current role; click to swap.
- **Avatar** — user menu (logout, preferences).

Nothing else lives in the header. No nav links — navigation is the left rail.

---

## 6. Left rail

160–200px wide, collapsible to icon-only on narrow screens. Two zones:

**Saved views (top):**
- Role-default views appear first, can be reordered by drag. User-saved views appear below the role defaults.
- Each view is a stored `(filter mode, domain chips, severity, mine/all, search query)` tuple.
- `+ Save current filter` at the bottom of the saved-views zone.

**More ▾ (bottom):**
- A collapsed group containing the demoted secondary routes: `Analytics`, `Evaluations`, `Economics`, `Policy`. Each is a single click but never default-visible.
- Order within "More ▾" is also role-scoped (e.g. SRE sees `Evaluations`, `Policy` first; Executive sees `Economics`, `Analytics` first; Reviewer sees the routes in their alphabetical default order).
- The constellation link (`Constellation ↗`) stays at the very bottom, still opens in a new tab to the `web/blueprint/` app (existing behaviour preserved).

---

## 7. Role switcher

A `<RoleSwitcher>` dropdown in the header, between the "Today" chip and the avatar.

Each role is a **frontend preset bundle**:

```ts
type RolePreset = {
  id: 'ops-reviewer' | 'finance-controller' | 'hiring-manager' | 'sre' | 'executive';
  label: string;
  defaultFilter: 'needs-you' | 'all-activity';
  defaultDomains: string[];           // domain prefix filter
  visibleCardTypes: CardType[];       // restricts what's renderable
  hideActionButtons: boolean;         // executive mode
  defaultSavedViews: SavedView[];     // populate left rail top zone
  moreOrder: string[];                // reorder More ▾ submenu
  todayChip: ChipSpec;                // header "Today" chip content
  drawerSectionOrder: ('decision' | 'activity' | 'audit')[];
};
```

Initial role bundles (subject to tuning, but ship with these 5):

| Role | Default filter | Default domains | Visible card types | Hide actions? | Today chip | Drawer order |
|---|---|---|---|---|---|---|
| **Ops Reviewer** (default) | Needs you | all | HITL · Exception · External wait · Resolved | no | `Today: N · M crit` | Decision · Activity · Audit |
| **Finance Controller** | Needs you | finance prefixes (`expense-claim`, `ap-invoice`, `purchase-order`, `treasury-fx`, `contract-renewal`) | HITL · Exception · External wait · Policy · Resolved | no | `$ saved today` | Decision · Activity · Audit |
| **Hiring Manager** | Needs you | `hiring` | HITL · Exception · Resolved | no | `Open roles · candidates today` | Decision · Activity · Audit |
| **Agent-Platform Engineer / SRE** | Show all activity | all | all 7 types | no | `Fleet health · p95 latency` | Activity · Decision · Audit |
| **Executive** | Show all activity | all | Milestone · Policy · Resolved | **yes** (read-only) | `Throughput · Auto-rate · Cost` | Audit · Activity · Decision |

Switching role does **not** navigate — it re-applies the preset to the current feed instantly:
1. Filter bar state swaps to the preset's default
2. Left rail saved-views zone repopulates with role-default views (user-saved views remain pinned below)
3. "More ▾" reorders
4. Header "Today" chip swaps
5. Visible card types filter applies (without removing already-resolved cards from history)
6. Action buttons on cards hide if `hideActionButtons: true`

Choice persists to `localStorage` (`fleetctl.role`). Default for first-time users is `ops-reviewer`. For the demo storytelling beat this is one click to flip the whole console from "Finance controller's day" → "Hiring manager's day" → "SRE's day" without leaving the feed.

---

## 8. Bulk actions

Kept but hidden behind a `Select` mode toggle in the `FilterBar` (or `Shift+click` a card to enter select mode). In select mode:
- Each card gains a checkbox on the left.
- A sticky action bar appears below the filter bar: `N selected · [Approve] [Request docs] [Escalate] [Reject] [Bulk resolve…] [Cancel]`.
- `Bulk resolve…` opens today's existing `BulkHitlModal` (preserved) calling `/api/exceptions/bulk-resolve`.
- Exiting select mode returns the feed to single-card flow.

Bulk mode is hidden by default so single-item flow stays frictionless. It is not available for `Executive` role (action-less).

---

## 9. Data flow

Single hook `useFeedItems(role, filter)` composes the existing hooks:

```ts
function useFeedItems(role: RolePreset, filter: FilterState): FeedItem[] {
  const workflows  = useWorkflows();
  const exceptions = useExceptions();
  const fmEvents   = useFleetManagerStream();
  const orchEvents = useOrchestrationStream();
  const policyEvents = usePolicyEvents();   // small new hook over /api/policy

  return useMemo(() => {
    const items: FeedItem[] = [
      ...buildHITLCards(workflows),
      ...buildExceptionCards(exceptions),
      ...buildExternalWaitCards(workflows),
      ...(filter.mode === 'all-activity' ? [
        ...buildMilestoneCards(workflows),
        ...buildPolicyCards(policyEvents),
        ...buildAgentEventCards(fmEvents, orchEvents),
      ] : []),
    ];
    return items
      .filter(i => role.visibleCardTypes.includes(i.type))
      .filter(i => filter.matches(i))
      .sort((a, b) => b.timestamp - a.timestamp);
  }, [workflows, exceptions, fmEvents, orchEvents, policyEvents, role, filter]);
}
```

Resolved cards are derived state — each `FeedItem` carries a `resolution?: { verb, actor, timestamp }` field set when the local optimistic store records the action. The store survives polling refreshes (server-side resolved items reconcile with optimistic state by id).

No new backend endpoints. The `usePolicyEvents()` hook polls `/api/policy` for change events (mirror of today's `PolicyAutonomyPanel`).

---

## 10. Visual language

- **Type**: Inter / system stack. 15px body, 13px metadata, 11px caption. Headings inside drawer sections are 14px medium uppercase tracking-wide.
- **Whitespace**: 16px padding inside cards; 12px gap between cards; gutter around the feed scales with viewport (16/32/48/64px per breakpoint).
- **Severity colour**: left-border accent only (`border-l-4 border-red-500` / `border-amber-500` / `border-slate-200`). No coloured card fills. Severity dot in the card header echoes the same colour.
- **Status badges**: small ring badges (`ring-1` + tinted bg) — re-use today's `STATUS_COLOR` and `VERDICT_COLOR` palettes from `WorkflowCard.tsx`.
- **Action buttons**: re-use today's `ACTION_BUTTON_CLASS` palette from `ReviewerQueue.tsx` (Approve = emerald solid, Request docs / Escalate / Reject = white with coloured ring).
- **Motion**: card resolve-transform = 150ms ease-out; drawer slide = 200ms ease-out; pill insert = 250ms ease-in-out. Nothing else animates.
- **Density**: a horizontal `HITLCard` on a wide screen is ~96px tall; vertical version is ~200px tall.

---

## 11. Routing

| Path | Behaviour |
|---|---|
| `/` | Feed (replaces `/fleet`) |
| `/fleet` | 301 → `/` (preserve old bookmarks) |
| `/exceptions` | 301 → `/?filter=exceptions` (preserve old bookmarks; applies the exceptions filter) |
| `/reviewer-queue` | 301 → `/?filter=hitl` (preserve old bookmarks) |
| `/workflows/:id` | Opens Feed with the matching card's drawer pre-open. Browser back closes the drawer. |
| `/analytics` · `/evals` · `/economics` · `/policy` | Unchanged — reached via "More ▾". |
| `/hiring-manager/:workflowId?` | Unchanged — POC2 surface, reached via drawer's "Open in domain view ↗" link. |

Closing the drawer pushes back from `/workflows/:id` to `/`. Browser back/forward navigation works between drawer-open and drawer-closed states.

---

## 12. Persistence

`localStorage` keys (all under namespace `fleetctl.`):

| Key | Value | Purpose |
|---|---|---|
| `fleetctl.role` | `RolePreset['id']` | Last-selected role; restored on next visit |
| `fleetctl.savedViews.<roleId>` | `SavedView[]` | User-added saved views, scoped per role |
| `fleetctl.leftRailCollapsed` | `boolean` | Left rail icon-only mode |
| `fleetctl.criticalToasts` | `boolean` | Whether to surface real-time toasts for critical severity (default: `true`) |
| `fleetctl.layoutDense` | `boolean` | Opt-in two-column masonry on wide screens (>1600px); off by default |

No server-side user preferences — this is a frontend-only redesign.

---

## 13. Testing

Re-use today's Vitest + React Testing Library setup (already configured at the repo root via `vitest.config.ts`). Tests live next to components under `web/client/components/feed/__tests__/`.

Key test surfaces:

| Component | What to test |
|---|---|
| `Feed.tsx` | Chronological ordering; pill behaviour on inbound items; "Needs you" vs "Show all activity" filtering |
| `CardShell.tsx` | Severity border accent; horizontal vs vertical layout switch via container query |
| `cards/HITLCard.tsx` | Optimistic transform to `ResolvedCard` on action click; undo behaviour within TTL; revert on backend failure |
| `RoleSwitcher.tsx` | Swapping role re-applies filter, swaps left rail, swaps header chip, hides actions for Executive |
| `Drawer.tsx` | Section order per role; close returns scroll position; deep-link from `/workflows/:id` opens drawer pre-open |
| `useFeedItems.ts` | Composing 5 hooks into one ordered list; filter mode swap toggles agent-event visibility |
| Integration | Land on `/`, see feed; click HITL action → card transforms; click 🔔 → notifications popover; click `Esc` → drawer closes |

Backend contract tests (against `/api/exceptions/:id/resolve`, `/api/exceptions/bulk-resolve`, `/api/workflows/:id`) are unchanged — same endpoints, same payloads.

---

## 14. Migration & rollout

Single PR, single switch — no feature flag. The shape of today's `web/client/` (no own `package.json`; hosted by repo-root Vite) means:

1. Add all new components under `web/client/components/feed/`.
2. Reshape `WorkflowDetail.tsx` content into `Drawer.tsx`; preserve all child panels (`AuthorityCard`, `KillSwitchPanel`, `EvidencePanel`, etc.) — they move, they don't change.
3. Replace `App.tsx` with `FleetControlShell.tsx`. Delete `routes/FleetDashboard.tsx`, `routes/ExceptionQueue.tsx`, `routes/ReviewerQueue.tsx`, `components/FleetManagerRail.tsx`, `components/apex/KpiTileRow.tsx`, `components/apex/ExceptionCardCompact.tsx`.
4. Wire 301-style redirects for the deleted routes (preserve bookmarks).
5. Re-point root `index.html` if needed (it should already pick up the new `App.tsx`).

The redesign is shippable as one PR because: backend is unchanged, routing changes are additive + redirect, no schema work, and the component graph is well-bounded by the existing `web/client/` directory.

A `?legacy=1` query param flag is **not** included — the simplification thesis is undermined if both shells live in the codebase. If we need a rollback, that's what `git revert` is for.

---

## 15. Open questions deferred to implementation plan

The following are intentionally deferred to the writing-plans step and don't change the shape of the design:

1. Exact CSS container-query breakpoints for card horizontal/vertical layout switch (must coexist with drawer-open feed-narrowing).
2. Whether `usePolicyEvents()` polls `/api/policy` every N seconds or piggybacks on an existing event stream.
3. Toast component choice — re-use `react-hot-toast` if already in tree, otherwise a tiny in-app primitive.
4. Whether the role-default saved views are hardcoded in `web/shared/roles.ts` or fetched from a tiny `/api/roles/presets` endpoint (recommendation: hardcoded for v1, server-driven later).
5. Search popover scope — workflow ids only in v1, expand to entities (vendors, employees, candidates) in v1.1.
