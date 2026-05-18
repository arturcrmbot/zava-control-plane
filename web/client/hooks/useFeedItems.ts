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
            kind: e.kind, timestamp: e.receivedAt, workflow_id: e.workflow_id, payload: e.payload,
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
  }, [
    workflows, exceptions, fmEvents, orchEvents, policyEvents, resolutions,
    role.visibleCardTypes,
    filter.mode, filter.domains, filter.severity, filter.search,
  ]);
}
