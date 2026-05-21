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
  buildWorkflowCards,
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
  mine?: boolean;        // when true, only items the operator has acted on
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
    const exceptionWorkflowIds = new Set(
      exceptions.filter((e) => !e.resolvedAt).map((e) => e.workflowId),
    );
    // De-dupe: when a workflow already has an open exception, drop its HITL
    // card. The ExceptionCard is richer (carries summary, recommendation,
    // severity, confidence, scenario context) and the HITL card for the
    // same workflow would just stack on top of it as an empty duplicate.
    const hitlCards = buildHITLCards(workflows).filter(
      (i) => !exceptionWorkflowIds.has(i.workflowId),
    );
    const items: FeedItem[] = [
      ...hitlCards,
      ...buildExceptionCards(exceptions, workflows),
      ...buildExternalWaitCards(workflows),
    ];
    if (filter.mode === "all-activity") {
      items.push(
        ...buildMilestoneCards(workflows),
        ...buildPolicyCards(policyEvents),
        ...buildAgentEventCards(
          fmEvents.map((e) => ({ kind: e.kind, timestamp: e.timestamp, data: e.data })),
          orchEvents.map((e) => ({
            kind: e.kind, timestamp: e.receivedAt, workflow_id: e.workflow_id, payload: e.payload,
          })),
        ),
      );
      // Generic workflow cards: ensure every workflow is observable
      // in the control plane. De-dup against the more-specific card
      // types so a workflow that already has a HITL / exception /
      // external-wait / milestone card doesn't double-render.
      // Only emitted in `all-activity` mode — `needs-you` is reserved
      // for cards that genuinely need the operator (HITL, exception,
      // external-wait).
      const coveredWorkflowIds = new Set<string>(
        items
          .map((i) => i.workflowId)
          .filter((id): id is string => typeof id === "string"),
      );
      items.push(
        ...buildWorkflowCards(workflows).filter(
          (i) => !coveredWorkflowIds.has(i.workflowId),
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
        originId: it.id,
        verb: r.verb,
        actor: r.actor,
        actedAt: r.actedAt,
      };
    });

    // Materialise resolved cards for any persisted resolution whose original
    // card has *already left* the live stream (server closed the exception,
    // SSE removed it). Without this fallback "All my decisions today"
    // empties out the moment the server confirms the action.
    const covered = new Set(
      decorated.filter((d) => d.type === "resolved").map((d) => d.id),
    );
    const wfById = new Map(workflows.map((w) => [w.id, w]));
    const orphanResolutions: FeedItem[] = [];
    for (const [origId, r] of Object.entries(resolutions.all())) {
      const resolvedId = `resolved:${origId}`;
      if (covered.has(resolvedId)) continue;
      // Best-effort domain/workflow lookup from the id prefix (e.g. "exception:EXC-..."
      // → fall through to workflow map via stripped id). We can't always
      // recover the workflowId post-eviction, so render the card with what
      // we have and skip the domain filter cleanly via domain=undefined.
      const m = origId.match(/^(?:exception|hitl|external-wait):(.+)$/);
      const stripped = m?.[1] ?? origId;
      const wf = wfById.get(stripped);
      orphanResolutions.push({
        type: "resolved" as const,
        id: resolvedId,
        timestamp: r.actedAt,
        // When the parent workflow has been evicted we deliberately leave
        // workflowId undefined so the card renders non-clickable rather
        // than deep-linking to a 404 drawer (the exception id is not a
        // workflow id).
        workflowId: wf?.id,
        domain: wf?.type,
        severity: null,
        originId: origId,
        verb: r.verb,
        actor: r.actor,
        actedAt: r.actedAt,
      });
    }
    const allItems = [...decorated, ...orphanResolutions];

    return chronological(
      allItems
        .filter((i) => role.visibleCardTypes.includes(i.type))
        .filter((i) => {
          if (!filter.mine) return true;
          // "my decisions today": only resolved cards (current session)
          if (i.type !== "resolved") return false;
          const cutoff = Date.now() / 1000 - 86_400;
          return (i.actedAt ?? 0) >= cutoff;
        })
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
  }, [
    workflows, exceptions, fmEvents, orchEvents, policyEvents, resolutions,
    role.visibleCardTypes,
    filter.mode, filter.domains, filter.severity, filter.search, filter.mine,
  ]);
}
