// src/client/hooks/useExceptions.ts
import { useCallback, useEffect, useState } from "react";
import { useSSE } from "./useSSE";
export function useExceptions() {
    const [items, setItems] = useState([]);
    const refresh = useCallback(async () => {
        const r = await fetch("/api/exceptions");
        setItems((await r.json()));
    }, []);
    useEffect(() => {
        void refresh();
    }, [refresh]);
    useSSE("/api/stream/fleet", useCallback(() => {
        void refresh();
    }, [refresh]));
    return { items, refresh };
}
