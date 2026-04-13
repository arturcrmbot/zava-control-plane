// control-plane/src/shared/types.ts

export type PhaseName =
  | "Intake" | "Validation" | "Routing"
  | "Approval" | "Payment" | "Reconciliation";

export const PHASE_ORDER: PhaseName[] = [
  "Intake", "Validation", "Routing", "Approval", "Payment", "Reconciliation"
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

export interface ToolCall {
  tool: string;
  argsPreview: string;
  ms: number;
  ok: boolean;
}

export interface ActionLedgerEntry {
  workflowId: string;
  timestamp: number;
  actor: { kind: "agent" | "human"; id: string };
  action: string;
  revocable: boolean;
  details: Record<string, unknown>;
}

export interface Workflow {
  id: string;
  type: "invoice-p2p";
  status: WorkflowStatus;
  currentPhase: PhaseName;
  createdAt: number;
  slaDueAt: number;
  vendor: Vendor;
  invoice: InvoiceData;
  jurisdiction: string;
  agency: string;
  activeExceptionId?: string;
  actionLedger: ActionLedgerEntry[];
  tokensSpent: number;
  costUSD: number;
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
