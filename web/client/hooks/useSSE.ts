// src/client/hooks/useSSE.ts
import { useEffect } from "react";

export function useSSE<T>(path: string, onMessage: (data: T) => void): void {
  useEffect(() => {
    const es = new EventSource(path);
    es.onmessage = (ev) => {
      try {
        onMessage(JSON.parse(ev.data) as T);
      } catch {
        /* ignore parse errors */
      }
    };
    return () => es.close();
  }, [path, onMessage]);
}
