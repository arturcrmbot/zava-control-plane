// web/client/components/apex/ExceptionCardCompact.tsx
import { Link } from "react-router-dom";
import type { Exception } from "@shared/types";

export default function ExceptionCardCompact({ e }: { e: Exception }) {
  return (
    <Link to={`/workflows/${e.workflowId}`}
          className="panel block p-4 hover:border-blue-400 transition">
      <div className="flex items-center gap-2 mb-2">
        <span className="chip-danger">{e.severity}</span>
        <span className="font-semibold text-slate-800">{e.workflowId}</span>
        <span className="text-xs text-slate-500">· {e.category}</span>
      </div>
      <div className="text-sm text-slate-700 line-clamp-2">{e.summary}</div>
      <div className="text-xs text-emerald-700 mt-2">→ {e.recommendation}</div>
    </Link>
  );
}
