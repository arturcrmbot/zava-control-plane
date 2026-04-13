// src/client/hooks/useSSE.ts
import { useEffect } from "react";
export function useSSE(path, onMessage) {
    useEffect(() => {
        const es = new EventSource(path);
        es.onmessage = (ev) => {
            try {
                onMessage(JSON.parse(ev.data));
            }
            catch {
                /* ignore parse errors */
            }
        };
        return () => es.close();
    }, [path, onMessage]);
}
