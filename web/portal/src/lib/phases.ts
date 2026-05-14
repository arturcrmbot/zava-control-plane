export type Phase =
  | "apply"
  | "triage"
  | "screening"
  | "interview"
  | "offer"
  | "onboarding"
  | "complete";

export const PHASES: { id: Phase; label: string }[] = [
  { id: "apply",      label: "Applied" },
  { id: "triage",     label: "Review" },
  { id: "screening",  label: "Screening" },
  { id: "interview",  label: "Interview" },
  { id: "offer",      label: "Offer" },
  { id: "onboarding", label: "Onboarding" },
  { id: "complete",   label: "Done" },
];

// Backend phase strings (api/functions/workflows/activities.py _with_phase):
// Budget, JobDesign, Sourcing, Triage, Screening, Voice, Interview,
// Compliance, Offer, Onboarding. The candidate-side ribbon collapses these
// into the 7 visible buckets above.
const PHASE_ALIAS: Record<string, Phase> = {
  budget:       "apply",
  jobdesign:    "apply",
  "job design": "apply",
  sourcing:     "triage",
  voice:        "screening",
  compliance:   "interview",
};

export function resolvePhase(raw: string | null | undefined): Phase {
  const norm = (raw ?? "apply").toLowerCase();
  return (PHASE_ALIAS[norm] ?? norm) as Phase;
}
