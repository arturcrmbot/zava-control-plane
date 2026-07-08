import { Check, Loader2, Lightbulb } from "lucide-react";

export type Decision = { question: string; answer: string };

// Plain-language milestones keyed to the agent's report_stage. This is the
// progress backbone — it does NOT surface the agent's raw thoughts/tool-calls
// (those are internal jargon, wrong for this audience; a future "technical
// detail" toggle can expose them).
const MILESTONES: { key: string; label: string }[] = [
  { key: "understanding", label: "Reading your document" },
  { key: "brief", label: "Designing the process" },
  { key: "composing", label: "Building the components" },
  { key: "graduating", label: "Wiring it into Zava" },
  { key: "verifying", label: "Checking it all works" },
  { key: "ready", label: "Ready to go live" },
];

function activeIndex(agentStage: string, done: boolean): number {
  if (done || agentStage === "ready") return MILESTONES.length; // everything complete
  const i = MILESTONES.findIndex((m) => m.key === agentStage);
  return i < 0 ? 0 : i; // intake/unknown → sitting on the first milestone
}

export function AgentRail({
  agentStage,
  done,
  decisions,
}: {
  agentStage: string;
  done: boolean;
  decisions: Decision[];
}) {
  const active = activeIndex(agentStage, done);
  const completed = Math.min(active, MILESTONES.length);
  const complete = done || agentStage === "ready";
  const pct = Math.round((completed / MILESTONES.length) * 100);
  const stepLabel = complete ? "complete" : `step ${Math.min(active + 1, MILESTONES.length)} of ${MILESTONES.length}`;

  return (
    <div className="flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
      <div className="border-b border-slate-100 p-3 dark:border-slate-800">
        <div className="flex items-center gap-2 text-[13px] font-bold text-slate-900 dark:text-slate-100">
          <span className={"h-2 w-2 rounded-full " + (complete ? "bg-emerald-500" : "bg-amber-500 animate-pulse")} />
          {complete ? "All done" : "Progress"}
        </div>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
          <div className="h-full rounded-full bg-gradient-to-r from-blue-500 to-emerald-500 transition-all duration-500" style={{ width: `${pct}%` }} />
        </div>
        <div className="mt-1.5 text-[10px] text-slate-400 dark:text-slate-500">{stepLabel}</div>
      </div>

      <div className="flex-1 space-y-0.5 overflow-auto p-3">
        {MILESTONES.map((m, i) => {
          const tone = i < completed ? "done" : i === active && !done ? "now" : "next";
          return <Row key={m.key} tone={tone} title={m.label} />;
        })}

        {decisions.length > 0 && (
          <div className="mb-1 mt-3 text-[10px] font-bold uppercase tracking-wide text-slate-400 dark:text-slate-500">
            Decisions you made
          </div>
        )}
        {decisions.map((d, i) => (
          <div key={i} className="my-1.5 rounded-lg border border-violet-200 bg-violet-50 p-2 dark:border-violet-800/60 dark:bg-violet-950/20">
            <div className="flex items-center gap-1.5 text-[9.5px] font-bold uppercase tracking-wide text-violet-600 dark:text-violet-400">
              <Lightbulb size={11} /> Decision
            </div>
            <p className="mt-0.5 text-[11px] leading-snug text-slate-700 dark:text-slate-200">
              {d.question} <span className="font-semibold">{d.answer}</span>
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function Row({ tone, title }: { tone: "done" | "now" | "next"; title: string }) {
  return (
    <div className={"flex items-center gap-2.5 py-1 text-[12.5px] " + (tone === "now" ? "font-semibold text-slate-900 dark:text-slate-100" : tone === "done" ? "text-slate-500 dark:text-slate-400" : "text-slate-400 dark:text-slate-500")}>
      <span className="grid h-[16px] w-[16px] shrink-0 place-items-center">
        {tone === "done" ? (
          <span className="grid h-full w-full place-items-center rounded-full bg-emerald-50 dark:bg-emerald-950/40">
            <Check size={9} strokeWidth={3} className="text-emerald-600 dark:text-emerald-400" />
          </span>
        ) : tone === "now" ? (
          <Loader2 size={14} className="animate-spin text-amber-500 dark:text-amber-400" />
        ) : (
          <span className="h-[13px] w-[13px] rounded-full border border-dashed border-slate-300 dark:border-slate-600" />
        )}
      </span>
      {title}
    </div>
  );
}
