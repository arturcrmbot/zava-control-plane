// web/client/components/feed/LeftRail.tsx
//
// Collapsible sidebar (160–200px expanded → 44px collapsed). Houses role
// saved views, user-added saved views, and the More ▾ submenu with the
// demoted secondary routes.
import { useState } from "react";
import { NavLink } from "react-router-dom";
import { ChevronDown, ChevronsLeft, ChevronsRight, Plus, BarChart3, Brain, Network, Sparkles } from "lucide-react";
import type { RolePreset, SavedView } from "@shared/roles";
import { useLocalStorageState } from "@client/hooks/useLocalStorageState";

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
  const [collapsed, setCollapsed] = useLocalStorageState<boolean>("fleetctl.leftRail.collapsed", false);
  const [moreOpen, setMoreOpen] = useState(false);
  const allViews = [...role.defaultSavedViews, ...userViews];

  if (collapsed) {
    return (
      <aside className="w-[44px] shrink-0 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-700 p-2 flex flex-col items-center gap-2">
        <button
          type="button"
          onClick={() => setCollapsed(false)}
          aria-label="Expand sidebar"
          title="Expand sidebar"
          className="p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500 dark:text-slate-400"
        ><ChevronsRight size={16} /></button>
        <NavLink
          to="/dashboard"
          aria-label="Dashboard"
          title="Dashboard"
          className={({ isActive }) =>
            `p-1.5 rounded ${isActive ? "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300" : "text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"}`
          }
        ><BarChart3 size={16} /></NavLink>
      </aside>
    );
  }

  return (
    <aside className="w-[200px] shrink-0 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-700 p-3 flex flex-col gap-3 text-sm overflow-y-auto">
      <div className="flex items-center justify-between">
        <div className="text-[10px] uppercase tracking-wide text-slate-400 dark:text-slate-500 px-2">Saved views</div>
        <button
          type="button"
          onClick={() => setCollapsed(true)}
          aria-label="Collapse sidebar"
          title="Collapse sidebar"
          className="p-1 rounded text-slate-400 dark:text-slate-500 hover:text-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800"
        ><ChevronsLeft size={14} /></button>
      </div>
      <div>
        <div className="space-y-0.5">
          {allViews.map((v) => (
            <button
              key={v.id}
              type="button"
              onClick={() => onSelectView(v)}
              className="block w-full text-left text-xs px-3 py-1.5 rounded text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
            >{v.label}</button>
          ))}
          <button
            type="button"
            onClick={onSaveCurrent}
            className="flex items-center gap-1 text-[11px] px-3 py-1.5 text-slate-500 dark:text-slate-400 hover:text-slate-700"
          ><Plus size={12} /> Save current filter</button>
        </div>
      </div>

      <NavLink
        to="/dashboard"
        className={({ isActive }) =>
          `flex items-center gap-2 text-xs px-3 py-1.5 rounded ${isActive ? "bg-blue-50 text-blue-700 font-medium dark:bg-blue-900/30 dark:text-blue-300" : "text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"}`
        }
      ><BarChart3 size={14} /> Dashboard</NavLink>

      <NavLink
        to="/memory"
        className={({ isActive }) =>
          `flex items-center gap-2 text-xs px-3 py-1.5 rounded ${isActive ? "bg-blue-50 text-blue-700 font-medium dark:bg-blue-900/30 dark:text-blue-300" : "text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"}`
        }
      ><Brain size={14} /> Memory</NavLink>

      <NavLink
        to="/knowledge"
        className={({ isActive }) =>
          `flex items-center gap-2 text-xs px-3 py-1.5 rounded ${isActive ? "bg-blue-50 text-blue-700 font-medium dark:bg-blue-900/30 dark:text-blue-300" : "text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"}`
        }
      ><Network size={14} /> Knowledge</NavLink>

      <a
        href={constellationUrl()}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-2 text-xs px-3 py-1.5 rounded text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
      ><Sparkles size={14} /> Constellation ↗</a>

      <div className="mt-auto">
        <button
          type="button"
          onClick={() => setMoreOpen((v) => !v)}
          className="flex items-center justify-between w-full text-[11px] uppercase tracking-wide text-slate-400 dark:text-slate-500 px-2 py-1 hover:text-slate-600"
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
                  `block text-xs px-3 py-1.5 rounded ${isActive ? "bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-300 font-medium" : "text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"}`
                }
              >{ROUTE_LABEL[to] ?? to}</NavLink>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}
