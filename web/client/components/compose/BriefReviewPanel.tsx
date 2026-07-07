import { useState } from "react";
import { ClipboardCheck, ChevronRight, ArrowRight, Code2, UserRound, Sparkles, Wrench, Database, ShieldCheck } from "lucide-react";
import type { Composition } from "./studio/types";

const LANE_DOT: Record<string, string> = {
  automatic: "bg-blue-500",
  analysis: "bg-violet-500",
  human: "bg-amber-500",
};

export function BriefReviewPanel({
  brief,
  composition,
  onDecision,
}: {
  brief: { request_id: string; yaml: string };
  composition: Composition | null;
  onDecision: (request_id: string, approved: boolean, yaml: string) => void;
}) {
  const [yaml, setYaml] = useState(brief.yaml);
  const [showSpec, setShowSpec] = useState(false);

  const authority = composition?.steps.flatMap((s) => s.components).find((c) => c.type === "authority");
  const persona = composition?.steps.flatMap((s) => s.components).find((c) => c.type === "persona");
  const c = composition?.counts;

  const chips = c
    ? [
        { n: c.personae, one: "approver", many: "approvers", color: "text-amber-600 dark:text-amber-400", Icon: UserRound },
        { n: c.skills, one: "AI step", many: "AI steps", color: "text-violet-600 dark:text-violet-400", Icon: Sparkles },
        { n: c.tools, one: "connection", many: "connections", color: "text-blue-600 dark:text-blue-400", Icon: Wrench },
        { n: c.entities, one: "data type", many: "data types", color: "text-emerald-600 dark:text-emerald-400", Icon: Database },
        { n: c.rules, one: "sign-off rule", many: "sign-off rules", color: "text-rose-600 dark:text-rose-400", Icon: ShieldCheck },
      ].filter((x) => x.n > 0)
    : [];

  return (
    <div
      className="flex max-h-[82vh] w-full flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl dark:border-slate-700 dark:bg-slate-900"
      role="dialog"
      aria-label="Review the process"
    >
      <div className="border-b border-slate-100 px-6 py-4 dark:border-slate-800">
        <div className="flex items-center gap-2 text-[11.5px] font-bold uppercase tracking-wide text-blue-600 dark:text-blue-400">
          <ClipboardCheck size={15} /> Review the process
        </div>
        <h2 className="mt-1 text-[18px] font-bold tracking-tight text-slate-900 dark:text-slate-100">
          {composition ? composition.title : "Here's what I designed"}
        </h2>
        <p className="mt-0.5 text-[13px] text-slate-500 dark:text-slate-400">
          This is the process I built from your document. Approve it, or ask me to change something.
        </p>
      </div>

      <div className="flex-1 overflow-auto px-6 py-4">
        {composition ? (
          <>
            <div className="text-[11px] font-bold uppercase tracking-wide text-slate-400 dark:text-slate-500">The steps</div>
            <div className="mt-2 flex flex-wrap items-center gap-x-1.5 gap-y-2">
              {composition.steps.map((s, i) => (
                <span key={s.id} className="flex items-center gap-1.5">
                  <span className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-[12.5px] font-medium text-slate-800 dark:border-slate-700 dark:bg-slate-800/50 dark:text-slate-100">
                    <span className={"h-1.5 w-1.5 rounded-full " + (LANE_DOT[s.lane] ?? "bg-slate-400")} />
                    {s.name}
                  </span>
                  {i < composition.steps.length - 1 && <ArrowRight size={13} className="text-slate-300 dark:text-slate-600" />}
                </span>
              ))}
            </div>

            <div className="mt-5 text-[11px] font-bold uppercase tracking-wide text-slate-400 dark:text-slate-500">To run it, I'll create</div>
            <div className="mt-2 flex flex-wrap gap-2">
              {chips.map((x, i) => {
                const Icon = x.Icon;
                return (
                  <span key={i} className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 px-3 py-1 text-[12.5px] text-slate-700 dark:border-slate-700 dark:text-slate-200">
                    <Icon size={13} className={x.color} />
                    <span className="font-semibold">{x.n}</span> {x.n === 1 ? x.one : x.many}
                  </span>
                );
              })}
            </div>

            {(persona || authority) && (
              <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50/60 p-3.5 dark:border-slate-700 dark:bg-slate-800/30">
                <div className="text-[11px] font-bold uppercase tracking-wide text-slate-400 dark:text-slate-500">Who signs off</div>
                {persona && persona.type === "persona" && (
                  <div className="mt-1.5 flex items-center gap-2">
                    <span className="grid h-6 w-6 place-items-center rounded-full bg-gradient-to-br from-amber-400 to-rose-500 text-[8.5px] font-extrabold text-white">
                      {persona.name.split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase()}
                    </span>
                    <span className="text-[13.5px] font-semibold text-slate-900 dark:text-slate-100">{persona.name}</span>
                  </div>
                )}
                {authority && authority.type === "authority" && (
                  <p className="mt-1.5 text-[12.5px] text-slate-600 dark:text-slate-300">
                    Above <span className="font-semibold text-slate-900 dark:text-slate-100">{authority.threshold}</span>, it escalates to the{" "}
                    <span className="font-semibold text-rose-600 dark:text-rose-400">{authority.chain[authority.chain.length - 1]}</span>.
                  </p>
                )}
              </div>
            )}
          </>
        ) : (
          <p className="text-[13px] text-slate-500 dark:text-slate-400">Preparing the summary…</p>
        )}

        <button
          onClick={() => setShowSpec((v) => !v)}
          className="mt-5 inline-flex items-center gap-1.5 text-[12px] font-medium text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300"
        >
          <Code2 size={13} />
          {showSpec ? "Hide" : "View"} the technical spec
          <ChevronRight size={13} className={"transition-transform " + (showSpec ? "rotate-90" : "")} />
        </button>
        {showSpec && (
          <textarea
            className="mt-2 h-56 w-full resize-none rounded-lg border border-slate-200 bg-slate-50 p-3 font-mono text-[11px] leading-relaxed text-slate-700 focus:border-blue-500 focus:outline-none dark:border-slate-700 dark:bg-slate-950 dark:text-slate-300"
            value={yaml}
            onChange={(e) => setYaml(e.target.value)}
            aria-label="Technical spec (YAML)"
          />
        )}
      </div>

      <div className="flex items-center justify-end gap-2 border-t border-slate-100 px-6 py-3.5 dark:border-slate-800">
        <button
          className="rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-[13.5px] font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
          onClick={() => onDecision(brief.request_id, false, yaml)}
        >
          Ask for changes
        </button>
        <button
          className="rounded-lg bg-blue-600 px-5 py-2.5 text-[13.5px] font-semibold text-white hover:bg-blue-500 dark:text-slate-950"
          onClick={() => onDecision(brief.request_id, true, yaml)}
        >
          Approve &amp; build →
        </button>
      </div>
    </div>
  );
}
