// web/client/components/feed/FilterBar.tsx
//
// Top-of-feed control bar: segmented mode toggle, domain chips (collapsed
// to top 6 by default with a "+N more" expander), severity pill,
// select-mode toggle, search input. Emits a fresh FilterState on every
// change via onChange.
import { useMemo, useState } from "react";
import type { FilterState } from "@client/hooks/useFeedItems";

const SEVERITY_CHOICES: Array<FilterState["severity"]> = [null, "critical", "high", "medium"];
const VISIBLE_CHIPS = 6;

export default function FilterBar({
  filter, onChange, selectMode, onSelectModeChange, availableDomains,
}: {
  filter: FilterState;
  onChange: (next: FilterState) => void;
  selectMode: boolean;
  onSelectModeChange: (next: boolean) => void;
  availableDomains: string[];
}) {
  const setMode = (mode: FilterState["mode"]) => onChange({ ...filter, mode });
  const toggleDomain = (d: string) => {
    const has = filter.domains.includes(d);
    onChange({ ...filter, domains: has ? filter.domains.filter((x) => x !== d) : [...filter.domains, d] });
  };
  const setSeverity = (s: FilterState["severity"]) => onChange({ ...filter, severity: s });
  const setSearch = (s: string) => onChange({ ...filter, search: s });
  const [chipsExpanded, setChipsExpanded] = useState(false);

  // Always show active filter chips + the first N inactive ones, so the
  // user's current selection never disappears behind the +more toggle.
  const orderedChips = useMemo(() => {
    const active = availableDomains.filter((d) => filter.domains.includes(d));
    const inactive = availableDomains.filter((d) => !filter.domains.includes(d));
    return [...active, ...inactive];
  }, [availableDomains, filter.domains]);
  const visibleChips = chipsExpanded ? orderedChips : orderedChips.slice(0, VISIBLE_CHIPS);
  const hiddenCount = orderedChips.length - visibleChips.length;

  return (
    <div className="flex items-center gap-2 flex-wrap bg-white border border-slate-200 rounded-lg p-2 dark:bg-slate-900 dark:border-slate-700">
      <div className="inline-flex rounded-md border border-slate-200 overflow-hidden dark:border-slate-700">
        <button
          type="button" onClick={() => setMode("needs-you")}
          className={`text-xs px-3 py-1.5 font-medium ${filter.mode === "needs-you" ? "bg-blue-600 text-white" : "bg-white text-slate-600 hover:bg-slate-50 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"}`}
        >● Needs you</button>
        <button
          type="button" onClick={() => setMode("all-activity")}
          className={`text-xs px-3 py-1.5 font-medium border-l border-slate-200 dark:border-slate-700 ${filter.mode === "all-activity" ? "bg-blue-600 text-white" : "bg-white text-slate-600 hover:bg-slate-50 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"}`}
        >All activity</button>
      </div>

      <div className="flex items-center gap-1 flex-wrap">
        {visibleChips.map((d) => {
          const active = filter.domains.includes(d);
          return (
            <button
              key={d}
              type="button"
              onClick={() => toggleDomain(d)}
              className={`text-[11px] px-2 py-1 rounded font-medium ${active ? "bg-slate-700 text-white dark:bg-slate-200 dark:text-slate-900" : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"}`}
            >{d}</button>
          );
        })}
        {hiddenCount > 0 && (
          <button
            type="button"
            onClick={() => setChipsExpanded(true)}
            className="text-[11px] px-2 py-1 rounded font-medium text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
            aria-label={`Show ${hiddenCount} more domains`}
          >+{hiddenCount} more</button>
        )}
        {chipsExpanded && orderedChips.length > VISIBLE_CHIPS && (
          <button
            type="button"
            onClick={() => setChipsExpanded(false)}
            className="text-[11px] px-2 py-1 rounded font-medium text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
          >less</button>
        )}
      </div>

      <select
        aria-label="Severity"
        value={filter.severity ?? ""}
        onChange={(e) => setSeverity((e.target.value || null) as FilterState["severity"])}
        className="text-xs border border-slate-200 rounded px-2 py-1 bg-white text-slate-700 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-200"
      >
        {SEVERITY_CHOICES.map((s) => (
          <option key={s ?? ""} value={s ?? ""}>{s == null ? "any severity" : s}</option>
        ))}
      </select>

      <input
        type="search"
        placeholder="Search…"
        value={filter.search}
        onChange={(e) => setSearch(e.target.value)}
        className="text-xs border border-slate-200 rounded px-2 py-1 bg-white text-slate-700 w-40 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-200 dark:placeholder-slate-500"
      />

      <button
        type="button"
        onClick={() => onSelectModeChange(!selectMode)}
        className={`ml-auto text-xs px-3 py-1.5 rounded font-medium ${selectMode ? "bg-blue-600 text-white" : "text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"}`}
      >{selectMode ? "Done" : "Select"}</button>
    </div>
  );
}
