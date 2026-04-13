// src/client/hooks/useFleetManagerStream.ts
import { useCallback, useRef, useState } from "react";
import { useSSE } from "./useSSE";

export interface FMLive {
  kind: "idle" | "wakeup" | "reasoning_start" | "tool_call" | "reasoning_done" | "error";
  timestamp: number;
  data?: unknown;
}

export function useFleetManagerStream(max = 50) {
  const [events, setEvents] = useState<FMLive[]>([]);
  const ref = useRef<FMLive[]>([]);

  useSSE<FMLive>(
    "/api/stream/fleet-manager",
    useCallback(
      (e) => {
        ref.current = [e, ...ref.current].slice(0, max);
        setEvents(ref.current.slice());
      },
      [max]
    )
  );

  return events;
}
