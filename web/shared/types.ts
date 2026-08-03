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

// All per-domain phase ordering now lives in api/shared/domains.py and is
// served via /api/blueprint/composition (see
// web/client/hooks/useDomainRegistry.ts). The constants that used to live
// here — EXPENSE_PHASE_ORDER, HIRING_PHASE_ORDER, TRAVEL_PREAPPROVAL_…,
// VENDOR_KYC_…, EMPLOYEE_ONBOARDING_…, EMPLOYEE_TRANSFER_…,
// IT_ACCESS_REQUEST_…, CONTRACT_RENEWAL_…, PERF_REVIEW_…, AP_INVOICE_…,
// PURCHASE_ORDER_…, CONTRACT_REVIEW_…, PRIVACY_DPIA_…, TREASURY_FX_… —
// have been deleted to prevent the recurring "I added a domain to the
// registry but the UI still shows the wrong phase order" failure mode.
// New code: use usePhaseOrderFor(workflow_type) from useDomainRegistry.
//
// The PhaseName union below is retained because typed fixtures + tests
// still reference some of these names; widening it to `string` is a
// follow-up refactor.

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
  // Active workflow types come from the runtime domain registry. Keeping this
  // open lets newly graduated verticals render without a client release.
  type: string;
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
  agentId: string;
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

export interface McpCall {
  workflowId: string;
  toolCallId?: string | null;
  timestamp: number;
  tool: string;
  url: string;
  method: string;
  request: Record<string, unknown>;
  response: Record<string, unknown>;
  statusCode: number;
  durationMs: number;
}

export type CanonicalExecutionTimelineKind =
  | "workflow"
  | "phase"
  | "reasoning"
  | "agentOutput"
  | "tool"
  | "output"
  | "decision"
  | "ledger";

export type LegacyExecutionTimelineKind = "agent" | "system" | "error";
export type ExecutionTimelineKind = CanonicalExecutionTimelineKind | LegacyExecutionTimelineKind;

export interface ExecutionTimelineRow {
  id: string;
  ts: number;
  kind: ExecutionTimelineKind;
  label: string;
  status?: string | null;
  verdict?: string | null;
  actor?: string | null;
  actorKind?: string | null;
  agent?: string | null;
  agentId?: string | null;
  personaRole?: string | null;
  currentPhase?: string | null;
  phase?: string | null;
  name?: string | null;
  skill?: string | null;
  model?: string | null;
  startedAt?: number | string | null;
  completedAt?: number | string | null;
  completed_at?: number | string | null;
  decidedAt?: number | string | null;
  timestamp?: number | string | null;
  durationMs?: number | null;
  latencyMs?: number | null;
  tokens?: number | null;
  tokensIn?: number | null;
  tokensOut?: number | null;
  costUsd?: number | null;
  tool?: string | null;
  toolCallId?: string | null;
  mcpCallIndex?: number | null;
  method?: string | null;
  url?: string | null;
  request?: Record<string, unknown> | null;
  response?: Record<string, unknown> | null;
  statusCode?: number | null;
  resultSummary?: string | null;
  result_summary?: string | null;
  messages?: Array<Record<string, unknown>>;
  toolCalls?: unknown[];
  extractedJson?: unknown;
  command?: unknown;
  reasoning?: unknown;
  results?: unknown;
  reason?: string | null;
  details?: unknown;
  attributes?: Record<string, unknown>;
  spanIds?: string[];
  traceId?: string | null;
  spanId?: string | null;
  parentSpanId?: string | null;
  childWorkflowId?: string | null;
  childWorkflowType?: string | null;
  revocable?: boolean | null;
  decisionId?: string | null;
  policyVersion?: string | null;
  enforcementMode?: string | null;
  prevHash?: string | null;
  entryHash?: string | null;
  actorJws?: string | null;
  ledger?: Record<string, unknown>;
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

export interface WorkflowDetailResponse {
  workflow: Workflow;
  phases: Phase[];
  spans: OtelSpan[];
  amplifications: SkillAmplification[];
  activeException: Exception | null;
  mcpCalls: McpCall[];
  economics: Economics;
  narrative: Narrative | null;
  timeline: ExecutionTimelineRow[];
  auditBlobUrl?: string | null;
  packDetail?: Record<string, unknown> | null;
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
