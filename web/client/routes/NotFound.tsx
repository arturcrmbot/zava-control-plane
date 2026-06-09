// web/client/routes/NotFound.tsx
//
// SPA catch-all for paths the router doesn't recognise. Without this
// fallback unknown routes (typos, stale bookmarks, retired pages such
// as /foundry, /replay, /inbox, /governance, /personae) rendered the
// chrome with a blank content area, which looked like a broken app.
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Compass } from "lucide-react";

export default function NotFound() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  return (
    <section className="flex-1 flex items-center justify-center p-10">
      <div className="max-w-md text-center space-y-4">
        <div className="mx-auto w-12 h-12 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-500 dark:text-slate-400">
          <Compass size={22} />
        </div>
        <h1 className="text-xl font-semibold text-slate-800 dark:text-slate-100">
          Page not found
        </h1>
        <p className="text-sm text-slate-600 dark:text-slate-400">
          The path <code className="text-xs px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800">{pathname}</code> isn’t part of the operator console.
          It may have been renamed or removed.
        </p>
        <div className="flex items-center justify-center gap-2 pt-2">
          <Link
            to="/dashboard"
            className="text-xs px-3 py-1.5 rounded bg-slate-900 dark:bg-amber-500 text-white dark:text-slate-900 hover:opacity-90"
          >Go to Dashboard</Link>
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="text-xs px-3 py-1.5 rounded border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800"
          >Go back</button>
        </div>
      </div>
    </section>
  );
}
