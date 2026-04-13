// src/client/hooks/useWorkflows.ts
import { useCallback, useEffect, useState } from "react";
import { useSSE } from "./useSSE";
export function useWorkflows() {
    const [items, setItems] = useState([]);
    const refresh = useCallback(async () => {
        const r = await fetch("/api/workflows");
        setItems((await r.json()));
    }, []);
    useEffect(() => {
        void refresh();
    }, [refresh]);
    useSSE("/api/stream/fleet", useCallback((e) => {
        if (e.type.startsWith("workflow.") || e.type === "otel.span.emitted")
            void refresh();
    }, [refresh]));
    return items;
}
