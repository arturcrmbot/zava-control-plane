// src/client/hooks/useFleetManagerStream.ts
import { useCallback, useRef, useState } from "react";
import { useSSE } from "./useSSE";
export function useFleetManagerStream(max = 50) {
    const [events, setEvents] = useState([]);
    const ref = useRef([]);
    useSSE("/api/stream/fleet-manager", useCallback((e) => {
        ref.current = [e, ...ref.current].slice(0, max);
        setEvents(ref.current.slice());
    }, [max]));
    return events;
}
