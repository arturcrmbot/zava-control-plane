// src/client/hooks/useWorkflows.ts
import { useCallback, useEffect, useState } from "react";
import type { Workflow } from "@shared/types";
import { useSSE } from "./useSSE";

export function useWorkflows() {
  const [items, setItems] = useState<Workflow[]>([]);

  const refresh = useCallback(async () => {
    const r = await fetch("/api/workflows");
    setItems((await r.json()) as Workflow[]);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useSSE<{ type: string }>(
    "/api/stream/fleet",
    useCallback(
      (e) => {
        if (e.type.startsWith("workflow.") || e.type === "otel.span.emitted") void refresh();
      },
      [refresh]
    )
  );

  return items;
}
