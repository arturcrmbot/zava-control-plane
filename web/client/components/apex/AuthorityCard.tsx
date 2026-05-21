// web/client/components/apex/AuthorityCard.tsx
//
// Sidebar card on WorkflowDetail. For workflows whose type maps to a known
// `action` in the delegated-authority matrix, derives (action, value, category)
// from the workflow payload, calls /api/authority/resolve, and renders the
// matched approver + threshold + governing rule.
//
// Render only when:
//   - the workflow type maps to a known matrix action, AND
//   - the resolve call returns matched=true.
//
// On any error or no-match, render nothing — this is a substrate-level affordance,
// not a primary surface, and silence is the right behaviour when it can't help.
import { useEffect, useState } from "react";
import type { Workflow } from "@shared/types";

type Resolution = {
  matched: boolean;
  approver_role?: string | null;
  threshold_gbp?: number | null;
  escalation_chain?: string[];
  rule_id?: string | null;
  basis?: string | null;
  reason?: string | null;
};

type Derivation = {
  action: string;
  value?: number | null;
  category?: string | null;
  geography?: string | null;
};

/**
 * Map workflow type + payload to (action, category, value) for the matrix.
 * Returns null when there's no sensible mapping (in which case the card is
 * silent — operators get the existing FleetAssignment/Audit/Economics tiles).
 */
function deriveMatrixRequest(w: Workflow): Derivation | null {
  const t = w.type;
  if (t === "expense-claim" && w.claim) {
    return {
      action: "expense_claim_approval",
      value: w.claim.amount,
      category: w.claim.category?.toLowerCase() ?? "*",
    };
  }
  if (t === "hiring") {
    // Hiring HITLs go through finance_bp (budget) then hr_bp (offer). We surface
    // the budget rule as the headline because that's the one the controller cares
    // about most in the operator view.
    return {
      action: "hire_budget_approval",
      value: undefined,
      category: "within_band",
    };
  }
  if (t === "travel-preapproval") {
    const p = (w.payload ?? {}) as { destination_country?: string; origin_country?: string; cheapest_total_usd?: number };
    const intl = !!(p.origin_country && p.destination_country && p.origin_country !== p.destination_country);
    return {
      action: "travel_preapproval",
      value: p.cheapest_total_usd ?? undefined,
      category: intl ? "international" : "domestic",
    };
  }
  if (t === "vendor-kyc") {
    const p = (w.payload ?? {}) as { scenario?: string };
    const cat = p.scenario && p.scenario.includes("sanctions") ? "high_risk"
      : p.scenario === "adverse-media" ? "high_risk"
      : "low_risk";
    return { action: "vendor_kyc_signoff", category: cat };
  }
  if (t === "contract-renewal") {
    const p = (w.payload ?? {}) as { scenario?: string };
    const cat = p.scenario === "price-jump" ? "price_jump"
      : p.scenario === "scope-expansion" ? "scope_expansion"
      : "flat_renewal";
    return { action: "contract_renewal_signoff", category: cat };
  }
  if (t === "it-access-request") {
    const p = (w.payload ?? {}) as { scenario?: string };
    const cat = p.scenario === "privileged-broad" ? "privileged_role"
      : p.scenario === "post-incident-narrow" ? "elevated_role"
      : "standard_role";
    return { action: "it_access_grant", category: cat };
  }
  if (t === "employee-onboarding") {
    const p = (w.payload ?? {}) as { scenario?: string };
    const cat = p.scenario === "external-contractor" ? "external_contractor"
      : p.scenario === "elevated-access-request" ? "elevated_access_request"
      : "standard_joiner";
    return { action: "employee_onboarding_access", category: cat };
  }
  if (t === "employee-transfer") {
    const p = (w.payload ?? {}) as {
      transfer?: { source_org_id?: string; target_org_id?: string };
      compensation_remap?: { delta_pct?: number };
      scenario?: string;
    };
    const src = (p.transfer?.source_org_id ?? "").toUpperCase();
    const dst = (p.transfer?.target_org_id ?? "").toUpperCase();
    const srcCountry = src.split("-").pop();
    const dstCountry = dst.split("-").pop();
    const intl = !!(srcCountry && dstCountry && srcCountry !== dstCountry);
    const delta = p.compensation_remap?.delta_pct ?? 0;
    const cat = delta > 10 ? "comp_uplift_over_threshold"
      : intl ? "international_transfer"
      : "domestic_transfer";
    return { action: "employee_transfer_signoff", category: cat };
  }
  if (t === "perf-review") {
    const p = (w.payload ?? {}) as { scenario?: string };
    const cat = p.scenario?.startsWith("calibration-outlier") ? "calibration_outlier"
      : p.scenario === "promotion-candidate" ? "promotion_candidate"
      : "on_track";
    return { action: "perf_calibration_signoff", category: cat };
  }
  if (t === "ap-invoice") {
    const p = (w.payload ?? {}) as { invoice?: { amount_gbp?: number; category?: string } };
    return {
      action: "ap_invoice_approval",
      value: p.invoice?.amount_gbp,
      category: p.invoice?.category ?? "standard",
    };
  }
  if (t === "purchase-order") {
    const p = (w.payload ?? {}) as { purchase_order?: { amount_gbp?: number; category?: string } };
    return {
      action: "purchase_order_approval",
      value: p.purchase_order?.amount_gbp,
      category: p.purchase_order?.category ?? "standard",
    };
  }
  if (t === "contract-review") {
    const p = (w.payload ?? {}) as { contract_review?: { amount_gbp?: number; contract_type?: string } };
    return {
      action: "contract_review_signoff",
      value: p.contract_review?.amount_gbp,
      category: p.contract_review?.contract_type ?? "msa",
    };
  }
  if (t === "privacy-dpia") {
    const p = (w.payload ?? {}) as { dpia?: { risk_tier?: string; geography?: string } };
    return {
      action: "privacy_dpia_signoff",
      category: p.dpia?.risk_tier ?? "low_risk",
      geography: p.dpia?.geography ?? "EMEA",
    };
  }
  if (t === "treasury-fx") {
    const p = (w.payload ?? {}) as { treasury_op?: { notional_gbp?: number } };
    return {
      action: "treasury_fx_hedge",
      value: p.treasury_op?.notional_gbp,
      category: "standard",
    };
  }
  return null;
}

function fmtGbp(v: number | null | undefined): string {
  if (v == null) return "—";
  return `£${v.toLocaleString()}`;
}

export default function AuthorityCard({ workflow }: { workflow: Workflow }) {
  const [resolution, setResolution] = useState<Resolution | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const req = deriveMatrixRequest(workflow);
    if (!req) {
      setResolution(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    fetch("/api/authority/resolve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    })
      .then((r) => r.json())
      .then((d: Resolution) => {
        if (cancelled) return;
        setResolution(d);
        setLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        setResolution(null);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [workflow.id, workflow.type]);

  if (loading) return null;
  if (!resolution || !resolution.matched || !resolution.approver_role) return null;

  return (
    <div className="panel" data-testid="authority-card">
      <div className="panel-header flex items-center justify-between">
        <span>Delegated Authority</span>
        {resolution.rule_id && (
          <code className="text-[10px] text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 px-1.5 py-0.5 rounded ring-1 ring-amber-200">
            {resolution.rule_id}
          </code>
        )}
      </div>
      <div className="panel-body space-y-2 text-xs">
        <div className="flex items-center gap-2">
          <span className="text-slate-500 dark:text-slate-400 shrink-0">Approver</span>
          <code className="text-slate-900 dark:text-slate-100 font-medium bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded">
            {resolution.approver_role}
          </code>
        </div>
        {resolution.threshold_gbp != null && (
          <div className="flex items-center gap-2">
            <span className="text-slate-500 dark:text-slate-400 shrink-0">Up to</span>
            <span className="text-slate-800 dark:text-slate-100 tabular-nums font-medium">
              {fmtGbp(resolution.threshold_gbp)}
            </span>
          </div>
        )}
        {resolution.escalation_chain && resolution.escalation_chain.length > 0 && (
          <div className="space-y-0.5">
            <div className="text-slate-500 dark:text-slate-400">Escalation</div>
            <div className="text-slate-700 dark:text-slate-200 leading-snug">
              {resolution.escalation_chain.map((r, i) => (
                <span key={r}>
                  {i > 0 && <span className="text-slate-400 dark:text-slate-500 px-1">→</span>}
                  <code className="bg-slate-100 dark:bg-slate-800 px-1 py-0.5 rounded text-[11px]">{r}</code>
                </span>
              ))}
            </div>
          </div>
        )}
        {resolution.basis && (
          <div className="text-[11px] text-slate-500 dark:text-slate-400 leading-snug border-t border-slate-200 dark:border-slate-700 pt-1.5 mt-1">
            {resolution.basis}
          </div>
        )}
      </div>
    </div>
  );
}
