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
  const initialRef = useRef<T>(defaultValue);
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = typeof window !== "undefined" ? window.localStorage.getItem(key) : null;
      if (raw == null) return defaultValue;
      return JSON.parse(raw) as T;
    } catch {
      return defaultValue;
    }
  });

  useEffect(() => {
    initialRef.current = defaultValue;
    // intentionally do not write the default on mount; only writes from
    // setter calls are persisted, so the default never overwrites a value
    // a different tab wrote first.
  }, [defaultValue]);

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
