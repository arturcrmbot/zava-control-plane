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

export default function PhaseProgress({ phase }: { phase: Phase }) {
  const activeIdx = PHASES.findIndex((p) => p.id === phase);
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
