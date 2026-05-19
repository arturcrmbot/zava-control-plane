// web/client/hooks/useNotificationState.ts
//
// Per-role "what's still unread" state for the header notifications bell.
//
// The bell consumes the role's "needs you" feed which never decreases on its
// own (server-side HITL items stay open until acted on), so without this hook
// the bell only ever climbs and feels dead. Two affordances make it useful:
//
//   - markSeen(id)    — dismiss one item; fired when the user clicks it in
//                       the popover (which also navigates to the workflow)
//   - clearAll()      — bump a watermark past every currently-visible item;
//                       fired by the popover's "Clear all" link
//
// Persistence: `fleetctl.notif.<roleId>` → { seen: string[]; clearedAt: number }
//   - clearedAt is in *seconds* since epoch to match FeedItem.timestamp
//   - seen is bounded by clearAll() (which resets it to [])
//
// `isUnread(item)` is true iff `item.timestamp > clearedAt && !seen.has(id)`.
import { useCallback, useMemo } from "react";
import type { FeedItem } from "@shared/feedItems";
import { useLocalStorageState } from "./useLocalStorageState";

interface NotifState {
  seen: string[];
  clearedAt: number;     // seconds since epoch
}

const DEFAULT: NotifState = { seen: [], clearedAt: 0 };

function nowSec(): number {
  return Math.floor(Date.now() / 1000);
}

export interface NotificationAPI {
  unread: (items: FeedItem[]) => FeedItem[];
  count: (items: FeedItem[]) => number;
  markSeen: (id: string) => void;
  clearAll: () => void;
}

export function useNotificationState(roleId: string): NotificationAPI {
  const [state, setState] = useLocalStorageState<NotifState>(
    `fleetctl.notif.${roleId}`,
    DEFAULT,
  );

  const seenSet = useMemo(() => new Set(state.seen), [state.seen]);
  const clearedAt = state.clearedAt;

  const isUnread = useCallback(
    (it: FeedItem) => it.timestamp > clearedAt && !seenSet.has(it.id),
    [clearedAt, seenSet],
  );

  const unread = useCallback(
    (items: FeedItem[]) => items.filter(isUnread),
    [isUnread],
  );

  const count = useCallback(
    (items: FeedItem[]) => {
      let n = 0;
      for (const it of items) if (isUnread(it)) n += 1;
      return n;
    },
    [isUnread],
  );

  const markSeen = useCallback(
    (id: string) => {
      setState((prev) => {
        if (prev.seen.includes(id)) return prev;
        return { ...prev, seen: [...prev.seen, id] };
      });
    },
    [setState],
  );

  const clearAll = useCallback(() => {
    setState(() => ({ seen: [], clearedAt: nowSec() }));
  }, [setState]);

  return { unread, count, markSeen, clearAll };
}
