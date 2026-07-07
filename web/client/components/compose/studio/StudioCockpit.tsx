import { useState } from "react";
import { Wand2 } from "lucide-react";
import { useComposeStream } from "../useComposeStream";
import type { CockpitState } from "../reducer";
import { QuestionCard } from "../QuestionCard";
import { BriefReviewPanel } from "../BriefReviewPanel";
import { IgniteButton } from "../IgniteButton";
import { Stepper } from "./Stepper";
import { DocPanel } from "./DocPanel";
import { Canvas } from "./Canvas";
import { AgentRail } from "./AgentRail";
import { ZoomOverlay } from "./ZoomOverlay";
import { visualStage, type Composition, type ZoomTarget } from "./types";

const HEADINGS: Record<string, { h: string; t: string }> = {
  read: { h: "Reading your document", t: "Understanding what your process needs to do…" },
  design: { h: "Mapping out the steps", t: "Laying out the process I found in your document…" },
  build: { h: "Building the machinery", t: "Generating the people, skills and safeguards for each step…" },
  ready: { h: "Your process is ready", t: "Built from your document — review it, then go live." },
};

// Pure presentational studio — driven by CockpitState (live stream or preview).
export function StudioView({
  state,
  source,
  replay,
  onAnswer,
  onApproveBrief,
  onIgnite,
}: {
  state: CockpitState;
  source: string | null;
  replay?: boolean;
  onAnswer: (request_id: string, value: string) => void | Promise<void>;
  onApproveBrief: (request_id: string, approved: boolean, yaml: string) => void | Promise<void>;
  onIgnite: () => void | Promise<void>;
}) {
  const [zoom, setZoom] = useState<ZoomTarget | null>(null);
  const stage = visualStage(state.stage, !!state.done);
  const composition = (state.composition as Composition | undefined) ?? null;
  const heading = HEADINGS[stage];

  return (
    <div className="relative flex h-full w-full flex-col bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      {/* top bar */}
      <div className="flex items-center justify-between border-b border-slate-200 bg-white px-5 py-2.5 dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-center gap-2 text-[15px] font-bold">
          <span className="grid h-5 w-5 place-items-center rounded-md bg-blue-600 text-white dark:text-slate-950"><Wand2 size={12} /></span>
          Compose
        </div>
        <Stepper stage={stage} />
        <div className="w-24 text-right text-[11px] text-slate-400 dark:text-slate-500">{composition?.workflowType ?? ""}</div>
      </div>

      {/* header */}
      <div className="px-8 pb-1 pt-3.5">
        <div className="text-[11.5px] font-bold uppercase tracking-widest text-blue-600 dark:text-blue-400">
          {composition?.title ?? "New domain"}
        </div>
        <h1 className="mt-0.5 text-[22px] font-bold tracking-tight">{heading.h}</h1>
        <div className="mt-1 flex items-center gap-2 text-[13px] text-slate-500 dark:text-slate-400">
          <span className={"h-2 w-2 rounded-full " + (stage === "ready" ? "bg-emerald-500" : "bg-violet-500 animate-pulse")} />
          {heading.t}
        </div>
      </div>

      {/* body */}
      <div className="grid min-h-0 flex-1 grid-cols-[230px_1fr_300px] gap-4 px-6 pb-4 pt-2">
        <DocPanel source={source} composition={composition} read={stage !== "read"} />
        <Canvas composition={composition} stage={stage} onZoom={setZoom} />
        <AgentRail agentStage={state.stage} done={!!state.done} decisions={state.decisions} />
      </div>

      <ZoomOverlay target={zoom} composition={composition} onClose={() => setZoom(null)} onNavigate={setZoom} />

      {/* HITL + terminal overlays. In replay mode the "Go live" step is hidden —
          igniting is a local-only action, so a recorded demo ends on the canvas. */}
      {(state.question || state.brief || (state.done && !replay) || state.error) && !zoom && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-slate-900/40 p-6 dark:bg-slate-950/60">
          <div className="w-full max-w-2xl">
            {state.error && <div className="rounded-lg border border-red-500/50 bg-white p-5 text-red-600 dark:bg-slate-900 dark:text-red-300">{state.error}</div>}
            {state.question && <QuestionCard question={state.question} onAnswer={onAnswer} />}
            {state.brief && !state.question && <BriefReviewPanel brief={state.brief} composition={composition} onDecision={onApproveBrief} />}
            {state.done && !state.brief && !state.question && !replay && (
              <div className="flex justify-center"><IgniteButton done={state.done} onIgnite={() => Promise.resolve(onIgnite())} /></div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// Live/replay wrapper: binds the SSE stream to the studio view.
export function StudioCockpit({ cid, source, replay }: { cid: string; source: string | null; replay?: boolean }) {
  const { state, answer, approveBrief, ignite } = useComposeStream(cid);
  return <StudioView state={state} source={source} replay={replay} onAnswer={answer} onApproveBrief={approveBrief} onIgnite={ignite} />;
}
