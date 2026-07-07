import { FileText, CheckCircle2 } from "lucide-react";
import type { ReactNode } from "react";
import type { Composition } from "./types";

export function DocPanel({
  source,
  composition,
  read,
}: {
  source: string | null;
  composition: Composition | null;
  read: boolean;
}) {
  const autoChecks = composition ? composition.steps.filter((s) => s.lane === "automatic").length : 0;
  const approvals = composition ? composition.steps.filter((s) => s.kind === "hitl").length : 0;
  const hasThreshold = composition
    ? composition.steps.some((s) => s.components.some((c) => c.type === "authority"))
    : false;

  const mode: "text" | "recap" | "loading" = source ? "text" : composition ? "recap" : "loading";

  return (
    <div className="flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white p-3.5 shadow-sm dark:border-slate-700 dark:bg-slate-900">
      <div className="flex items-center gap-2 text-[10.5px] font-bold uppercase tracking-wide text-slate-400 dark:text-slate-500">
        <FileText size={14} /> {mode === "recap" ? "What I read" : "Your document"}
        {read && (
          <span className="ml-auto flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
            <CheckCircle2 size={12} /> read
          </span>
        )}
      </div>

      <div className="relative mt-3 flex-1 overflow-auto">
        {mode === "text" && (
          <p className="whitespace-pre-wrap text-[12.5px] leading-[1.75] text-slate-600 dark:text-slate-300">
            {highlight(source!)}
          </p>
        )}

        {mode === "recap" && composition && <Recap composition={composition} />}

        {mode === "loading" && <DocSkeleton />}

        {mode === "text" && !read && (
          <div className="pointer-events-none absolute inset-x-0 top-0 h-14 animate-[scan_3s_ease-in-out_infinite] bg-gradient-to-b from-transparent via-violet-500/12 to-transparent" />
        )}
      </div>

      {composition && (
        <div className="mt-3 border-t border-slate-100 pt-3 dark:border-slate-800">
          <div className="text-[10.5px] font-bold uppercase tracking-wide text-slate-400 dark:text-slate-500">What I found</div>
          <Finding color="bg-blue-500" text={`${composition.counts.steps} steps in the process`} />
          {autoChecks > 0 && <Finding color="bg-emerald-500" text={`${autoChecks} automatic ${autoChecks === 1 ? "step" : "steps"}`} />}
          {approvals > 0 && (
            <Finding color="bg-amber-500" text={`${approvals} approval${approvals === 1 ? "" : "s"}${hasThreshold ? " — with a threshold rule" : ""}`} />
          )}
        </div>
      )}
    </div>
  );
}

// Subtle key-phrase highlighting so the document reads like the thing the agent
// is working from (currency thresholds, money, approvals, risk).
function highlight(text: string) {
  const re = /(£[\d,]+(?:\.\d+)?|GBP\s?[\d,]+|approv\w*|budget|risk|CFO)/gi;
  const out: ReactNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const w = m[0];
    const cls = /£|GBP/i.test(w)
      ? "bg-amber-100/70 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300"
      : /approv/i.test(w)
      ? "bg-blue-100/70 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300"
      : "bg-emerald-100/60 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300";
    out.push(<mark key={i++} className={"rounded px-1 font-medium " + cls}>{w}</mark>);
    last = m.index + w.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

function Recap({ composition }: { composition: Composition }) {
  const laneWord: Record<string, string> = {
    automatic: "runs automatically",
    analysis: "an agent reviews it",
    human: "a person signs off",
  };
  const authority = composition.steps.flatMap((s) => s.components).find((c) => c.type === "authority");
  const persona = composition.steps.flatMap((s) => s.components).find((c) => c.type === "persona");

  return (
    <div className="text-[12.5px] leading-relaxed text-slate-600 dark:text-slate-300">
      <p>
        I read your document and mapped out a{" "}
        <span className="font-semibold text-slate-900 dark:text-slate-100">{composition.title.toLowerCase()}</span> process:
      </p>
      <ol className="mt-2.5 space-y-1.5">
        {composition.steps.map((s, i) => (
          <li key={s.id} className="flex gap-2.5">
            <span className="mt-[1px] grid h-4 w-4 shrink-0 place-items-center rounded-full bg-slate-100 text-[9px] font-bold text-slate-500 dark:bg-slate-800 dark:text-slate-400">
              {i + 1}
            </span>
            <span>
              <span className="font-medium text-slate-800 dark:text-slate-200">{s.name}</span>
              <span className="text-slate-400 dark:text-slate-500"> — {laneWord[s.lane] ?? s.lane}</span>
            </span>
          </li>
        ))}
      </ol>
      {authority && authority.type === "authority" && (
        <p className="mt-2.5 rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-1.5 text-[11.5px] text-amber-800 dark:border-amber-800/50 dark:bg-amber-950/20 dark:text-amber-300">
          Above <span className="font-semibold">{authority.threshold}</span>, sign-off escalates to the{" "}
          {authority.chain[authority.chain.length - 1]}
          {persona && persona.type === "persona" ? `; otherwise the ${persona.name} approves.` : "."}
        </p>
      )}
    </div>
  );
}

function DocSkeleton() {
  const paras = [
    [96, 88, 92, 72],
    [90, 97, 84, 66],
    [93, 80, 89],
  ];
  return (
    <div className="space-y-3.5" aria-label="Reading your document">
      {paras.map((para, pi) => (
        <div key={pi} className="space-y-2">
          {para.map((w, i) => (
            <div key={i} className="h-2.5 animate-pulse rounded bg-slate-100 dark:bg-slate-800" style={{ width: `${w}%` }} />
          ))}
        </div>
      ))}
    </div>
  );
}

function Finding({ color, text }: { color: string; text: string }) {
  return (
    <div className="mt-1.5 flex items-center gap-2 text-[11.5px] text-slate-600 dark:text-slate-300">
      <span className={"h-1.5 w-1.5 rounded-full " + color} />
      {text}
    </div>
  );
}
