// web/client/components/feed/Header.tsx
//
// Sticky thin top row: brand · search · 🔔 · Today chip · RoleSwitcher.
// Today chip content is keyed off role.todayChip. Clock removed — system
// taskbar already shows it and the extra digits added clutter.
import { useState } from "react";
import { Link } from "react-router-dom";
import { Sun, Moon, Rows3, Rows4 } from "lucide-react";
import type { RoleId, RolePreset } from "@shared/roles";
import type { FeedItem } from "@shared/feedItems";
import type { Workflow } from "@shared/types";
import { useDarkMode } from "@client/hooks/useDarkMode";
import { useDensity } from "@client/hooks/useDensity";
import { useSSEStatus } from "@client/hooks/useSSE";
import { useReplayMeta } from "@client/hooks/useReplayMeta";
import RoleSwitcher from "./RoleSwitcher";
import NotificationsPopover from "./NotificationsPopover";
import { ReplayBadge } from "./ReplayBadge";

function TodayChip({ role, items, workflows }: { role: RolePreset; items: FeedItem[]; workflows: Workflow[] }) {
  if (role.todayChip === "needs-you-count") {
    const crit = items.filter((i) => i.severity === "critical").length;
    return <span className="text-xs text-slate-600 dark:text-slate-300">Today: {items.length} · {crit} crit</span>;
  }
  if (role.todayChip === "money-saved") {
    return <span className="text-xs text-slate-600 dark:text-slate-300">$ saved today: $—</span>;
  }
  if (role.todayChip === "hiring-summary") {
    const open = workflows.filter((w) => w.type === "hiring" && w.status !== "completed").length;
    return <span className="text-xs text-slate-600 dark:text-slate-300">Open roles: {open}</span>;
  }
  if (role.todayChip === "fleet-health") {
    return <span className="text-xs text-slate-600 dark:text-slate-300">Fleet health: green</span>;
  }
  if (role.todayChip === "executive-summary") {
    const completed = workflows.filter((w) => w.status === "completed").length;
    return <span className="text-xs text-slate-600 dark:text-slate-300">Throughput: {completed}</span>;
  }
  return null;
}

function ConnectionStatusDot() {
  const status = useSSEStatus();
  const map = {
    open:       { cls: "bg-emerald-500", label: "Live — receiving updates" },
    connecting: { cls: "bg-amber-400 animate-pulse", label: "Connecting…" },
    error:      { cls: "bg-red-500 animate-pulse", label: "Offline — feed is stale" },
  } as const;
  const { cls, label } = map[status];
  return (
    <span
      role="status"
      aria-label={label}
      title={label}
      className={`h-2 w-2 rounded-full ${cls}`}
    />
  );
}

export default function Header({
  role, onRoleChange, unreadItems, onJumpTo, onSearch, workflows,
}: {
  role: RolePreset;
  onRoleChange: (next: RoleId) => void;
  unreadItems: FeedItem[];
  onJumpTo: (itemId: string) => void;
  onSearch: (workflowId: string) => void;
  workflows: Workflow[];
}) {
  const [q, setQ] = useState("");
  const matches = q.trim().length === 0 ? [] :
    workflows.filter((w) => w.id.toLowerCase().includes(q.toLowerCase())).slice(0, 8);
  const { resolved: theme, toggle: toggleTheme } = useDarkMode();
  const { density, toggle: toggleDensity } = useDensity();
  const replayMeta = useReplayMeta();
  const ESSAY_URL = ((import.meta as any).env?.VITE_ESSAY_URL as string | undefined)
    ?? "https://arturcrmbot.github.io/zava-control-plane/";

  return (
    <header className="flex items-center gap-4 px-6 h-12 border-b border-slate-200 bg-white sticky top-0 z-30 dark:bg-slate-900 dark:border-slate-700">
      <Link to="/" className="font-semibold text-slate-900 dark:text-slate-100">Apex</Link>
      <span className="text-slate-300 dark:text-slate-600">·</span>
      <div className="relative">
        <input
          type="search"
          placeholder="Search workflows…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="text-xs border border-slate-200 rounded px-2 py-1 bg-white text-slate-700 w-64 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-200 dark:placeholder-slate-500"
        />
        {matches.length > 0 && (
          <div className="absolute left-0 top-full mt-1 bg-white border border-slate-200 rounded-md shadow-lg w-64 py-1 z-40 dark:bg-slate-800 dark:border-slate-700">
            {matches.map((w) => (
              <button
                key={w.id}
                type="button"
                onClick={() => { onSearch(w.id); setQ(""); }}
                className="w-full text-left text-xs px-3 py-1.5 hover:bg-slate-50 dark:hover:bg-slate-700 dark:text-slate-200"
              >{w.id}<span className="text-slate-400"> · {w.type}</span></button>
            ))}
          </div>
        )}
      </div>
      <div className="ml-auto flex items-center gap-3">
        <NotificationsPopover roleId={role.id} items={unreadItems} onJumpTo={onJumpTo} />
        <ConnectionStatusDot />
        <TodayChip role={role} items={unreadItems} workflows={workflows} />
        <button
          type="button"
          onClick={toggleDensity}
          aria-label={density === "compact" ? "Switch to cosy density" : "Switch to compact density"}
          title={density === "compact" ? "Switch to cosy density" : "Switch to compact density"}
          className="p-1.5 rounded text-slate-500 hover:text-slate-800 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-slate-100 dark:hover:bg-slate-800"
        >
          {density === "compact" ? <Rows3 size={16} /> : <Rows4 size={16} />}
        </button>
        <button
          type="button"
          onClick={toggleTheme}
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          className="p-1.5 rounded text-slate-500 hover:text-slate-800 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-slate-100 dark:hover:bg-slate-800"
        >
          {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
        </button>
        {replayMeta?.mode === "replay" && (
          <a
            href={`${ESSAY_URL}${ESSAY_URL.includes("?") ? "&" : "?"}from=demo`}
            className="text-xs text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-slate-100 underline-offset-4 hover:underline"
            rel="noopener noreferrer"
            target="_blank"
          >
            Read the essay →
          </a>
        )}
        <ReplayBadge />
        <RoleSwitcher current={role.id} onChange={onRoleChange} />
        <div className="w-7 h-7 rounded-full bg-slate-200 text-slate-600 text-xs flex items-center justify-center font-medium dark:bg-slate-700 dark:text-slate-200" aria-label="user avatar">A</div>
      </div>
    </header>
  );
}
