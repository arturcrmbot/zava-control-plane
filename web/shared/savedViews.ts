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
  // Truthy check intentionally treats null and undefined identically: both mean
  // "no severity filter" for v1. A future caller wanting "items with no severity
  // only" should use a tagged value (e.g. "none") rather than overloading null.
  if (v.severity && item.severity !== v.severity) return false;
  if (v.search && v.search.trim().length > 0) {
    const needle = v.search.trim().toLowerCase();
    const haystack = (item.workflowId ?? "").toLowerCase();
    if (!haystack.includes(needle)) return false;
  }
  return true;
}
