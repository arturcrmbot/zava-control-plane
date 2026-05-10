// control-plane/src/shared/types.ts

export type PhaseName =
  // Invoice P2P (legacy)
  | "Intake" | "Validation" | "Routing"
  | "Approval" | "Payment" | "Reconciliation"
  // POC1 Expense compliance
  | "Classify" | "Validate Receipt" | "Route" | "Notify" | "Arbitrate" | "Audit"
  // POC2 Hiring (Talent Lifecycle)
  | "Budget" | "Job Design" | "Sourcing" | "Triage" | "Screening"
  | "Voice" | "Interview" | "Compliance" | "Offer" | "Onboarding"
  // Fleet/composed domains (compose-domain v3 - generated phase names)
  | "Employee Lookup" | "Policy Fit Check" | "Manager Approval"
  | "Vendor Intake" | "KYC Diligence" | "UBO Resolver" | "Finance Signoff"
  | "Access Drafter" | "IT Admin Approval" | "Induction Planner"
  | "RBAC Resolver" | "Risk Assessor" | "Line Manager Approval"
  | "Contract Lookup" | "Market Benchmarker" | "Renewal Terms Drafter"
  | "Contract Owner Signoff"
  | "Peer Feedback Aggregator" | "Calibration Drafter"
  | "HR Calibration" | "Line Manager Delivery"
  // Hand-graduated wave 2 fleet domains
  | "Invoice Lookup" | "Three-Way Match"
  | "PO Lookup" | "Supplier Check" | "Authority Resolve"
  | "Contract Intake" | "Risk Classify"
  | "DPIA Intake"
  | "Op Lookup" | "Position Check";

export const PHASE_ORDER: PhaseName[] = [
  "Intake", "Validation", "Routing", "Approval", "Payment", "Reconciliation"
];

export const EXPENSE_PHASE_ORDER: PhaseName[] = [
  "Intake", "Classify", "Validate Receipt", "Route", "Notify", "Arbitrate", "Audit"
];

export const HIRING_PHASE_ORDER: PhaseName[] = [
  "Budget", "Job Design", "Sourcing", "Triage", "Screening",
  "Voice", "Interview", "Compliance", "Offer", "Onboarding"
];

// Fleet/composed domains (per api/shared/domains.py registry).
// HITL gate names use Title Case here to match what the orchestrator
// emits via step.started; the orchestrator stamps snake_case `phase` on
// suspended payloads (see fleet_*_orchestration generators) but the
// store's current_phase tracks step.started's name.
export const TRAVEL_PREAPPROVAL_PHASE_ORDER: PhaseName[] = [
  "Employee Lookup", "Policy Fit Check", "Manager Approval",
];
export const VENDOR_KYC_PHASE_ORDER: PhaseName[] = [
  "Vendor Intake", "KYC Diligence", "UBO Resolver", "Finance Signoff",
];
export const EMPLOYEE_ONBOARDING_PHASE_ORDER: PhaseName[] = [
  "Employee Lookup", "Access Drafter", "IT Admin Approval", "Induction Planner",
];
export const IT_ACCESS_REQUEST_PHASE_ORDER: PhaseName[] = [
  "Employee Lookup", "RBAC Resolver", "Risk Assessor",
  "Line Manager Approval", "IT Admin Approval",
];
export const CONTRACT_RENEWAL_PHASE_ORDER: PhaseName[] = [
  "Contract Lookup", "Market Benchmarker", "Renewal Terms Drafter",
  "Finance Signoff", "Contract Owner Signoff",
];
export const PERF_REVIEW_PHASE_ORDER: PhaseName[] = [
  "Employee Lookup", "Peer Feedback Aggregator", "Calibration Drafter",
  "HR Calibration", "Line Manager Delivery",
];
export const AP_INVOICE_PHASE_ORDER: PhaseName[] = [
  "Invoice Lookup", "Three-Way Match", "Authority Resolve",
];
export const PURCHASE_ORDER_PHASE_ORDER: PhaseName[] = [
  "PO Lookup", "Supplier Check", "Authority Resolve",
];
export const CONTRACT_REVIEW_PHASE_ORDER: PhaseName[] = [
  "Contract Intake", "Risk Classify", "Authority Resolve",
];
export const PRIVACY_DPIA_PHASE_ORDER: PhaseName[] = [
  "DPIA Intake", "Risk Classify", "Authority Resolve",
];
export const TREASURY_FX_PHASE_ORDER: PhaseName[] = [
  "Op Lookup", "Position Check", "Authority Resolve",
];

export type WorkflowStatus =
  | "in_progress" | "awaiting_hitl" | "completed" | "failed";

export type Severity = "critical" | "high" | "medium";

export type ExceptionCategory =
  | "duplicate-invoice" | "po-mismatch" | "threshold-exceeded"
  | "sanctions-flag" | "compliance" | "payment-timeout";

export interface Vendor {
  id: string;
  name: string;
  country: string;
}

export interface InvoiceLineItem {
  description: string;
  qty: number;
  unitPrice: number;
}

export interface InvoiceData {
  number: string;
  amount: number;
  currency: string;
  lineItems: InvoiceLineItem[];
  poRef: string;
}

export type Verdict = "green" | "amber" | "red";

export interface ClaimData {
  claimId: string;
  employeeId: string;
  submittedAt: string;
  market: "UK" | "US" | "DE" | "IN";
  currency: string;
  category: "meals" | "travel" | "accommodation" | "entertainment" | "miscellaneous";
  vendor: string;
  amount: number;
  attendees: number;
  receiptFilename?: string;
  receiptMismatchFlavour?: string;
  emsSource: "workday" | "concur";
}

export interface ToolCall {
  tool: string;
  argsPreview: string;
  ms: number;
  ok: boolean;
}

export interface ActionLedgerEntry {
  workflowId: string;
  timestamp: number;
  actorKind: "agent" | "human";
  actorId: string;
  action: string;
  revocable: boolean;
  details: Record<string, unknown>;
}

export interface Workflow {
  id: string;
  type:
    | "invoice-p2p" | "expense-claim" | "hiring"
    // Fleet/composed domains (compose-domain v3). Same shape as the rest;
    // domain-specific inputs go in `payload`.
    | "travel-preapproval" | "vendor-kyc" | "employee-onboarding"
    | "it-access-request" | "contract-renewal" | "perf-review"
    // Hand-graduated curve-proof domain.
    | "ap-invoice"
    // Hand-graduated wave 2: matrix-driven dynamic-persona domains.
    | "purchase-order" | "contract-review" | "privacy-dpia" | "treasury-fx";
  status: WorkflowStatus;
  currentPhase: PhaseName;
  createdAt: number;
  slaDueAt: number;
  // Invoice payload — set on type="invoice-p2p"
  vendor?: Vendor;
  invoice?: InvoiceData;
  // Expense payload — set on type="expense-claim"
  claim?: ClaimData;
  // Fleet/composed domains payload — set on the six fleet-* types.
  payload?: Record<string, unknown>;
  verdict?: Verdict;
  jurisdiction: string;
  agency: string;
  activeExceptionId?: string;
  actionLedger: ActionLedgerEntry[];
  tokensSpent: number;
  costUSD: number;
  // POC2 hiring stash — keys: candidate_id, candidate_name, role_family,
  // level_target, jurisdiction, right_to_work. Empty for POC1.
  metadata?: Record<string, unknown>;
  // POC2 §4.21 AG-UI: per-agent structured outputs lifted onto the workflow
  // ledger. Keyed by agent name (e.g. "cv_crystalliser"); each value carries
  // the canonical agent payload incl. an optional component_spec array.
  agentOutputs?: Record<string, { profile?: Record<string, unknown>; componentSpec?: unknown[]; component_spec?: unknown[]; inconsistencies?: unknown[] }>;
}

export interface Phase {
  workflowId: string;
  name: PhaseName;
  status: "pending" | "in_progress" | "completed" | "failed";
  startedAt?: number;
  completedAt?: number;
  agentId: "finance-agent";
  toolCalls: ToolCall[];
  spanIds: string[];
}

export interface OtelSpan {
  traceId: string;
  spanId: string;
  parentSpanId?: string;
  name: string;
  startMs: number;
  endMs: number;
  attributes: {
    "workflow.id": string;
    "workflow.phase": PhaseName;
    "tool.name"?: string;
    "llm.model"?: string;
    "llm.tokens.in"?: number;
    "llm.tokens.out"?: number;
    "cost.usd"?: number;
    [k: string]: unknown;
  };
  status: "ok" | "error";
}

export interface ExceptionOption {
  label: string;
  action: string;
  nonRevocable: boolean;
  recommended?: boolean;
}

export interface PolicyRef {
  title: string;
  snippet: string;
  source: string;
}

export interface Exception {
  id: string;
  workflowId: string;
  composedBy: "fleet-manager" | "guardrail" | "simulator-injected";
  severity: Severity;
  category: ExceptionCategory;
  summary: string;
  recommendation: string;
  options: ExceptionOption[];
  relatedPolicyRefs: PolicyRef[];
  bulkCandidateIds?: string[];
  confidence: number;
  createdAt: number;
  resolvedAt?: number;
  resolvedBy?: string;
}

export interface SkillAmplification {
  id: string;
  workflowId: string;
  policyContext: PolicyRef[];
  precedents: Array<{ workflowId: string; outcome: string; rationale: string }>;
  recommendedApproach: string;
  createdAt: number;
}

export interface AutonomyPolicy {
  id: string;
  description: string;
  currentValue: number | string | boolean;
  gitSha: string;
  author: string;
  updatedAt: number;
}

export function nextPhase(p: PhaseName): PhaseName | null {
  const i = PHASE_ORDER.indexOf(p);
  if (i === -1 || i === PHASE_ORDER.length - 1) return null;
  return PHASE_ORDER[i + 1];
}

export interface McpCall {
  workflowId: string;
  timestamp: number;
  tool: string;
  url: string;
  method: string;
  request: Record<string, unknown>;
  response: Record<string, unknown>;
  statusCode: number;
  durationMs: number;
}

export interface EconomicsPerModel {
  model: string;
  inputTokens: number;
  outputTokens: number;
  calls: number;
  costUsd: number;
}

export interface Economics {
  // NEW (2026-05-05): real model cost from gen_ai.usage.* span attributes.
  modelCostUsd: number;
  inputTokens: number;
  outputTokens: number;
  pricingSource: string;
  perModel: EconomicsPerModel[];
  // DEPRECATED alias of modelCostUsd, kept for back-compat.
  computeCostUsd: number;
  modelCalls: number;
  toolCalls: number;
  daysElapsed: number;
  slaToken: string;
}

export interface Narrative {
  whatHappened: string;
  whatAgentTried: string[];
  agentRecommendation: string;
}

export interface FleetEconomics {
  activeWorkflowCount: number;
  totalWorkflowCount: number;
  totalComputeCostUsd: number;
  totalModelCalls: number;
  totalToolCalls: number;
  averageCostPerWorkflow: number;
}

export interface WorkflowDetail {
  workflow: Workflow;
  phases: Phase[];
  spans: OtelSpan[];
  amplifications: SkillAmplification[];
  activeException: Exception | null;
  mcpCalls: McpCall[];
  economics: Economics;
  narrative: Narrative | null;
  // NEW (2026-05-05): live append-blob URL for the workflow's immutable
  // audit ledger. null when the cloud audit path isn't configured.
  auditBlobUrl?: string | null;
}
