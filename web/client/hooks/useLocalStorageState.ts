// web/client/hooks/useLocalStorageState.ts
//
// useState-shaped hook backed by localStorage. Used for fleetctl.* keys
// (role, savedViews, leftRailCollapsed, criticalToasts, layoutDense).
import { useCallback, useEffect, useRef, useState } from "react";

type Updater<T> = T | ((prev: T) => T);

export function useLocalStorageState<T>(
  key: string,
  defaultValue: T,
): [T, (next: Updater<T>) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = typeof window !== "undefined" ? window.localStorage.getItem(key) : null;
      if (raw == null) return defaultValue;
      return JSON.parse(raw) as T;
    } catch {
      return defaultValue;
    }
  });

  const isFirstRunRef = useRef(true);
  useEffect(() => {
    if (isFirstRunRef.current) {
      isFirstRunRef.current = false;
      return;
    }
    try {
      const raw = window.localStorage.getItem(key);
      setValue(raw == null ? defaultValue : (JSON.parse(raw) as T));
    } catch {
      setValue(defaultValue);
    }
    // Intentionally only re-run on `key` change; defaultValue identity changes
    // are not a sync signal. If the caller wants a forced reset, they should
    // change the key.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const set = useCallback(
    (next: Updater<T>) => {
      setValue((prev) => {
        const resolved =
          typeof next === "function" ? (next as (p: T) => T)(prev) : next;
        try {
          window.localStorage.setItem(key, JSON.stringify(resolved));
        } catch {
          /* quota or disabled — ignore */
        }
        return resolved;
      });
    },
    [key],
  );

  return [value, set];
}
