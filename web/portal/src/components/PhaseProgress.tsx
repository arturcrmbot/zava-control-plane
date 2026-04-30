type Phase = "apply" | "triage" | "screening" | "interview" | "offer" | "onboarding" | "complete";

const PHASES: { id: Phase; label: string }[] = [
  { id: "apply", label: "Applied" },
  { id: "triage", label: "Review" },
  { id: "screening", label: "Screening" },
  { id: "interview", label: "Interview" },
  { id: "offer", label: "Offer" },
  { id: "onboarding", label: "Onboarding" },
  { id: "complete", label: "Done" },
];

// Backend phase strings (from api/functions/workflows/activities.py
// _with_phase): Budget, JobDesign, Sourcing, Triage, Screening, Voice,
// Interview, Compliance, Offer, Onboarding. The candidate-side ribbon
// collapses the orchestration internals into the 7 visible buckets.
const PHASE_ALIAS: Record<string, Phase> = {
  budget: "apply",
  jobdesign: "apply",
  "job design": "apply",
  sourcing: "triage",
  voice: "screening",
  compliance: "interview",
};

export default function PhaseProgress({ phase }: { phase: string }) {
  const norm = (phase ?? "apply").toLowerCase();
  const resolved = (PHASE_ALIAS[norm] ?? norm) as Phase;
  const activeIdx = PHASES.findIndex((p) => p.id === resolved);
  return (
    <ol className="flex items-center gap-2 text-xs">
      {PHASES.map((p, i) => {
        const reached = i <= activeIdx;
        return (
          <li key={p.id} className="flex items-center gap-2">
            <span
              className={
                "inline-flex items-center justify-center rounded-full w-6 h-6 border " +
                (reached
                  ? "bg-blue-600 text-white border-blue-600"
                  : "bg-white text-slate-400 border-slate-300")
              }
            >
              {i + 1}
            </span>
            <span className={reached ? "text-slate-800 font-medium" : "text-slate-400"}>
              {p.label}
            </span>
            {i < PHASES.length - 1 && <span className="text-slate-300">›</span>}
          </li>
        );
      })}
    </ol>
  );
}
