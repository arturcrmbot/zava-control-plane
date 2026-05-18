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
      if (
        merged.length === prev.length &&
        merged.every((m, idx) => m.id === prev[idx].id)
      ) {
        return prev;
      }
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
