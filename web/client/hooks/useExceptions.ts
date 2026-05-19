// src/client/hooks/useExceptions.ts
import { useCallback, useEffect, useState } from "react";
import type { Exception } from "@shared/types";
import { useSSE } from "./useSSE";
import { useThrottledFetch } from "./useThrottledFetch";

export function useExceptions() {
  const [items, setItems] = useState<Exception[]>([]);
  const refresh = useThrottledFetch<Exception[]>("/api/exceptions", setItems, 750);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useSSE<{ type: string }>(
    "/api/stream/fleet",
    useCallback(() => {
      refresh();
    }, [refresh])
  );

  return { items, refresh };
}
