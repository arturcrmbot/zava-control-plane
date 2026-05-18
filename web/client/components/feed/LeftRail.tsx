// web/client/components/feed/LeftRail.tsx
//
// 160-200px sidebar: role-default saved views + user-added saved views +
// More ▾ submenu containing the demoted secondary routes + Constellation
// external link at the bottom.
import { useState } from "react";
import { NavLink } from "react-router-dom";
import { ChevronDown, Plus } from "lucide-react";
import type { RolePreset, SavedView } from "@shared/roles";

const ROUTE_LABEL: Record<string, string> = {
  "/analytics": "Analytics",
  "/evals": "Evaluations",
  "/economics": "Economics",
  "/policy": "Policy",
};

const VITE_PORTS = new Set(["5273", "5274", "5275"]);
function constellationUrl(): string {
  const fromEnv = (import.meta.env.VITE_BLUEPRINT_URL as string | undefined)?.trim();
  if (fromEnv) return `${fromEnv.replace(/\/$/, "")}/?view=constellation&from=fleet`;
  if (typeof window !== "undefined" && VITE_PORTS.has(window.location.port)) {
    return `${window.location.protocol}//${window.location.hostname}:5275/?view=constellation&from=fleet`;
  }
  return "/?view=constellation&from=fleet";
}

export default function LeftRail({
  role, userViews, onSelectView, onSaveCurrent,
}: {
  role: RolePreset;
  userViews: SavedView[];
  onSelectView: (v: SavedView) => void;
  onSaveCurrent: () => void;
}) {
  const [moreOpen, setMoreOpen] = useState(false);
  const allViews = [...role.defaultSavedViews, ...userViews];

  return (
    <aside className="w-[200px] shrink-0 bg-white border-r border-slate-200 p-3 flex flex-col gap-3 text-sm overflow-y-auto">
      <div>
        <div className="text-[10px] uppercase tracking-wide text-slate-400 px-2 mb-1">Saved views</div>
        <div className="space-y-0.5">
          {allViews.map((v) => (
            <button
              key={v.id}
              type="button"
              onClick={() => onSelectView(v)}
              className="block w-full text-left text-xs px-3 py-1.5 rounded text-slate-700 hover:bg-slate-100"
            >{v.label}</button>
          ))}
          <button
            type="button"
            onClick={onSaveCurrent}
            className="flex items-center gap-1 text-[11px] px-3 py-1.5 text-slate-500 hover:text-slate-700"
          ><Plus size={12} /> Save current filter</button>
        </div>
      </div>

      <div className="mt-auto">
        <button
          type="button"
          onClick={() => setMoreOpen((v) => !v)}
          className="flex items-center justify-between w-full text-[11px] uppercase tracking-wide text-slate-400 px-2 py-1 hover:text-slate-600"
        >
          More
          <ChevronDown size={12} className={moreOpen ? "rotate-180 transition" : "transition"} />
        </button>
        {moreOpen && (
          <div className="space-y-0.5">
            {role.moreOrder.map((to) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `block text-xs px-3 py-1.5 rounded ${isActive ? "bg-blue-50 text-blue-700 font-medium" : "text-slate-700 hover:bg-slate-100"}`
                }
              >{ROUTE_LABEL[to] ?? to}</NavLink>
            ))}
          </div>
        )}
        <a
          href={constellationUrl()}
          target="_blank" rel="noopener noreferrer"
          className="block text-xs px-3 py-1.5 mt-1 rounded text-slate-700 hover:bg-slate-100"
        >Constellation ↗</a>
      </div>
    </aside>
  );
}
