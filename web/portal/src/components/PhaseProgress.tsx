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
  const activeIdx = Math.max(PHASES.findIndex((p) => p.id === resolved), 0);

  return (
    <ol className="grid grid-cols-7 gap-1 sm:gap-2 text-[11px] sm:text-xs">
      {PHASES.map((p, i) => {
        const done = i < activeIdx;
        const current = i === activeIdx;
        const bubbleClass = done
          ? "phase-bubble phase-bubble-done"
          : current
            ? "phase-bubble phase-bubble-current"
            : "phase-bubble phase-bubble-todo";
        const labelClass = done
          ? "phase-label-done"
          : current
            ? "phase-label-current"
            : "phase-label-todo";
        const railClass = done
          ? "phase-rail-done"
          : current
            ? "phase-rail-current"
            : "phase-rail-todo";

        return (
          <li key={p.id} className="flex flex-col items-center text-center relative">
            <div className="flex items-center w-full">
              {i > 0 && <div className={`flex-1 h-0.5 ${railClass}`}/>}
              <span className={bubbleClass}>
                {done ? "✓" : i + 1}
              </span>
              {i < PHASES.length - 1 && <div className={`flex-1 h-0.5 ${
                i < activeIdx ? "phase-rail-done" :
                i === activeIdx ? "phase-rail-current" : "phase-rail-todo"
              }`}/>}
            </div>
            <span className={`mt-2 ${labelClass}`}>{p.label}</span>
          </li>
        );
      })}
    </ol>
  );
}
