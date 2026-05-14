// src/client/routes/Economics.tsx — fleet economics breakdown.
import { useEffect, useState } from "react";
import { useWorkflows } from "../hooks/useWorkflows";
import type { Workflow } from "@shared/types";

interface FleetEcon {
  activeWorkflowCount: number;
  totalWorkflowCount: number;
  totalComputeCostUsd: number;
  totalModelCalls: number;
  totalToolCalls: number;
  averageCostPerWorkflow: number;
}

const HUMAN_REVIEW_COST_USD = 12;     // estimated SSC reviewer minute cost × avg time
const PROCESSED_BASELINE_COST_USD = 18; // baseline cost per claim if reviewed manually end-to-end

export default function Economics() {
  const workflows = useWorkflows();
  const [d, setD] = useState<FleetEcon | null>(null);

  useEffect(() => {
    const load = () => fetch("/api/fleet/economics").then(r => r.json()).then(setD);
    void load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, []);

  const completed = workflows.filter((w: Workflow) => w.status === "completed").length;
  const humanTouched = workflows.filter((w: Workflow) =>
    w.actionLedger?.some(a => a.actorKind === "human")
  ).length;
  const autoCompleted = completed - humanTouched > 0 ? completed - humanTouched : completed;
  const humanCost = humanTouched * HUMAN_REVIEW_COST_USD;
  const baselineCost = workflows.length * PROCESSED_BASELINE_COST_USD;
  const computeCost = d?.totalComputeCostUsd ?? 0;
  const totalActualCost = humanCost + computeCost;
  const savings = baselineCost - totalActualCost;
  const savingsPct = baselineCost > 0 ? (savings / baselineCost) * 100 : 0;

  return (
    <div className="space-y-4">
      <div>
        <div className="text-lg font-semibold text-slate-900">Economics</div>
        <div className="text-xs text-slate-500">
          Compute, intervention, and savings vs all-manual baseline.
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="panel panel-body">
          <div className="text-[11px] uppercase tracking-wide text-slate-500">Compute spend</div>
          <div className="text-2xl font-semibold text-slate-900 mt-1 tabular-nums">${computeCost.toFixed(4)}</div>
          <div className="text-[11px] text-slate-500 mt-0.5">{d?.totalModelCalls ?? 0} model · {d?.totalToolCalls ?? 0} tool calls · session total</div>
        </div>
        <div className="panel panel-body">
          <div className="text-[11px] uppercase tracking-wide text-slate-500">Avg cost / workflow</div>
          <div className="text-2xl font-semibold text-slate-900 mt-1 tabular-nums">${(d?.averageCostPerWorkflow ?? 0).toFixed(4)}</div>
          <div className="text-[11px] text-slate-500 mt-0.5">across {d?.totalWorkflowCount ?? 0} workflows · {d?.activeWorkflowCount ?? 0} active</div>
        </div>
        <div className="panel panel-body">
          <div className="text-[11px] uppercase tracking-wide text-slate-500">Human-review cost</div>
          <div className="text-2xl font-semibold text-slate-900 mt-1 tabular-nums">${humanCost.toFixed(2)}</div>
          <div className="text-[11px] text-slate-500 mt-0.5">{humanTouched} touched · ${HUMAN_REVIEW_COST_USD}/review</div>
        </div>
        <div className="panel panel-body bg-emerald-50 border-emerald-200">
          <div className="text-[11px] uppercase tracking-wide text-emerald-700">Savings vs baseline</div>
          <div className="text-2xl font-semibold text-emerald-800 mt-1 tabular-nums">${savings.toFixed(2)}</div>
          <div className="text-[11px] text-emerald-700 mt-0.5">
            {savingsPct > 0 ? `${savingsPct.toFixed(0)}% off all-manual` : "—"}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <div className="panel">
          <div className="panel-header">Cost composition</div>
          <div className="panel-body space-y-3">
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-slate-700">Compute (LLM + tools)</span>
                <span className="font-medium text-slate-900 tabular-nums">${computeCost.toFixed(4)}</span>
              </div>
              <div className="h-2 bg-slate-100 rounded">
                <div className="h-2 bg-blue-500 rounded" style={{ width: `${totalActualCost > 0 ? (computeCost / totalActualCost) * 100 : 0}%` }} />
              </div>
            </div>
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-slate-700">Human-review (SSC)</span>
                <span className="font-medium text-slate-900 tabular-nums">${humanCost.toFixed(2)}</span>
              </div>
              <div className="h-2 bg-slate-100 rounded">
                <div className="h-2 bg-amber-500 rounded" style={{ width: `${totalActualCost > 0 ? (humanCost / totalActualCost) * 100 : 0}%` }} />
              </div>
            </div>
            <div className="text-[11px] text-slate-500 pt-1 border-t border-slate-100">
              Baseline (all-manual at ${PROCESSED_BASELINE_COST_USD}/claim) would be <span className="text-slate-900 font-medium">${baselineCost.toFixed(2)}</span>.
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">Throughput economics</div>
          <div className="panel-body space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-slate-600">Workflows processed</span>
              <span className="font-medium text-slate-900 tabular-nums">{workflows.length}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-600">Auto-completed (no human touch)</span>
              <span className="font-medium text-emerald-700 tabular-nums">{autoCompleted}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-600">Required human review</span>
              <span className="font-medium text-amber-700 tabular-nums">{humanTouched}</span>
            </div>
            <div className="flex justify-between pt-2 border-t border-slate-100">
              <span className="text-slate-600">Cost per claim — actual</span>
              <span className="font-medium text-slate-900 tabular-nums">
                ${workflows.length > 0 ? (totalActualCost / workflows.length).toFixed(3) : "0.000"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-600">Cost per claim — baseline</span>
              <span className="font-medium text-slate-900 tabular-nums">
                ${PROCESSED_BASELINE_COST_USD.toFixed(2)}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
