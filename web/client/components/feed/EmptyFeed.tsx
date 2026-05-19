// web/client/components/feed/EmptyFeed.tsx
//
// Renders when the visible buffer is empty. Distinguishes two cases:
//   - no items at all (page is fresh, simulator hasn't spawned anything yet)
//   - items exist but are all filtered out (offer a "Clear filters" reset)
import { Inbox, FilterX } from "lucide-react";

export default function EmptyFeed({
  hasItems, onClearFilters,
}: {
  hasItems: boolean;
  onClearFilters: () => void;
}) {
  if (!hasItems) {
    return (
      <div
        data-testid="feed-empty-no-items"
        className="flex flex-col items-center justify-center text-center py-20 px-6 text-slate-500 dark:text-slate-400"
      >
        <Inbox size={40} className="text-slate-300 dark:text-slate-600 mb-3" aria-hidden />
        <div className="text-sm font-medium text-slate-700 dark:text-slate-200">
          You're all caught up
        </div>
        <div className="text-xs mt-1 max-w-sm">
          New work will appear here as it arrives. The feed is live — no need to refresh.
        </div>
      </div>
    );
  }
  return (
    <div
      data-testid="feed-empty-filtered"
      className="flex flex-col items-center justify-center text-center py-20 px-6 text-slate-500 dark:text-slate-400"
    >
      <FilterX size={40} className="text-slate-300 dark:text-slate-600 mb-3" aria-hidden />
      <div className="text-sm font-medium text-slate-700 dark:text-slate-200">
        No items match these filters
      </div>
      <div className="text-xs mt-1 max-w-sm">
        Try removing a domain chip, dropping the severity filter, or clearing the search.
      </div>
      <button
        type="button"
        onClick={onClearFilters}
        className="mt-4 text-xs px-3 py-1.5 rounded font-medium bg-blue-600 text-white hover:bg-blue-700"
      >Clear filters</button>
    </div>
  );
}
