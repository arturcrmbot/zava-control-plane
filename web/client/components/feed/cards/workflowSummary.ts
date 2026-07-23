// web/client/components/feed/cards/workflowSummary.ts
//
// Pull human-readable fields out of a Workflow's payload (which varies by
// domain) so HITL/Exception/ExternalWait cards can show meaningful content
// instead of just the workflow id.
//
// Falls back gracefully when fields are missing.
import type { Workflow } from "@shared/types";

export interface WorkflowSummary {
  // One-line headline ("Invoice INV-2026-00001 · Globex Industries · GBP 850")
  headline: string;
  // Optional sub-line ("Three-Way Match · awaiting AP clerk · scenario: amount-mismatch")
  subline: string | null;
  // Human-friendly domain label for the card header / chip
  domainLabel: string;
}

const DOMAIN_LABEL: Record<string, string> = {
  "expense-claim": "Expense claim",
  "hiring": "Hiring",
  "invoice-p2p": "Invoice",
  "travel-preapproval": "Travel pre-approval",
  "vendor-kyc": "Vendor KYC",
  "employee-onboarding": "Onboarding",
  "it-access-request": "IT access",
  "contract-renewal": "Contract renewal",
  "perf-review": "Perf review",
  "ap-invoice": "AP invoice",
  "purchase-order": "Purchase order",
  "contract-review": "Contract review",
  "privacy-dpia": "DPIA",
  "treasury-fx": "Treasury FX",
  "creative-campaign": "Creative campaign",
};

function fmtMoney(amount: number | undefined, currency = "GBP"): string | null {
  if (amount == null) return null;
  return `${currency} ${amount.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function humanizeAwaiting(reason: string | undefined): string | null {
  if (!reason) return null;
  // "awaiting_ap_clerk" → "AP clerk"
  return reason
    .replace(/^awaiting_/, "")
    .replace(/_/g, " ")
    .replace(/\b(\w)/g, (m) => m.toUpperCase())
    // common abbreviations
    .replace(/\bAp\b/, "AP")
    .replace(/\bHr\b/, "HR")
    .replace(/\bIt\b/, "IT")
    .replace(/\bDpo\b/, "DPO")
    .replace(/\bCfo\b/, "CFO")
    .replace(/\bSsc\b/, "SSC")
    .replace(/\bUbo\b/, "UBO");
}

// Pull the first {amount_gbp, vendor_name, *_id} triple out of a domain
// payload. The shapes vary per domain (`invoice`, `contract`, `purchase_order`,
// `treasury_op`, `dpia`, `request`, `joiner`, `review`, `vendor`, `brief`) but
// they all use these field names where applicable.
function summariseDomainPayload(
  payload: Record<string, unknown> | undefined,
): string | null {
  if (!payload) return null;
  // The outer payload has one key matching the domain entity; unwrap if so.
  const candidates: Array<Record<string, unknown>> = [];
  for (const v of Object.values(payload)) {
    if (v && typeof v === "object") candidates.push(v as Record<string, unknown>);
  }
  candidates.push(payload);

  for (const obj of candidates) {
    const idKey = Object.keys(obj).find((k) => /_(id)$/.test(k)) ?? null;
    const id = idKey ? String(obj[idKey] ?? "") : "";
    const vendor = (obj.vendor_name ?? obj.name ?? obj.system_name ?? obj.client_brand ?? "") as string;
    const amount = (obj.amount_gbp ?? obj.notional_gbp ?? obj.current_annual_value ?? null) as number | null;
    const amountStr = amount != null ? fmtMoney(amount) : null;
    const parts = [id, vendor, amountStr].filter(Boolean);
    if (parts.length > 0) return parts.join(" · ");
  }
  // Hiring metadata-style payload sits under metadata not payload — handled by caller.
  // Anything left is "type only"
  return null;
}

export function summariseWorkflow(w: Workflow): WorkflowSummary {
  const domainLabel = DOMAIN_LABEL[w.type] ?? w.type;
  const meta = (w.metadata ?? {}) as Record<string, unknown>;

  // Domain-specific headline strategies, ordered by signal strength.
  let headline: string | null = null;

  // 1. Expense claim
  if (w.claim) {
    const amt = `${w.claim.currency} ${w.claim.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    headline = `${amt} · ${w.claim.vendor} · ${w.claim.employeeId}`;
  }
  // 2. Legacy invoice-p2p
  else if (w.invoice && w.vendor) {
    headline = `${w.invoice.currency} ${w.invoice.amount.toLocaleString()} · ${w.vendor.name} · PO ${w.invoice.poRef}`;
  }
  // 3. Hiring — uses metadata, not payload
  else if (w.type === "hiring") {
    const title = (meta.role_title as string | undefined) ?? (meta.role_id as string | undefined);
    const cand = (meta.candidate_name as string | undefined) ?? (meta.candidate_id as string | undefined);
    const jur = meta.role_jurisdiction as string | undefined;
    headline = [cand, title, jur].filter(Boolean).join(" · ") || null;
  }
  // 4. Generic fleet/generated domains — look in payload
  if (!headline) {
    headline = summariseDomainPayload(w.payload);
  }
  // Last-resort: domain label + phase
  if (!headline) {
    headline = `${domainLabel} · ${w.currentPhase}`;
  }

  // Subline: "<phase> · awaiting <persona> · <agency>"
  const sublineParts: string[] = [];
  if (w.currentPhase) sublineParts.push(w.currentPhase);
  const awaiting = humanizeAwaiting(meta.awaiting_reason as string | undefined);
  if (awaiting) sublineParts.push(`awaiting ${awaiting}`);
  if (w.agency && w.agency !== "Zava") sublineParts.push(w.agency);

  return {
    headline,
    subline: sublineParts.length > 0 ? sublineParts.join(" · ") : null,
    domainLabel,
  };
}
