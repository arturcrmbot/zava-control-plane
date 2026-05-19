// web/client/components/feed/FilterBar.tsx
//
// Top-of-feed control bar: segmented mode toggle, domain chips, severity
// pill, select-mode toggle, search input. Emits a fresh FilterState on
// every change via onChange.
import type { FilterState } from "@client/hooks/useFeedItems";

const SEVERITY_CHOICES: Array<FilterState["severity"]> = [null, "critical", "high", "medium"];

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

  return (
    <div className="flex items-center gap-2 flex-wrap bg-white border border-slate-200 rounded-lg p-2">
      <div className="inline-flex rounded-md border border-slate-200 overflow-hidden">
        <button
          type="button" onClick={() => setMode("needs-you")}
          className={`text-xs px-3 py-1.5 font-medium ${filter.mode === "needs-you" ? "bg-blue-600 text-white" : "bg-white text-slate-600 hover:bg-slate-50"}`}
        >● Needs you</button>
        <button
          type="button" onClick={() => setMode("all-activity")}
          className={`text-xs px-3 py-1.5 font-medium border-l border-slate-200 ${filter.mode === "all-activity" ? "bg-blue-600 text-white" : "bg-white text-slate-600 hover:bg-slate-50"}`}
        >All activity</button>
      </div>

      <div className="flex items-center gap-1 flex-wrap">
        {availableDomains.map((d) => {
          const active = filter.domains.includes(d);
          return (
            <button
              key={d}
              type="button"
              onClick={() => toggleDomain(d)}
              className={`text-[11px] px-2 py-1 rounded font-medium ${active ? "bg-slate-700 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}
            >{d}</button>
          );
        })}
      </div>

      <select
        aria-label="Severity"
        value={filter.severity ?? ""}
        onChange={(e) => setSeverity((e.target.value || null) as FilterState["severity"])}
        className="text-xs border border-slate-200 rounded px-2 py-1 bg-white text-slate-700"
      >
        {SEVERITY_CHOICES.map((s) => (
          <option key={s ?? ""} value={s ?? ""}>{s == null ? "any severity" : s}</option>
        ))}
      </select>

      <input
        type="search"
        placeholder="Search workflow id…"
        value={filter.search}
        onChange={(e) => setSearch(e.target.value)}
        className="text-xs border border-slate-200 rounded px-2 py-1 bg-white text-slate-700 w-48"
      />

      <button
        type="button"
        onClick={() => onSelectModeChange(!selectMode)}
        className={`ml-auto text-xs px-3 py-1.5 rounded font-medium ${selectMode ? "bg-blue-600 text-white" : "bg-white text-slate-600 ring-1 ring-slate-300 hover:bg-slate-50"}`}
      >{selectMode ? "Done" : "Select"}</button>
    </div>
  );
}
