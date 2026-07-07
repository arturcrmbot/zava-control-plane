import { useComposeStream } from "./useComposeStream";
import { ThoughtStream } from "./ThoughtStream";
import { ActivityTimeline } from "./ActivityTimeline";
import { PlanChecklist } from "./PlanChecklist";
import { QuestionCard } from "./QuestionCard";
import { BriefReviewPanel } from "./BriefReviewPanel";
import { IgniteButton } from "./IgniteButton";

export function Cockpit({ cid }: { cid: string }) {
  const { state, answer, approveBrief, ignite } = useComposeStream(cid);
  return (
    <div className="relative w-full h-full bg-slate-50 dark:bg-slate-950/40 text-slate-900 dark:text-slate-100">
      <div className="grid h-full grid-cols-[320px_1fr_280px] gap-3 p-3">
        <ThoughtStream text={state.thoughts} />
        <ActivityTimeline narration={state.narration} tools={state.tools} />
        <PlanChecklist plan={state.plan} />
      </div>

      {(state.question || state.brief || state.done || state.error) && (
        <div className="absolute inset-0 flex items-center justify-center bg-slate-900/40 dark:bg-slate-950/60 p-6">
          <div className="w-full max-w-2xl">
            {state.error && <div className="rounded-lg border border-red-500/50 bg-white dark:bg-slate-900 p-5 text-red-600 dark:text-red-300">{state.error}</div>}
            {state.question && <QuestionCard question={state.question} onAnswer={answer} />}
            {state.brief && !state.question && <BriefReviewPanel brief={state.brief} onDecision={approveBrief} />}
            {state.done && !state.brief && !state.question &&
              <div className="flex justify-center"><IgniteButton done={state.done} onIgnite={ignite} /></div>}
          </div>
        </div>
      )}

      <div className="absolute left-3 top-3 rounded-full bg-slate-200 dark:bg-slate-800/80 px-3 py-1 text-xs text-slate-700 dark:text-slate-300">stage: {state.stage}</div>
    </div>
  );
}
