// web/client/routes/HiringManager.tsx — POC2 §4.6 Hiring Manager surface.
//
// Lightweight single-hire view, deep-linkable from Teams. Shows the candidate's
// crystallised profile, the panel scheduling state, and a one-tap RSVP. The
// HR BP's full-fleet view is the Fleet Control Feed; this surface is the
// hiring manager's narrow lens on one hire.
//
// Track B stub — wire-up to live workflow data lands in the next iteration.
import { useParams } from "react-router-dom";

type CandidateSummary = {
  candidate_id: string;
  name: string;
  current_title: string;
  tenure_years_total: number;
  skills: string[];
};

const STUB_CANDIDATE: CandidateSummary = {
  candidate_id: "C-101",
  name: "Priya Mehta",
  current_title: "Senior Data Engineer",
  tenure_years_total: 7.5,
  skills: ["python", "spark", "airflow", "dbt", "kubernetes"],
};

export default function HiringManager() {
  const { workflowId } = useParams<{ workflowId?: string }>();
  const c = STUB_CANDIDATE;
  return (
    <div className="max-w-2xl mx-auto p-6 bg-white rounded-lg shadow-sm border border-slate-200">
      <div className="text-xs uppercase tracking-wide text-slate-500">Hiring Manager view</div>
      <div className="mt-1 text-lg font-semibold text-slate-900">
        Hire {workflowId ?? "—"} · {c.name}
      </div>
      <div className="text-sm text-slate-600">{c.current_title} · {c.tenure_years_total.toFixed(1)} yrs</div>
      <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
        <div>
          <div className="font-medium text-slate-800">Skills</div>
          <div className="mt-1 flex flex-wrap gap-1">
            {c.skills.map(s => (
              <span key={s} className="text-[11px] bg-slate-100 text-slate-700 rounded px-2 py-0.5">{s}</span>
            ))}
          </div>
        </div>
        <div>
          <div className="font-medium text-slate-800">Panel slot</div>
          <div className="mt-1 text-slate-600">Tue 12 May · 14:00 GMT</div>
          <div className="mt-2 flex gap-2">
            <button className="text-xs bg-emerald-600 text-white rounded px-3 py-1.5">Accept</button>
            <button className="text-xs bg-slate-200 text-slate-800 rounded px-3 py-1.5">Propose alt</button>
          </div>
        </div>
      </div>
      <div className="mt-6 border-t border-slate-200 pt-4 text-xs text-slate-500">
        Track B-stub: live data binding lands once the FastAPI hiring-workflow
        endpoints come online. The HR BP's full-fleet view stays at /.
      </div>
    </div>
  );
}
