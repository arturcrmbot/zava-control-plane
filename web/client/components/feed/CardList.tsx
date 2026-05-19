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
  focusedIndex,
}: {
  items: FeedItem[];
  hideActions: boolean;
  onOpenDrawer: (workflowId: string) => void;
  selectMode: boolean;
  selected: Set<string>;
  onToggleSelect: (itemId: string) => void;
  focusedIndex?: number;
}) {
  const [limit, setLimit] = useState(PAGE);

  if (items.length === 0) {
    return (
      <div className="text-sm text-slate-500 dark:text-slate-400 italic px-2 py-8 text-center border border-dashed border-slate-200 dark:border-slate-700 rounded">
        Nothing here. Try switching to "All activity".
      </div>
    );
  }

  const visible = items.slice(0, limit);

  return (
    <div className="space-y-3">
      {visible.map((it, idx) => (
        <div
          key={it.id}
          data-feed-idx={idx}
          className={`flex items-start gap-2 rounded-lg ${
            idx === focusedIndex ? "ring-2 ring-blue-400 dark:ring-blue-500 ring-offset-2 ring-offset-slate-50 dark:ring-offset-slate-950" : ""
          }`}
        >
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
            className="text-xs px-3 py-1.5 rounded bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 ring-1 ring-slate-300 dark:ring-slate-600 hover:bg-slate-50 dark:hover:bg-slate-800"
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
