# UX bugs from 2026-05-21 demo prep — orphan resolutions + drawer 404 + drawer bloat

Three issues surfaced during the employee-transfer end-to-end demo. All are post-demo follow-ups — none block the immediate review but every one is a credibility-tax during a live walkthrough.

## Bug 1 — Drawer hangs on "loading…" when the workflow_id doesn't exist

**Symptom (operator-observable).** Clicking certain feed cards / notification items navigates to e.g. `/workflows/EXC-osfMt7vs` and the drawer shows nothing forever — no error, no empty-state, no "workflow not found", just a perpetual `loading…` shimmer while the URL keeps polling every 2.5s.

**Root cause.** `web/client/components/feed/Drawer.tsx:39-42`:

```tsx
const refresh = useCallback(async () => {
  const r = await fetch(`/api/workflows/${workflowId}`);
  setD((await r.json()) as DrawerData);          // ← no `r.ok` check
}, [workflowId]);
```

`/api/workflows/<unknown>` returns HTTP 404 with body `{"detail":"Not Found"}`. The code blindly parses it as `DrawerData`, so `d` becomes `{detail:"Not Found"}` — truthy → the `if (!d)` "loading…" branch is skipped → React tries to render `<header>{d.workflow.id}</header>` against a missing `.workflow` and silently produces nothing (because the parent `<aside>` swallows the failure). `setInterval` keeps refetching every 2.5s, forever.

**Fix.**
1. Check `r.ok` and treat `404` as a terminal state with a clear "Workflow not found — it may have completed and been archived" empty-state + a "Back to feed" link.
2. Clear the `setInterval` once a 404 lands (no point polling a non-existent id).
3. Bubble the URL `workflowId` into the empty-state so the operator can copy it for triage.

**Files.** `web/client/components/feed/Drawer.tsx` (the `refresh` callback + the `if (!d)` branch).

## Bug 2 — Feed surfaces ghost workflow_ids for orphan resolutions

**Symptom.** The Notifications popover and the Feed itself sometimes show entries whose "workflow id" is actually an **exception id** (e.g. `EXC-osfMt7vs`). Click → routes to `/workflows/EXC-osfMt7vs` → hits Bug 1.

**Root cause.** `web/client/hooks/useFeedItems.ts:140`:

```ts
const m = origId.match(/^(?:exception|hitl|external-wait):(.+)$/);
const stripped = m?.[1] ?? origId;
const wf = wfById.get(stripped);
orphanResolutions.push({
  ...
  workflowId: wf?.id ?? stripped,  // ← fallback stamps the EXCEPTION id as workflowId
  ...
});
```

When a resolution lands for an exception whose parent workflow has already completed + been evicted from the in-flight list (`/api/workflows/index/in-flight`), `wfById.get(stripped)` returns `undefined` and the orphan-resolution card is stamped with the exception id as its `workflowId`. Combined with Bug 1, clicking it hangs the drawer.

**Why the fallback exists.** The comment on `useFeedItems.ts:130-132` explains: "We can't always recover the workflowId post-eviction, so render the card with what we have and skip the domain filter cleanly via domain=undefined." The intent was to keep showing the resolution receipt even after the parent dropped out. The bug is making it clickable as if it were a workflow.

**Fix options (pick one).**
- **A. Cheapest.** When `wf` is `undefined`, set `workflowId: null` and make the orphan card non-clickable (or surface "workflow archived" instead of a "View" affordance). Bug 1 fix becomes nice-to-have.
- **B. More work, better UX.** Persist a long-tail workflow lookup endpoint (e.g. `/api/workflows/<id>?include_archived=true`) so the drawer can fetch completed workflows for read-only display. The orphan-resolution card stays clickable and shows the historical record.
- **C. Hybrid.** Resolutions store the originating workflow_id alongside the exception id at write-time (no lookup needed); orphan cards then carry the right id even after eviction.

**Files.** `web/client/hooks/useFeedItems.ts:120-148` (orphan-resolution decoration loop). For option C: `api/server/services/resolutions.py` (or wherever resolution receipts are stored) needs to also record the originating workflow_id.

## Bug 3 — Workflow drawer is bloated and full of duplicate surfaces

**Symptom (raised verbatim).** *"the whole ux page sucks. it's so detailed there's so much duplication there. it's crazy"*

**Concrete duplication observed on `/workflows/EXF-0002` (Playwright snapshot 2026-05-21 09:43):**

1. **Decision section** carries the same 4 buttons in two places:
   - "Intervention Protocols" card → Approve ⚠ / Request additional docs / Escalate to approver L2 / Reject ⚠
   - Bare button row underneath → Approve / Request docs / Escalate L2 / Reject

2. **Phase progression rendered three times** in one drawer:
   - `PhaseRibbon` at the top of `DrawerActivity` (pills row)
   - `PhaseTimeline` under the "Phases" tab (vertical list)
   - The exception narrative's "What the Agent Tried" bullet list also enumerates phase transitions

3. **Activity panel** has 4 tabs whose content overlaps for most workflows:
   - Phases (the timeline)
   - Timeline (the execution trace — same events, different ordering)
   - Raw spans (OTEL spans = same events again at one level deeper)
   - Ledger (the action ledger — overlaps with the OTEL spans)

4. **Audit panel** stacks 5 sub-sections (Evidence / Audit trail / Economics / Fleet assignment / Skill amplification) one above the other, all of which most operators never expand during a triage.

5. **Live reasoning** header shows ⏸ Awaiting + a strong-tag persona name AND duplicates the same content in the Decision card's "What Happened" paragraph.

6. **Header strip** shows `EXF-0002 employee-transfer awaiting_hitl` while the page title already shows the same; the Status pill and the `awaiting_hitl` label both encode the same fact.

**Why this happened.** The drawer was built additively over several plans (apex DrawerDecision, fleet-control feed redesign, AG-UI per-workflow drill-in, AGT authority chip) — each one added its own section guarded by feature flags / role booleans, with no opportunity to merge with what was already there. The Decision section in particular gained "Exception Analysis" / "Intervention Protocols" / "Decision actions" from three different PRs without a follow-up to dedupe.

**Fix sketch (post-demo).**
- Merge "Decision" subsections — one Decision card with one action row. Move the secondary buttons (Snooze 1h, Request additional docs) behind an overflow.
- Collapse Activity's four tabs into two: **Phases** (the timeline; absorb Ribbon visualisation as the header) + **Spans** (a single Raw spans / Ledger / Timeline merged view filterable by tool / phase). Ledger is a span subtype today — render it as such.
- Default Audit to collapsed (operator opt-in); turn its 5 sub-sections into a single chip strip + click-to-expand drawer-on-drawer.
- Make Live Reasoning + Decision narrative consume from the same SSE stream so the prose doesn't appear twice.

Estimated scope: 1-2 day refactor on `DrawerDecision.tsx`, `DrawerActivity.tsx`, `DrawerAudit.tsx`, removing 200-300 LOC net.

## Priority

1. **Bug 1** (Drawer 404 hang) — 30 min. Highest visibility, lowest risk. Ship first.
2. **Bug 2 option A** (non-clickable orphan resolutions) — 15 min. Removes the foot-gun that triggers Bug 1.
3. **Bug 3** (Drawer dedupe) — 1-2 days. Needs a design pass before code; out of scope for an emergency patch.

## Related

- [docs/superpowers/plans/2026-05-21-compose-domain-findings-employee-transfer.md](./2026-05-21-compose-domain-findings-employee-transfer.md) — the broader compose-domain findings doc from the same session; UX bloat (Bug 3) is C3-adjacent ("UX surfaces silently degraded for new domains") but distinct.
- [docs/superpowers/plans/2026-05-18-fleet-control-feed-redesign.md](./2026-05-18-fleet-control-feed-redesign.md) — the feed redesign that established the orphan-resolution decoration pattern in `useFeedItems.ts`.
