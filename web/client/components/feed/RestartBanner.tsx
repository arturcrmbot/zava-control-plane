import { useCallback, useEffect, useRef, useState } from "react";
import { useSSE } from "@client/hooks/useSSE";

const BANNER_TTL_MS = 3_000;

interface BlueprintStreamEvent {
  type?: string;
}

export function RestartBanner() {
  const [visible, setVisible] = useState(false);
  const timeoutRef = useRef<number | null>(null);

  const handleMessage = useCallback((message: BlueprintStreamEvent) => {
    if (message?.type !== "playback.restart.pending") return;
    if (timeoutRef.current !== null) clearTimeout(timeoutRef.current);
    setVisible(true);
    timeoutRef.current = window.setTimeout(() => {
      setVisible(false);
      timeoutRef.current = null;
    }, BANNER_TTL_MS);
  }, []);

  useSSE<BlueprintStreamEvent>("/api/blueprint/stream", handleMessage);

  useEffect(() => () => {
    if (timeoutRef.current !== null) clearTimeout(timeoutRef.current);
  }, []);

  if (!visible) return null;

  return (
    <div
      role="status"
      className="fixed inset-x-0 top-0 z-50 flex items-center justify-center"
    >
      <div className="rounded-b bg-slate-900/95 px-4 py-2 text-sm text-white shadow">
        Replay restarting…
      </div>
    </div>
  );
}
