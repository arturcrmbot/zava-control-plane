// web/client/components/feed/Header.tsx
//
// Sticky thin top row: brand · search · 🔔 · Today chip · RoleSwitcher.
// Today chip content is keyed off role.todayChip.
import { useState } from "react";
import { Link } from "react-router-dom";
import type { RoleId, RolePreset } from "@shared/roles";
import type { FeedItem } from "@shared/feedItems";
import type { Workflow } from "@shared/types";
import RoleSwitcher from "./RoleSwitcher";
import NotificationsPopover from "./NotificationsPopover";

function TodayChip({ role, items, workflows }: { role: RolePreset; items: FeedItem[]; workflows: Workflow[] }) {
  if (role.todayChip === "needs-you-count") {
    const crit = items.filter((i) => i.severity === "critical").length;
    return <span className="text-xs text-slate-600">Today: {items.length} · {crit} crit</span>;
  }
  if (role.todayChip === "money-saved") {
    return <span className="text-xs text-slate-600">$ saved today: $—</span>;
  }
  if (role.todayChip === "hiring-summary") {
    const open = workflows.filter((w) => w.type === "hiring" && w.status !== "completed").length;
    return <span className="text-xs text-slate-600">Open roles: {open}</span>;
  }
  if (role.todayChip === "fleet-health") {
    return <span className="text-xs text-slate-600">Fleet health: green</span>;
  }
  if (role.todayChip === "executive-summary") {
    const completed = workflows.filter((w) => w.status === "completed").length;
    return <span className="text-xs text-slate-600">Throughput: {completed}</span>;
  }
  return null;
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

  return (
    <header className="flex items-center gap-4 px-6 h-12 border-b border-slate-200 bg-white sticky top-0 z-30">
      <Link to="/" className="font-semibold text-slate-900">Apex</Link>
      <span className="text-slate-300">·</span>
      <div className="relative">
        <input
          type="search"
          placeholder="Search workflows…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="text-xs border border-slate-200 rounded px-2 py-1 bg-white text-slate-700 w-64"
        />
        {matches.length > 0 && (
          <div className="absolute left-0 top-full mt-1 bg-white border border-slate-200 rounded-md shadow-lg w-64 py-1 z-40">
            {matches.map((w) => (
              <button
                key={w.id}
                type="button"
                onClick={() => { onSearch(w.id); setQ(""); }}
                className="w-full text-left text-xs px-3 py-1.5 hover:bg-slate-50"
              >{w.id}<span className="text-slate-400"> · {w.type}</span></button>
            ))}
          </div>
        )}
      </div>
      <div className="ml-auto flex items-center gap-3">
        <NotificationsPopover items={unreadItems} onJumpTo={onJumpTo} />
        <TodayChip role={role} items={unreadItems} workflows={workflows} />
        <RoleSwitcher current={role.id} onChange={onRoleChange} />
        <div className="w-7 h-7 rounded-full bg-slate-200 text-slate-600 text-xs flex items-center justify-center font-medium" aria-label="user avatar">A</div>
      </div>
    </header>
  );
}
