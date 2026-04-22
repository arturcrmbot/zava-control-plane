// src/client/hooks/useOrchestrationStream.ts
import { useCallback, useRef, useState } from "react";
import { useSSE } from "./useSSE";
export function useOrchestrationStream(max = 100) {
    const [events, setEvents] = useState([]);
    const ref = useRef([]);
    useSSE("/api/stream/orchestration", useCallback((e) => {
        ref.current = [e, ...ref.current].slice(0, max);
        setEvents(ref.current.slice());
    }, [max]));
    return events;
}
