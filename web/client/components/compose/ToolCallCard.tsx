import { FileEdit, FileSearch, Terminal, Check, Loader2, Ban } from "lucide-react";
import type { ToolItem } from "./reducer";

const ICON = { edit: FileEdit, read: FileSearch, search: FileSearch, execute: Terminal, other: FileSearch };

export function ToolCallCard({ tool }: { tool: ToolItem }) {
  const Icon = ICON[tool.kind ?? "other"];
  const done = tool.status === "completed";
  const failed = tool.status === "failed";
  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-3" data-testid="tool-card">
      <div className="flex items-center gap-2 text-sm text-slate-900 dark:text-slate-200">
        <Icon size={16} />
        <span className="font-medium">{tool.title ?? tool.path ?? tool.id}</span>
        <span className="ml-auto">
          {failed ? <Ban size={16} className="text-red-500 dark:text-red-400" />
            : done ? <Check size={16} className="text-emerald-500 dark:text-emerald-400" />
            : <Loader2 size={16} className="animate-spin text-blue-500 dark:text-blue-400" />}
        </span>
      </div>
      {tool.diff && (
        <pre className="mt-2 max-h-48 overflow-auto rounded bg-slate-100 dark:bg-slate-950 p-2 text-xs">
          <code className="text-emerald-600 dark:text-emerald-300">{tool.diff.new}</code>
        </pre>
      )}
      {tool.output && tool.kind === "execute" && (
        <pre className="mt-2 max-h-48 overflow-auto rounded bg-slate-100 dark:bg-slate-950 p-2 text-xs text-slate-700 dark:text-slate-300">{tool.output}</pre>
      )}
    </div>
  );
}
