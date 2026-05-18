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
  const hasBaselineRef = useRef<boolean>(items.length > 0);
  const [pending, setPending] = useState<FeedItem[]>([]);

  useEffect(() => {
    // Initial-baseline path: if the hook mounted with [] (data not yet
    // loaded), treat the first non-empty arrival as the baseline rather
    // than buffering every item into `pending`. Otherwise the operator
    // would land on an empty feed with a "↑ N new" pill, contradicting
    // the spec's "buffer items arriving *while* the user is reading".
    if (!hasBaselineRef.current) {
      if (items.length === 0) return;
      hasBaselineRef.current = true;
      knownIds.current = new Set(items.map((i) => i.id));
      setVisible(items);
      return;
    }

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
      // Bailout: when ids AND severity all match in order, return prev
      // (same reference) to short-circuit React's re-render. This breaks
      // the infinite loop when the upstream returns a new array reference
      // on every render. Severity is included in the comparison because
      // it's the most-frequently-changing user-visible field (border
      // colour, badge) — without it, severity escalations on existing
      // cards would be lost. Other content-field changes on existing
      // visible items are an accepted v1 limitation; consumers needing
      // field-level updates should re-key the card via id.
      if (
        merged.length === prev.length &&
        merged.every((m, idx) =>
          m.id === prev[idx].id && m.severity === prev[idx].severity,
        )
      ) {
        return prev;
      }
      return merged;
    });
  }, [items]);

  const pullIn = useCallback(() => {
    if (pending.length === 0) return;
    setVisible((prev) => {
      const ids = new Set(prev.map((i) => i.id));
      const fresh = pending.filter((p) => !ids.has(p.id));
      if (fresh.length === 0) return prev;
      return [...fresh, ...prev];
    });
    setPending([]);
  }, [pending]);

  return { visible, pendingCount: pending.length, pullIn };
}
