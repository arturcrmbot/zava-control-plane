import { Check } from "lucide-react";
import { FileInput, Table2, ShieldQuestion, UserRound, Boxes } from "lucide-react";
import { stepPalette } from "./tokens";
import { ComponentCard } from "./ComponentCard";
import type { Step } from "./types";

function stepIcon(step: Step) {
  if (step.kind === "hitl") return UserRound;
  if (step.kind === "agent") return ShieldQuestion;
  if (step.id.includes("intake") || step.id.includes("submit") || step.id.includes("request")) return FileInput;
  if (step.id.includes("register")) return Boxes;
  return Table2;
}

export function StepCard({
  step,
  built,
  onZoomStep,
  onZoomComponent,
}: {
  step: Step;
  built: boolean;
  onZoomStep: () => void;
  onZoomComponent: (index: number) => void;
}) {
  const p = stepPalette(step.kind);
  const Icon = stepIcon(step);
  return (
    <div className="flex flex-col">
      <button
        onClick={onZoomStep}
        className={
          "relative cursor-zoom-in rounded-xl border bg-white p-2.5 text-left shadow-sm hover:shadow-md dark:bg-slate-900 " +
          (step.kind === "hitl"
            ? "border-amber-300 dark:border-amber-700/60"
            : "border-slate-200 dark:border-slate-700")
        }
      >
        {built && (
          <span className="absolute -left-2 -top-2 grid h-[18px] w-[18px] place-items-center rounded-full border-2 border-white bg-emerald-500 shadow dark:border-slate-950">
            <Check size={9} strokeWidth={3} className="text-white dark:text-slate-950" />
          </span>
        )}
        <div className="flex items-center gap-2">
          <span className={"grid h-[26px] w-[26px] shrink-0 place-items-center rounded-lg border " + p.bg + " border-transparent " + p.text}>
            <Icon size={14} />
          </span>
          <div className="min-w-0">
            <h3 className="truncate text-[12px] font-semibold text-slate-900 dark:text-slate-100">{step.name}</h3>
            <div className="text-[9.5px] text-slate-400 dark:text-slate-500">{laneText(step)}</div>
          </div>
        </div>
      </button>

      {built && step.components.length > 0 && (
        <>
          <span className="mx-auto my-0.5 h-3 w-0.5 bg-slate-200 dark:bg-slate-700" />
          <div className="flex flex-col gap-1.5">
            {step.components.map((c, i) => (
              <ComponentCard key={i} comp={c} onZoom={() => onZoomComponent(i)} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function laneText(step: Step): string {
  if (step.kind === "hitl") return "human sign-off";
  if (step.kind === "agent") return "analysis";
  return "automatic";
}
