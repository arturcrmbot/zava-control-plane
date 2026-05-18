// web/client/components/feed/CardShell.tsx
//
// Shared chrome for every card in the feed. Per spec §3.4 every card carries
// the same outer skeleton: severity border accent (left), header row (icon +
// type label + workflow id + relative time), body slot, action slot. CardShell
// itself declares an @container scope; cards can lay out body/actions
// horizontally at container ≥ 720px (spec §3.1 — drawer-open narrowing).
import type { ReactNode } from "react";
import type { Severity } from "@shared/types";

const SEVERITY_BORDER: Record<string, string> = {
  critical: "border-l-4 border-red-500",
  high: "border-l-4 border-amber-500",
  medium: "border-l-4 border-slate-200",
  null: "border-l-4 border-slate-200",
};

const SEVERITY_DOT: Record<string, string> = {
  critical: "bg-red-500",
  high: "bg-amber-500",
  medium: "bg-slate-300",
  null: "bg-slate-200",
};

function relativeTime(tsSec: number): string {
  const now = Date.now() / 1000;
  const diff = Math.max(0, now - tsSec);
  if (diff < 60) return `${Math.round(diff)}s ago`;
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  if (diff < 86400) return `${(diff / 3600).toFixed(1)}h ago`;
  return `${Math.round(diff / 86400)}d ago`;
}

export interface CardShellProps {
  severity: Severity | null;
  icon: ReactNode;
  typeLabel: string;
  workflowId: string;
  timestampSec: number;
  body: ReactNode;
  actions: ReactNode;
  onPrimaryClick?: () => void;
  testId?: string;
}

export default function CardShell({
  severity, icon, typeLabel, workflowId, timestampSec,
  body, actions, onPrimaryClick, testId,
}: CardShellProps) {
  const sevKey = severity ?? "null";
  const onKey = onPrimaryClick
    ? (e: import("react").KeyboardEvent<HTMLDivElement>) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onPrimaryClick();
        }
      }
    : undefined;

  return (
    <article
      data-testid={testId ?? `card-${workflowId}`}
      className={`@container bg-white ${SEVERITY_BORDER[sevKey]} border border-slate-200 rounded-lg shadow-sm hover:border-slate-300 transition`}
    >
      <div className="flex items-center gap-2 px-4 pt-3 text-xs text-slate-500">
        <span className={`h-1.5 w-1.5 rounded-full ${SEVERITY_DOT[sevKey]}`} aria-hidden />
        {icon}
        <span className="uppercase tracking-wide text-[10px] font-semibold text-slate-700">
          {typeLabel}
        </span>
        <span className="text-slate-300">·</span>
        <span className="font-mono text-slate-700">{workflowId}</span>
        <span className="ml-auto text-[11px] text-slate-400">{relativeTime(timestampSec)}</span>
      </div>
      <div className="px-4 py-3 flex flex-col @[720px]:flex-row @[720px]:items-start @[720px]:gap-4 gap-3">
        <div
          className="flex-1 min-w-0"
          onClick={onPrimaryClick}
          onKeyDown={onKey}
          role={onPrimaryClick ? "button" : undefined}
          tabIndex={onPrimaryClick ? 0 : undefined}
        >
          {body}
        </div>
        <div className="flex flex-wrap gap-2 @[720px]:flex-nowrap @[720px]:justify-end shrink-0">
          {actions}
        </div>
      </div>
    </article>
  );
}
