import { Check } from "lucide-react";
import { STAGE_ORDER, type VisualStage } from "./types";

const LABELS: Record<VisualStage, string> = {
  read: "Read", design: "Design", build: "Build", ready: "Ready",
};

export function Stepper({ stage }: { stage: VisualStage }) {
  const current = STAGE_ORDER.indexOf(stage);
  return (
    <div className="flex items-center">
      {STAGE_ORDER.map((s, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <div key={s} className="flex items-center">
            <div
              className={
                "flex items-center gap-2 text-[12.5px] " +
                (active
                  ? "font-bold text-slate-900 dark:text-slate-100"
                  : done
                  ? "font-medium text-slate-600 dark:text-slate-300"
                  : "font-medium text-slate-400 dark:text-slate-500")
              }
            >
              <span
                className={
                  "grid h-[19px] w-[19px] place-items-center rounded-full border text-[10.5px] " +
                  (active
                    ? "border-blue-600 bg-blue-600 text-white dark:text-slate-950"
                    : done
                    ? "border-emerald-500 bg-emerald-500 text-white dark:text-slate-950"
                    : "border-slate-300 bg-white text-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-500")
                }
              >
                {done ? <Check size={11} strokeWidth={3} /> : i + 1}
              </span>
              {LABELS[s]}
            </div>
            {i < STAGE_ORDER.length - 1 && (
              <span
                className={
                  "mx-2 h-0.5 w-5 rounded-full " +
                  (i < current ? "bg-emerald-500" : "bg-slate-200 dark:bg-slate-700")
                }
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
