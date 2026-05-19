// web/client/hooks/useNewItemsBuffer.ts
//
// Facebook-timeline buffering. New items arriving while the user is at the
// TOP of the feed are inserted immediately (so the feed feels live). New
// items arriving while the user has scrolled DOWN are buffered behind a
// "↑ N new" pill (so the user's reading position never jumps).
//
// Design note (filter-change correctness):
// `visible` is *derived* from `items` minus `pendingIds`. We do NOT keep a
// separate `visible` array in state. That used to drift out of sync with
// `items` when the operator toggled a domain chip — items would vanish on
// narrow and never re-appear on widen because they were "known" (so not
// `incoming`) yet absent from the stale `visible` array. With derived
// visible, filter narrow/widen Just Works: pending is pruned to ids still
// present in items, and visible automatically picks up whatever remains.
import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import type { FeedItem } from "@shared/feedItems";

interface Options {
  autoInsertWhenAtTop?: boolean;
  scrollTopPx?: number;
  topThresholdPx?: number;
}

interface Result {
  visible: FeedItem[];
  pendingCount: number;
  pullIn: () => void;
}

export function useNewItemsBuffer(items: FeedItem[], opts: Options = {}): Result {
  const {
    autoInsertWhenAtTop = true,
    scrollTopPx = 0,
    topThresholdPx = 80,
  } = opts;

  const knownIds = useRef<Set<string>>(new Set(items.map((i) => i.id)));
  const hasBaselineRef = useRef<boolean>(items.length > 0);
  const [pendingIds, setPendingIds] = useState<Set<string>>(() => new Set());

  // Keep latest scroll position in a ref so the items-changed effect can
  // read it without itself depending on scroll updates (which would re-run
  // the diff on every scroll event).
  const scrollPxRef = useRef<number>(scrollTopPx);
  useEffect(() => { scrollPxRef.current = scrollTopPx; }, [scrollTopPx]);

  useEffect(() => {
    // Initial-baseline path: if the hook mounted with [] (data not yet
    // loaded), treat the first non-empty arrival as the baseline rather
    // than buffering every item into pending. Otherwise the operator
    // would land on an empty feed with a "↑ N new" pill.
    if (!hasBaselineRef.current) {
      if (items.length === 0) return;
      hasBaselineRef.current = true;
      knownIds.current = new Set(items.map((i) => i.id));
      return;
    }

    const itemIds = new Set(items.map((i) => i.id));
    const incoming = items.filter((i) => !knownIds.current.has(i.id));
    for (const it of incoming) knownIds.current.add(it.id);

    const atTop = autoInsertWhenAtTop && scrollPxRef.current <= topThresholdPx;

    setPendingIds((prev) => {
      // 1) Drop pending ids that vanished from items (filter narrowed,
      //    workflow resolved, etc.).
      const filtered = new Set<string>();
      for (const id of prev) if (itemIds.has(id)) filtered.add(id);

      if (atTop) {
        // At top: nothing is pending — everything goes to visible.
        if (filtered.size === 0 && prev.size === 0) return prev;
        return new Set();
      }

      // 2) Add genuinely-new arrivals to pending.
      for (const it of incoming) filtered.add(it.id);

      // Only allocate a new Set if changed (referential stability avoids
      // pointless visible recomputes).
      if (
        filtered.size === prev.size &&
        [...filtered].every((id) => prev.has(id))
      ) {
        return prev;
      }
      return filtered;
    });
  }, [items, autoInsertWhenAtTop, topThresholdPx]);

  const lastVisibleRef = useRef<FeedItem[] | null>(null);
  const visible = useMemo(() => {
    const next = items.filter((i) => !pendingIds.has(i.id));
    // Preserve referential stability across renders when nothing material
    // changed (same ids and same severities, same order). React.memo'd card
    // children and downstream useMemo callers rely on this — otherwise every
    // upstream re-render would re-render the entire visible list.
    const prev = lastVisibleRef.current;
    if (
      prev &&
      prev.length === next.length &&
      prev.every((p, idx) => p.id === next[idx].id && p.severity === next[idx].severity)
    ) {
      return prev;
    }
    lastVisibleRef.current = next;
    return next;
  }, [items, pendingIds]);
  const pendingCount = useMemo(
    () => items.reduce((n, i) => (pendingIds.has(i.id) ? n + 1 : n), 0),
    [items, pendingIds],
  );

  const pullIn = useCallback(() => {
    setPendingIds((prev) => (prev.size === 0 ? prev : new Set()));
  }, []);

  return { visible, pendingCount, pullIn };
}
