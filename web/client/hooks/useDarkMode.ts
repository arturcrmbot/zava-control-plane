// web/client/hooks/useDarkMode.ts
//
// Theme controller. `useDarkMode` exposes the current resolved theme
// ("light" | "dark"), the user's preference ("light" | "dark" | "system"),
// and setters. The actual <html class="dark"> toggle is performed as a
// side-effect inside the hook so any consumer applies it consistently.
//
// Precedence: user preference (localStorage) → prefers-color-scheme.
import { useEffect, useState, useCallback } from "react";
import { useLocalStorageState } from "./useLocalStorageState";

export type ThemePreference = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

function systemTheme(): ResolvedTheme {
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function useDarkMode(): {
  resolved: ResolvedTheme;
  preference: ThemePreference;
  setPreference: (p: ThemePreference) => void;
  toggle: () => void;
} {
  const [preference, setPreference] = useLocalStorageState<ThemePreference>(
    "fleetctl.theme", "system",
  );
  const [systemResolved, setSystemResolved] = useState<ResolvedTheme>(systemTheme);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => setSystemResolved(mq.matches ? "dark" : "light");
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const resolved: ResolvedTheme = preference === "system" ? systemResolved : preference;

  useEffect(() => {
    const root = document.documentElement;
    if (resolved === "dark") root.classList.add("dark");
    else root.classList.remove("dark");
  }, [resolved]);

  const toggle = useCallback(() => {
    // Toggle the resolved state, but write the explicit choice so future
    // page loads don't drift back to system preference unexpectedly.
    setPreference(resolved === "dark" ? "light" : "dark");
  }, [resolved, setPreference]);

  return { resolved, preference, setPreference, toggle };
}
