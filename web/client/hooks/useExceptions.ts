// src/client/hooks/useExceptions.ts
import { useCallback, useEffect, useState } from "react";
import type { Exception } from "@shared/types";
import { useSSE } from "./useSSE";

export function useExceptions() {
  const [items, setItems] = useState<Exception[]>([]);

  const refresh = useCallback(async () => {
    const r = await fetch("/api/exceptions");
    setItems((await r.json()) as Exception[]);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useSSE<{ type: string }>(
    "/api/stream/fleet",
    useCallback(() => {
      void refresh();
    }, [refresh])
  );

  return { items, refresh };
}
