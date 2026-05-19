// src/client/hooks/useWorkflows.ts
import { useCallback, useEffect, useState } from "react";
import type { Workflow } from "@shared/types";
import { useSSE } from "./useSSE";
import { useThrottledFetch } from "./useThrottledFetch";

export function useWorkflows() {
  const [items, setItems] = useState<Workflow[]>([]);
  const refresh = useThrottledFetch<Workflow[]>("/api/workflows", setItems, 750);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useSSE<{ type: string }>(
    "/api/stream/fleet",
    useCallback(
      (e) => {
        if (e.type.startsWith("workflow.") || e.type === "otel.span.emitted") refresh();
      },
      [refresh]
    )
  );

  return items;
}
