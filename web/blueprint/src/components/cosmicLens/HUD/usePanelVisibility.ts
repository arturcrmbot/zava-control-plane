/**
 * usePanelVisibility — tiny shared hook for "which HUD panels are visible".
 *
 * Backed by localStorage so refreshes preserve the user's choices.
 * The PanelPicker top-right chip is the canonical UI for toggling these.
 */
import { useCallback, useEffect, useState } from "react";

export type PanelId =
  | "narrative-arcs"
  | "knowledge-pulse"
  | "activity-rail"
  | "time-scrub";

// Stale ids that may still be in users' localStorage from a previous build.
// Filtered out on read so they don't keep panels permanently hidden.
const RETIRED_IDS = new Set<string>(["vital-signs"]);

const STORAGE_KEY = "zava.hud.hidden";

// Default-visible panels at first load. Anything added after a user hid it
// stays hidden until they un-hide it.
const DEFAULT_HIDDEN: PanelId[] = [
  // none — first load shows everything; user picks what to drop
];

function readHidden(): Set<PanelId> {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as string[];
      return new Set(parsed.filter((id) => !RETIRED_IDS.has(id)) as PanelId[]);
    }
  } catch {
    /* ignore */
  }
  return new Set(DEFAULT_HIDDEN);
}

function writeHidden(s: Set<PanelId>) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify([...s]));
  } catch {
    /* ignore */
  }
  // Notify other instances of the hook in the same window.
  window.dispatchEvent(new CustomEvent("zava-panel-visibility"));
}

export function usePanelVisibility() {
  const [hidden, setHidden] = useState<Set<PanelId>>(() => readHidden());

  useEffect(() => {
    const reload = () => setHidden(readHidden());
    window.addEventListener("zava-panel-visibility", reload);
    window.addEventListener("storage", reload);
    return () => {
      window.removeEventListener("zava-panel-visibility", reload);
      window.removeEventListener("storage", reload);
    };
  }, []);

  const visible = useCallback((id: PanelId) => !hidden.has(id), [hidden]);
  const toggle = useCallback((id: PanelId) => {
    const next = new Set(hidden);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    writeHidden(next);
    setHidden(next);
  }, [hidden]);
  const showAll = useCallback(() => {
    writeHidden(new Set());
    setHidden(new Set());
  }, []);
  const hideAll = useCallback(() => {
    const all = new Set<PanelId>(["narrative-arcs", "knowledge-pulse", "activity-rail", "time-scrub"]);
    writeHidden(all);
    setHidden(all);
  }, []);

  return { hidden, visible, toggle, showAll, hideAll };
}
