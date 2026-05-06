import {
  PHASE_ORDER, EXPENSE_PHASE_ORDER, HIRING_PHASE_ORDER,
  TRAVEL_PREAPPROVAL_PHASE_ORDER, VENDOR_KYC_PHASE_ORDER,
  EMPLOYEE_ONBOARDING_PHASE_ORDER, IT_ACCESS_REQUEST_PHASE_ORDER,
  CONTRACT_RENEWAL_PHASE_ORDER, PERF_REVIEW_PHASE_ORDER,
  AP_INVOICE_PHASE_ORDER, PURCHASE_ORDER_PHASE_ORDER,
  CONTRACT_REVIEW_PHASE_ORDER, PRIVACY_DPIA_PHASE_ORDER,
  TREASURY_FX_PHASE_ORDER,
  type Phase, type PhaseName, type Workflow,
} from "@shared/types";
import { Check, Loader2, Ban, CircleDashed } from "lucide-react";

function phaseOrderFor(type: Workflow["type"] | undefined): PhaseName[] {
  switch (type) {
    case "expense-claim":         return EXPENSE_PHASE_ORDER;
    case "hiring":                return HIRING_PHASE_ORDER;
    case "travel-preapproval":    return TRAVEL_PREAPPROVAL_PHASE_ORDER;
    case "vendor-kyc":            return VENDOR_KYC_PHASE_ORDER;
    case "employee-onboarding":   return EMPLOYEE_ONBOARDING_PHASE_ORDER;
    case "it-access-request":     return IT_ACCESS_REQUEST_PHASE_ORDER;
    case "contract-renewal":      return CONTRACT_RENEWAL_PHASE_ORDER;
    case "perf-review":           return PERF_REVIEW_PHASE_ORDER;
    case "ap-invoice":            return AP_INVOICE_PHASE_ORDER;
    case "purchase-order":        return PURCHASE_ORDER_PHASE_ORDER;
    case "contract-review":       return CONTRACT_REVIEW_PHASE_ORDER;
    case "privacy-dpia":          return PRIVACY_DPIA_PHASE_ORDER;
    case "treasury-fx":           return TREASURY_FX_PHASE_ORDER;
    default:                      return PHASE_ORDER;     // legacy invoice-p2p
  }
}

type Status = "completed" | "in_progress" | "blocked" | "pending";

function classify(
  name: string, phases: Phase[], currentPhase: string,
  hasException: boolean,
): Status {
  const p = phases.find(x => x.name === name);
  if (p?.status === "completed") return "completed";
  if (name === currentPhase && hasException) return "blocked";
  if (name === currentPhase) return "in_progress";
  return "pending";
}

const Icon = ({ s }: { s: Status }) => {
  if (s === "completed") return <Check size={14} className="text-emerald-600" />;
  if (s === "in_progress") return <Loader2 size={14} className="text-blue-600 animate-spin" />;
  if (s === "blocked") return <Ban size={14} className="text-red-600" />;
  return <CircleDashed size={14} className="text-slate-400" />;
};

const PILL: Record<Status, string> = {
  completed: "bg-emerald-50 border-emerald-200 text-emerald-800",
  in_progress: "bg-blue-50 border-blue-200 text-blue-800",
  blocked: "bg-red-50 border-red-200 text-red-800",
  pending: "bg-slate-50 border-slate-200 text-slate-500",
};

export default function PhaseRibbon({ workflow, phases }: {
  workflow: Workflow; phases: Phase[];
}) {
  const hasException = !!workflow.activeExceptionId;
  const order = phaseOrderFor(workflow.type);
  return (
    <div className="flex flex-wrap items-center gap-y-2 gap-x-1.5" data-testid="phase-ribbon">
      {order.map((name, i) => {
        const s = classify(name, phases, workflow.currentPhase, hasException);
        return (
          <div key={name} className="flex items-center gap-1.5">
            <div className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 border ${PILL[s]}`}>
              <Icon s={s} />
              <span className="text-xs font-medium whitespace-nowrap">{name}</span>
            </div>
            {i < order.length - 1 &&
              <div className="h-px w-3 bg-slate-300" />}
          </div>
        );
      })}
    </div>
  );
}
