// web/client/routes/BankingWorld.tsx
//
// Bespoke /world floor for the synthetic Zava Bank vertical. The view is fed
// only by the live banking world snapshot and causal event ring; no absolute
// positioning, no external brands.
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  BadgePoundSterling,
  Banknote,
  Building2,
  Clock3,
  Landmark,
  LockKeyhole,
  Scale,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  UsersRound,
} from "lucide-react";
import { type WorldEvent, type WorldState } from "@client/hooks/useWorldSimulation";
import { WorldInterventionStrip } from "@client/components/WorldInterventionStrip";
import { WorldObjectiveStrip } from "@client/components/WorldObjectiveStrip";
import { type InterventionStep } from "@client/lib/worldIntervention";

const RAIL_CAP = 8;
const CLAIM_CAP = 8;
const BENEFICIARY_CAP = 12;
const INVESTIGATION_CAP = 8;
const EXPOSURE_CAP = 24;
const POSITION_CAP = 12;
const JOURNAL_CAP = 42;

const ROUTINE_EVENTS = new Set([
  "banking.payment.settled",
  "banking.rail.throughput",
  "banking.exposure.revalued",
  "banking.position.marked",
]);

const FUNCTIONS = ["all", "payments", "retail-banking", "financial-crime", "credit-risk", "markets"] as const;
type FunctionFilter = typeof FUNCTIONS[number];

// Each action opens a NEW case. A claim's outcome follows from the facts the
// world draws for it; the kind only shapes those facts.
interface CaseAction { id: string; label: string; hint: string; kind: "claim" | "process" }
const CASE_ACTIONS: CaseAction[] = [
  { id: "new-fraud-claim", label: "Fraud claim reported", hint: "A customer reports an authorised push payment scam", kind: "claim" },
  { id: "new-fraud-claim:high-value", label: "High-value claim", hint: "A claim above the claims manager's delegated authority", kind: "claim" },
  { id: "new-fraud-claim:vulnerable", label: "Vulnerable customer claim", hint: "A claim from a customer with a vulnerability marker", kind: "claim" },
  { id: "mule-account-investigation", label: "Mule activity detected", hint: "A receiving account shows a mule pattern", kind: "process" },
  { id: "merchant-onboarding-risk", label: "Merchant risk flagged", hint: "A merchant application needs a risk decision", kind: "process" },
];
const CASE_LABELS: Record<string, string> = {
  "app-fraud-reimbursement": "Fraud claim",
  "mule-account-investigation": "Mule investigation",
  "merchant-onboarding-risk": "Merchant review",
};
const RECENT_CASES_CAP = 8;

interface RecentCase { id: string; type: string; status: string; phase?: string; createdAt: number; refused: boolean }

/** The bank's latest cases, newest first, each one openable. */
function useRecentCases(): RecentCase[] {
  const [cases, setCases] = useState<RecentCase[]>([]);
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const response = await fetch("/api/workflows");
        if (!response.ok) return;
        const data: unknown = await response.json();
        const rows = Array.isArray(data) ? data : [];
        if (cancelled) return;
        setCases(
          rows
            .filter((w: Record<string, unknown>) => typeof w.id === "string" && String(w.type) in CASE_LABELS)
            .map((w: Record<string, unknown>) => ({
              id: String(w.id),
              type: String(w.type),
              status: String(w.status ?? ""),
              phase: text(w.currentPhase),
              createdAt: Number(w.createdAt ?? 0),
              refused: Boolean((w.metadata as Record<string, unknown> | undefined)?.rejected),
            }))
            .sort((a, b) => b.createdAt - a.createdAt)
            .slice(0, RECENT_CASES_CAP),
        );
      } catch {
        // Keep the last list on a transient failure; the next poll retries.
      }
    };
    void load();
    const timer = window.setInterval(() => void load(), 3000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);
  return cases;
}

function caseStatus(c: RecentCase): { label: string; tone: string } {
  if (c.refused) return { label: "refused by authority", tone: "bg-red-50 text-red-700 dark:bg-red-950/50 dark:text-red-300" };
  if (c.status === "completed") return { label: "decided", tone: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300" };
  if (c.status === "failed") return { label: "failed", tone: "bg-red-50 text-red-700 dark:bg-red-950/50 dark:text-red-300" };
  if (c.status === "awaiting_hitl") return { label: "awaiting decision", tone: "bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300" };
  return { label: "agents working", tone: "bg-blue-50 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300" };
}

interface BankSnapshot extends WorldState {
  bank?: {
    customer_count?: number;
    vulnerable_customer_count?: number;
    account_count?: number;
    payment_count?: number;
    beneficiary_count?: number;
    corporate_client_count?: number;
    position_count?: number;
    payments_settled_total?: number;
    settled_value_gbp?: number;
    positions_marked_total?: number;
    positions_mtm_gbp?: number;
  };
  payment_rails?: PaymentRail[];
  recent_settlements?: RecentSettlement[];
  beneficiaries?: Beneficiary[];
  fraud_claims?: FraudClaim[];
  reimbursement_commands?: ReimbursementCommand[];
  reimbursement_evaluations?: ReimbursementEvaluation[];
  investigations?: Investigation[];
  counterparties?: Counterparty[];
  credit_limits?: CreditLimit[];
  exposures?: Exposure[];
  positions?: Position[];
}

interface PaymentRail {
  id: string;
  display_name?: string;
  settlement_window_minutes?: number;
  in_flight_count?: number;
  status?: string;
  last_event_id?: string | null;
}
interface RecentSettlement { payment_id: string; rail_id: string; amount_gbp: number; sim_time: number; event_id: string }
interface FraudClaim {
  id: string;
  customer_id: string;
  payment_id: string;
  beneficiary_id: string;
  rail_id: string;
  amount_gbp: number;
  vulnerability_flag?: boolean;
  status?: string;
  recoverable_gbp?: number;
  last_event_id?: string | null;
  /** The claim's story has started; dormant hero claims are not open work. */
  raised?: boolean;
}
interface Beneficiary {
  id: string;
  holder_id?: string;
  holder_kind?: string;
  status?: string;
  balance_gbp?: number;
  frozen_gbp?: number;
  last_event_id?: string | null;
}
interface ReimbursementCommand {
  id: string;
  workflow_id?: string;
  decision_id?: string;
  claim_id: string;
  option_id?: string;
  persona?: string;
  value_gbp?: number;
  action_types?: string[];
  last_event_id?: string | null;
}
interface ReimbursementEvaluation {
  id: string;
  command_id?: string;
  claim_id: string;
  option_id?: string;
  status?: string;
  reimbursed_gbp?: number;
  recovered_from_beneficiary_gbp?: number;
  receiving_psp_share_gbp?: number;
  synthetic_cost_gbp?: number;
  no_action_customer_loss_gbp?: number;
  vulnerability_respected?: boolean;
  last_event_id?: string | null;
}
interface Investigation { id: string; subject_id?: string; subject_kind?: string; status?: string; linked_claim_ids?: string[]; opened_by_workflow_id?: string; last_event_id?: string | null }
interface Counterparty { id: string; display_name?: string; rating?: string; status?: string }
interface CreditLimit { id: string; counterparty_id: string; limit_gbp?: number; status?: string }
interface Exposure { id: string; counterparty_id: string; limit_id?: string; current_gbp?: number; excess_gbp?: number; status?: string; last_event_id?: string | null }
interface Position { id: string; counterparty_id: string; instrument?: string; notional_gbp?: number; mark_to_market_gbp?: number; status?: string; last_event_id?: string | null }

const PULSE_CSS = `
@keyframes bankPulse { 0% { box-shadow: 0 0 0 0 rgba(14,165,233,0.48); transform: translateY(-1px); } 100% { box-shadow: 0 0 0 10px rgba(14,165,233,0); transform: translateY(0); } }
@keyframes bankGlow { 0%, 100% { opacity: .42; } 50% { opacity: 1; } }
.bank-pulse { animation: bankPulse 1.1s ease-out; }
.bank-live-glow { animation: bankGlow 1.8s ease-in-out infinite; }
`;

function n(value: number | undefined): number { return Math.round(value ?? 0); }
function compactInt(value: number | undefined): string { return new Intl.NumberFormat("en-GB").format(n(value)); }
function money(value: number | undefined, compact = false): string {
  const amount = value ?? 0;
  if (compact && Math.abs(amount) >= 1_000_000) return `£${(amount / 1_000_000).toFixed(Math.abs(amount) >= 10_000_000 ? 0 : 1)}m`;
  if (compact && Math.abs(amount) >= 1_000) return `£${(amount / 1_000).toFixed(Math.abs(amount) >= 100_000 ? 0 : 1)}k`;
  return new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 }).format(amount);
}
function pct(value: number): string { return `${Math.round(value * 100)}%`; }
function eventFunction(event: WorldEvent): string { return String(event.payload?.function ?? "operations"); }
function duration(minutes: number | undefined): string {
  const m = n(minutes);
  if (m >= 1440 && m % 1440 === 0) return `${m / 1440}-day cycle`;
  if (m >= 60 && m % 60 === 0) return `${m / 60} h window`;
  return `${m} min window`;
}
function simClock(minutes: number | undefined): string {
  const m = n(minutes);
  const days = Math.floor(m / 1440);
  const clock = `${String(Math.floor((m % 1440) / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
  return days > 0 ? `day ${days + 1} · ${clock}` : clock;
}
const OPTION_LABELS: Record<string, string> = {
  "SYN-APP-OPTION-REIMBURSE-FULL": "Reimburse in full",
  "SYN-APP-OPTION-REIMBURSE-CAPPED": "Reimburse to the £85k cap",
  "SYN-APP-OPTION-REFUSE-CAUTION": "Refuse · customer caution",
};
function roleLabel(role: string): string {
  const words = role.replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}
/** The orchestrator names the governing rule as `AUTH-<role>-<action>`. */
function authorisedRole(reasoning: string): string | undefined {
  return reasoning.match(/matched rule AUTH-([a-z_]+)-/)?.[1];
}

/** What the world journal says happened to one fraud claim, kept after the
 *  story's events scroll out of the ring. */
interface ClaimFacts {
  trace: string;
  workflowId?: string;
  decidedOption?: string;
  decidedValue?: number;
  refusal?: { reasoning: string; role?: string };
  failure?: string;
  closed?: boolean;
}

function collectClaimFacts(events: WorldEvent[], into: Map<string, ClaimFacts>): Map<string, ClaimFacts> {
  const claimByTrace = new Map<string, string>();
  for (const [claimId, facts] of into) claimByTrace.set(facts.trace, claimId);
  for (const event of events) {
    if (event.type === "banking.app_fraud.claim_raised") {
      const claimId = String(event.payload?.claim_id ?? event.actor_id ?? "");
      if (!claimId) continue;
      claimByTrace.set(event.trace_id, claimId);
      if (!into.has(claimId)) into.set(claimId, { trace: event.trace_id });
      continue;
    }
    const claimId = claimByTrace.get(event.trace_id);
    const facts = claimId ? into.get(claimId) : undefined;
    if (!facts) continue;
    if (event.type === "responder.requested") {
      facts.workflowId = String(event.payload?.workflow_id ?? "") || facts.workflowId;
    } else if (event.type === "responder.decided") {
      const command = event.payload?.command as { payload?: Record<string, unknown> } | undefined;
      facts.decidedOption = String(command?.payload?.option_id ?? "") || facts.decidedOption;
      const value = Number(command?.payload?.value_gbp);
      if (Number.isFinite(value)) facts.decidedValue = value;
    } else if (event.type === "responder.deferred") {
      const reasoning = String(event.payload?.reasoning ?? "refused");
      facts.refusal = { reasoning, role: authorisedRole(reasoning) };
    } else if (event.type === "responder.failed") {
      facts.failure = String(event.payload?.error ?? "workflow failed");
    } else if (event.type === "objective.resolved" || event.type === "objective.failed") {
      facts.closed = true;
    }
  }
  return into;
}

/** The causal chain of the newest fraud claim, in the bank's language. */
function deriveClaimStory(events: WorldEvent[]): { trace: string; steps: InterventionStep[] } | null {
  let trace: string | null = null;
  for (const event of events) if (event.type === "banking.app_fraud.claim_raised") trace = event.trace_id;
  if (!trace) return null;
  const steps: InterventionStep[] = [];
  const seen = new Set<string>();
  let refused = false;
  for (const event of events) {
    if (event.trace_id !== trace || seen.has(event.type)) continue;
    const p = event.payload ?? {};
    let step: Omit<InterventionStep, "eventId"> | null = null;
    switch (event.type) {
      case "banking.app_fraud.claim_raised":
        step = { label: "Claim raised", detail: `${money(Number(p.amount_gbp ?? 0))} · ${String(p.customer_id ?? "")}${p.vulnerability_flag ? " · vulnerable" : ""}` };
        break;
      case "sensor.tripped":
        step = { label: "Fraud signal detected" };
        break;
      case "objective.opened":
        step = { label: "Case opened", detail: roleLabel(String(p.owner_function ?? "retail_banking").replaceAll("-", "_")) };
        break;
      case "responder.requested":
        step = { label: "Agents investigating", detail: String(p.workflow_id ?? "") || undefined };
        break;
      case "responder.decided": {
        const command = p.command as { payload?: Record<string, unknown> } | undefined;
        const option = String(command?.payload?.option_id ?? "");
        const value = Number(command?.payload?.value_gbp);
        step = { label: "Decision approved", detail: [OPTION_LABELS[option] ?? option, Number.isFinite(value) ? money(value) : ""].filter(Boolean).join(" · ") };
        break;
      }
      case "responder.deferred": {
        refused = true;
        const role = authorisedRole(String(p.reasoning ?? ""));
        step = { label: "Refused by authority", detail: role ? `needs ${roleLabel(role)}` : "outside delegated authority" };
        break;
      }
      case "responder.failed":
        step = { label: "Workflow failed", detail: String(p.error ?? "") || undefined };
        break;
      case "banking.investigation.opened":
        step = { label: "Mule account investigated", detail: `${String(p.beneficiary_id ?? "")} → ${String(p.holder_id ?? "")}${p.holder_kind === "corporate" ? " (corporate client)" : ""}` };
        break;
      case "banking.reimbursement.applied":
        step = { label: "Customer reimbursed", detail: money(Number(p.value_gbp ?? 0)) };
        break;
      case "evaluation.resolved":
        step = { label: "Outcome evaluated" };
        break;
      case "objective.resolved":
        step = { label: "Case closed" };
        break;
      case "objective.failed":
        step = { label: refused ? "Escalation required" : "Case left open" };
        break;
    }
    if (!step) continue;
    seen.add(event.type);
    steps.push({ ...step, eventId: event.event_id });
  }
  return { trace, steps };
}

interface DecisionContext {
  persona?: string;
  phase?: string;
  impact?: string;
  optionId?: string;
  value?: number;
  reasoning?: string;
  allowed?: boolean;
}
interface PendingDecision { id: string; workflowId: string; summary?: string; context?: DecisionContext }

function text(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

/** The gate's own context: who decides, what the agents recommend and why,
 *  and whether it sits inside the decision-maker's delegated authority. */
function decisionContext(detail: unknown): DecisionContext | undefined {
  const payload = ((detail as { workflow?: { payload?: Record<string, unknown> } } | null)?.workflow?.payload ?? {}) as Record<string, unknown>;
  const evidence = (payload.evidence ?? {}) as Record<string, unknown>;
  const hitl = (payload.hitl_context ?? evidence.hitl_context) as Record<string, unknown> | undefined;
  if (!hitl) return undefined;
  const option = (hitl.selected_option ?? {}) as Record<string, unknown>;
  const ranking = (hitl.ranking ?? {}) as Record<string, unknown>;
  const authority = (hitl.authority ?? {}) as Record<string, unknown>;
  const value = Number(option.value_gbp);
  return {
    persona: text(hitl.persona),
    phase: text(hitl.phase),
    impact: text(option.impact),
    optionId: text(option.option_id),
    value: Number.isFinite(value) ? value : undefined,
    reasoning: text(ranking.reasoning),
    allowed: typeof authority.allowed === "boolean" ? authority.allowed : undefined,
  };
}

function excerpt(reasoning: string, max = 220): string {
  const firstTwo = reasoning.split(/(?<=\.)\s+/).slice(0, 2).join(" ");
  return firstTwo.length <= max ? firstTwo : `${firstTwo.slice(0, max - 1).replace(/\s+\S*$/, "")}…`;
}

/** The operator queue: workflows actually waiting on a human right now. */
function usePendingDecisions(): PendingDecision[] {
  const [rows, setRows] = useState<PendingDecision[]>([]);
  const contexts = useRef<Map<string, DecisionContext>>(new Map());
  useEffect(() => {
    let cancelled = false;
    // Only a found context is cached: a gate whose context has not been
    // persisted yet is looked up again on the next poll.
    const contextFor = async (workflowId: string): Promise<DecisionContext | undefined> => {
      const cached = contexts.current.get(workflowId);
      if (cached) return cached;
      try {
        const response = await fetch(`/api/workflows/${encodeURIComponent(workflowId)}`);
        const found = response.ok ? decisionContext(await response.json()) : undefined;
        if (found) contexts.current.set(workflowId, found);
        return found;
      } catch {
        return undefined;
      }
    };
    const load = async () => {
      try {
        const response = await fetch("/api/exceptions");
        if (!response.ok) return;
        const data: unknown = await response.json();
        if (cancelled || !Array.isArray(data)) return;
        const queue = data
          .map((row: Record<string, unknown>) => ({
            id: String(row.id ?? ""),
            workflowId: String(row.workflowId ?? row.workflow_id ?? ""),
            summary: text(row.summary),
          }))
          .filter((row) => row.id && row.workflowId);
        const enriched = await Promise.all(queue.map(async (row) => ({ ...row, context: await contextFor(row.workflowId) })));
        if (!cancelled) setRows(enriched);
      } catch {
        // A transient queue failure must not blank the floor; the next poll retries.
      }
    };
    void load();
    const timer = window.setInterval(() => void load(), 3000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);
  return rows;
}

export default function BankingWorld({
  state, events, loading, error, onRunScenario,
}: {
  state: WorldState;
  events: WorldEvent[];
  loading: boolean;
  error: string | null;
  onRunScenario: (name: string) => Promise<void>;
  onRunProcess: (workflowType: string) => Promise<void>;
}) {
  const bank = state as unknown as BankSnapshot;
  const [busy, setBusy] = useState(false);
  const [selectedActor, setSelectedActor] = useState<string | null>(null);
  const [functionFilter, setFunctionFilter] = useState<FunctionFilter>("all");
  const [showRoutine, setShowRoutine] = useState(false);
  const pendingDecisions = usePendingDecisions();
  const recentCases = useRecentCases();
  const derived = useMemo(() => deriveClaimStory(events), [events]);
  const [persistedStory, setPersistedStory] = useState<{ trace: string; steps: InterventionStep[] } | null>(null);
  // Facts accumulate so an outcome stays visible after its events leave the
  // ring; a world reset (the journal's newest seq going backwards) clears them.
  const newestSeq = events.length ? events[events.length - 1].seq : 0;
  const factsRef = useRef<{ latestSeq: number; facts: Map<string, ClaimFacts> }>({ latestSeq: 0, facts: new Map() });
  const claimFacts = useMemo(() => {
    if (newestSeq < factsRef.current.latestSeq) factsRef.current.facts = new Map();
    factsRef.current.latestSeq = newestSeq;
    return new Map(collectClaimFacts(events, factsRef.current.facts));
  }, [events, newestSeq]);

  useEffect(() => {
    if (derived) setPersistedStory(derived);
  }, [derived]);
  const storySeqRef = useRef(0);
  useEffect(() => {
    if (newestSeq < storySeqRef.current) setPersistedStory(null);
    storySeqRef.current = newestSeq;
  }, [newestSeq]);

  const story = derived ?? persistedStory;
  const raisedClaims = useMemo(() => (bank.fraud_claims ?? []).filter((claim) => claim.raised), [bank.fraud_claims]);
  const openClaims = raisedClaims.filter((claim) => claim.status !== "reimbursed" && claim.status !== "refused" && !claimFacts.get(claim.id)?.closed);
  const pendingWorkflowIds = useMemo(() => new Set(pendingDecisions.map((row) => row.workflowId)), [pendingDecisions]);
  const toggleActor = (id: string | null) => setSelectedActor((cur) => (cur === id ? null : id));
  const recentRefs = useMemo(() => {
    const refs = new Map<string, number>();
    for (const event of events) {
      if (event.actor_id) refs.set(event.actor_id, event.seq);
      if (event.target_id) refs.set(event.target_id, event.seq);
      const rail = event.payload?.rail_id;
      if (typeof rail === "string") refs.set(rail, event.seq);
      const claim = event.payload?.claim_id;
      if (typeof claim === "string") refs.set(claim, event.seq);
    }
    return refs;
  }, [events]);
  const journal = useMemo(() => {
    let source = events;
    if (!showRoutine) source = source.filter((event) => !ROUTINE_EVENTS.has(event.type));
    if (functionFilter !== "all") source = source.filter((event) => eventFunction(event) === functionFilter);
    if (selectedActor) {
      source = source.filter((event) => event.actor_id === selectedActor || event.target_id === selectedActor || event.trace_id === selectedActor || event.payload?.claim_id === selectedActor || event.payload?.rail_id === selectedActor);
    }
    return source.slice(-JOURNAL_CAP).reverse();
  }, [events, functionFilter, selectedActor, showRoutine]);

  async function runAction(action: CaseAction) {
    setBusy(true);
    try {
      if (action.kind === "claim") {
        await onRunScenario(action.id);
      } else {
        await fetch(`/api/simulator/inject-burst?n=1&workflow_type=${encodeURIComponent(action.id)}`, { method: "POST" });
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div data-testid="banking-world-route" className="flex-1 min-w-0 overflow-y-auto overflow-x-hidden bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100 p-4 lg:p-6">
      <style>{PULSE_CSS}</style>
      <div className="max-w-[1400px] mx-auto space-y-4">
        <header className="rounded-2xl border border-slate-200 bg-white/90 p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900/80">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-center gap-3">
                <div className="rounded-xl bg-blue-600 p-2 text-white shadow-sm shadow-blue-500/30"><Landmark size={22} /></div>
                <div>
                  <h1 className="text-2xl font-semibold tracking-tight text-slate-950 dark:text-white">Bank operations</h1>
                  <p className="text-sm text-slate-500 dark:text-slate-400">Zava Bank · synthetic</p>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-medium ${bank.enabled && bank.status === "running" ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300" : "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-300"}`}>
                  <span className={`h-2 w-2 rounded-full bg-emerald-500 ${bank.enabled && bank.status === "running" ? "bank-live-glow" : ""}`} /> Autonomous · world live
                </span>
                <span data-testid="humans-in-the-loop" className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-medium ${pendingDecisions.length > 0 ? "bg-amber-100 text-amber-800 ring-1 ring-amber-300 dark:bg-amber-950/60 dark:text-amber-200 dark:ring-amber-800" : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"}`}>
                  <Scale size={13} className={pendingDecisions.length > 0 ? "bank-live-glow" : ""} /><span>Decisions waiting: <span data-testid="decisions-waiting" className="tabular-nums">{pendingDecisions.length}</span></span>
                </span>
                <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300"><Clock3 size={13} /> sim <span className="tabular-nums">{simClock(bank.sim_time)}</span></span>
              </div>
            </div>
            <div className="grid w-full gap-2 sm:grid-cols-2 lg:w-auto lg:grid-cols-5">
              <HeaderMetric testId="bank-stat-payments" icon={<Banknote size={16} />} label="Payments settled" value={compactInt(bank.bank?.payments_settled_total)} sub={money(bank.bank?.settled_value_gbp, true)} />
              <HeaderMetric testId="bank-stat-customers" icon={<UsersRound size={16} />} label="Customers" value={compactInt(bank.bank?.customer_count)} sub={`${compactInt(bank.bank?.vulnerable_customer_count)} vulnerable`} />
              <HeaderMetric testId="bank-stat-claims" icon={<ShieldAlert size={16} />} label="Open fraud claims" value={compactInt(openClaims.length)} sub={`${compactInt(raisedClaims.length)} raised`} />
              <HeaderMetric testId="bank-stat-beneficiaries" icon={<LockKeyhole size={16} />} label="Beneficiaries watched" value={compactInt((bank.beneficiaries ?? []).filter((b) => b.status === "under_review" || b.status === "frozen").length)} sub="under review / frozen" />
              <HeaderMetric testId="bank-stat-mtm" icon={<TrendingUp size={16} />} label="Positions MTM" value={money(bank.bank?.positions_mtm_gbp, true)} sub={`${compactInt(bank.bank?.positions_marked_total)} marks`} />
            </div>
          </div>
        </header>

        {error && <div data-testid="banking-error" className="rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-800 dark:bg-red-950/40 dark:text-red-300">{error}</div>}

        <section aria-label="Make something happen" className="rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
          <div className="flex flex-wrap items-center gap-2">
            <span className="mr-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Make something happen</span>
            {CASE_ACTIONS.map((action) => (
              <button key={action.id} type="button" title={action.hint} disabled={busy || !bank.enabled} onClick={() => void runAction(action)} className="rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-700 transition hover:border-blue-300 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800/80 dark:text-slate-200 dark:hover:bg-blue-950/30">
                {action.label}
              </button>
            ))}
          </div>
        </section>

        <section data-testid="recent-cases" aria-label="Recent cases" className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400"><Activity size={15} /> Recent cases</div>
          {recentCases.length === 0 ? (
            <div data-testid="recent-cases-empty" className="text-xs text-slate-400">No cases yet. Make something happen above.</div>
          ) : (
            <div className="grid gap-1.5 md:grid-cols-2">
              {recentCases.map((c) => {
                const status = caseStatus(c);
                return (
                  <a key={c.id} data-testid={`case-${c.id}`} href={`/workflows/${encodeURIComponent(c.id)}`} className="flex items-center justify-between gap-2 rounded-lg border border-slate-100 bg-slate-50 px-2.5 py-1.5 text-xs transition hover:border-blue-300 hover:bg-blue-50 dark:border-slate-800 dark:bg-slate-950/50 dark:hover:bg-blue-950/30">
                    <span className="min-w-0 truncate"><span className="font-medium text-slate-800 dark:text-slate-100">{CASE_LABELS[c.type]}</span> <span className="font-mono text-slate-500">{c.id}</span>{c.phase ? <span className="text-slate-400"> · {c.phase}</span> : null}</span>
                    <span className="flex shrink-0 items-center gap-2"><span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${status.tone}`}>{status.label}</span><span className="text-blue-600 dark:text-blue-400">Open →</span></span>
                  </a>
                );
              })}
            </div>
          )}
        </section>

        <WorldObjectiveStrip testId="banking-objective" objectives={bank.objectives} />
        {story && story.steps.length > 0 && <WorldInterventionStrip testId="banking-intervention" trace={story.trace} steps={story.steps} onTrace={toggleActor} />}

        {pendingDecisions.length > 0 && (
          <section data-testid="pending-decisions" aria-label="Decisions waiting" className="rounded-xl border border-amber-300 bg-amber-50 p-3 shadow-sm dark:border-amber-800 dark:bg-amber-950/30">
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-amber-800 dark:text-amber-200"><Scale size={15} className="bank-live-glow" /> Waiting for a decision</div>
            <div className="grid gap-2 lg:grid-cols-2">
              {pendingDecisions.map((decision) => {
                const context = decision.context;
                const recommendation = context?.impact ?? (context?.optionId ? OPTION_LABELS[context.optionId] ?? context.optionId : undefined);
                return (
                  <div key={decision.id} data-testid={`pending-${decision.workflowId}`} className="flex items-start justify-between gap-3 rounded-lg border border-amber-200 bg-white px-3 py-2 dark:border-amber-900 dark:bg-slate-900">
                    <div className="min-w-0">
                      <div className="font-mono text-[11px] text-slate-500">{decision.workflowId}</div>
                      {context?.persona ? (
                        <>
                          <div className="mt-0.5 text-sm font-semibold text-slate-900 dark:text-white">{roleLabel(context.persona)}{context.phase ? ` · ${context.phase}` : ""}</div>
                          {recommendation && <div className="mt-1 text-xs text-slate-700 dark:text-slate-200">Agents recommend: {recommendation}{context.value !== undefined ? ` · ${money(context.value)}` : ""}</div>}
                          {context.reasoning && <div className="mt-1 text-xs italic text-slate-500 dark:text-slate-400">“{excerpt(context.reasoning)}”</div>}
                          {context.allowed !== undefined && (
                            <span className={`mt-1.5 inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold ${context.allowed ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300" : "bg-red-50 text-red-700 dark:bg-red-950/50 dark:text-red-300"}`}>
                              {context.allowed ? "Within delegated authority" : "Outside delegated authority"}
                            </span>
                          )}
                        </>
                      ) : (
                        <div className="mt-0.5 text-sm font-medium text-slate-900 dark:text-white">{decision.summary ?? "Decision requested"}</div>
                      )}
                    </div>
                    <a href={`/workflows/${encodeURIComponent(decision.workflowId)}`} className="shrink-0 rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-700">Review &amp; decide →</a>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        <Panel title="Payment rails" icon={<Activity size={16} />}>
          <div className="grid gap-3 md:grid-cols-3">
            {(bank.payment_rails ?? []).slice(0, RAIL_CAP).map((rail) => (
              <RailCard key={`${rail.id}:${recentRefs.get(rail.id) ?? rail.last_event_id ?? 0}`} rail={rail} pulse={recentRefs.has(rail.id)} selected={selectedActor === rail.id} onClick={() => toggleActor(rail.id)} />
            ))}
          </div>
          <div className="mt-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500"><BadgePoundSterling size={14} /> Recent settlements</div>
          <div data-testid="recent-settlements" className="mt-2 grid gap-1.5 sm:grid-cols-2 xl:grid-cols-4">
            {(bank.recent_settlements ?? []).slice(-RAIL_CAP).reverse().map((settlement) => (
              <button key={`${settlement.event_id}:${settlement.payment_id}`} type="button" onClick={() => toggleActor(settlement.payment_id)} className="bank-pulse flex w-full items-center justify-between gap-2 rounded-lg border border-slate-100 bg-slate-50 px-2 py-1.5 text-left text-[11px] dark:border-slate-800 dark:bg-slate-950/50">
                <span className="min-w-0 truncate font-mono text-slate-700 dark:text-slate-200">{settlement.payment_id}</span>
                <span className="shrink-0 tabular-nums text-slate-500">{money(settlement.amount_gbp)} · {settlement.rail_id.replace("SYN-RAIL-", "")}</span>
              </button>
            ))}
          </div>
        </Panel>

        <section className="grid grid-cols-1 items-start gap-3 xl:grid-cols-3">
          <Panel title="Fraud claims" icon={<ShieldCheck size={16} />} className="xl:col-span-2">
            {raisedClaims.length === 0 ? (
              <div data-testid="claims-empty" className="rounded-lg border border-dashed border-slate-200 px-3 py-6 text-center text-sm text-slate-500 dark:border-slate-800">
                No fraud claims raised. Start a story above and watch the bank respond.
              </div>
            ) : (
              <div className="grid gap-3 lg:grid-cols-3">
                {raisedClaims.slice(0, CLAIM_CAP).map((claim) => {
                  const facts = claimFacts.get(claim.id);
                  return (
                    <ClaimCard key={`${claim.id}:${recentRefs.get(claim.id) ?? claim.last_event_id ?? 0}`} claim={claim} evaluation={(bank.reimbursement_evaluations ?? []).find((e) => e.claim_id === claim.id)} facts={facts} awaitingHuman={Boolean(facts?.workflowId && pendingWorkflowIds.has(facts.workflowId))} selected={selectedActor === claim.id} onClick={() => toggleActor(claim.id)} />
                  );
                })}
              </div>
            )}
          </Panel>
          <Panel title="Financial crime" icon={<ShieldAlert size={16} />}>
            <div className="space-y-3">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Beneficiaries under review / frozen</div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {(bank.beneficiaries ?? []).slice(0, BENEFICIARY_CAP).map((beneficiary) => <StatusChip key={beneficiary.id} label={beneficiary.id} status={beneficiary.status ?? "review"} onClick={() => toggleActor(beneficiary.id)} />)}
                  {(bank.beneficiaries ?? []).length === 0 && <span className="text-xs text-slate-400">none in play</span>}
                </div>
              </div>
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Investigations</div>
                <div className="mt-1.5 space-y-1.5">
                  {(bank.investigations ?? []).slice(0, INVESTIGATION_CAP).map((investigation) => (
                    <button key={investigation.id} type="button" onClick={() => toggleActor(investigation.id)} className="w-full rounded-lg bg-slate-50 px-2 py-1.5 text-left text-[11px] dark:bg-slate-950/50">
                      <span className="font-mono font-semibold">{investigation.id}</span><span className="text-slate-500"> · {investigation.subject_id} · {investigation.status ?? "open"}</span>
                    </button>
                  ))}
                  {(bank.investigations ?? []).length === 0 && <div className="text-xs text-slate-400">no open investigations</div>}
                </div>
              </div>
            </div>
          </Panel>
        </section>

        <section className="grid grid-cols-1 items-start gap-3 xl:grid-cols-2">
          <Panel title="Credit risk" icon={<Building2 size={16} />}>
            <ExposureList exposures={bank.exposures ?? []} limits={bank.credit_limits ?? []} counterparties={bank.counterparties ?? []} onActor={toggleActor} />
          </Panel>
          <Panel title="Markets" icon={<TrendingUp size={16} />}>
            <PositionList positions={bank.positions ?? []} counterparties={bank.counterparties ?? []} onActor={toggleActor} />
          </Panel>
        </section>

        <Journal events={journal} selectedActor={selectedActor} functionFilter={functionFilter} showRoutine={showRoutine} loading={loading} onFunctionFilter={setFunctionFilter} onRoutine={setShowRoutine} onActor={toggleActor} onClear={() => setSelectedActor(null)} />
      </div>
    </div>
  );
}

function HeaderMetric({ testId, icon, label, value, sub }: { testId: string; icon: React.ReactNode; label: string; value: string; sub: string }) {
  return <div data-testid={testId} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-800 dark:bg-slate-950/60"><div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">{icon}{label}</div><div className="mt-1 text-lg font-semibold tabular-nums text-slate-950 dark:text-white">{value}</div><div className="text-[11px] text-slate-500 dark:text-slate-400">{sub}</div></div>;
}
function Panel({ title, icon, className = "", children }: { title: string; icon: React.ReactNode; className?: string; children: React.ReactNode }) {
  return <section className={`rounded-xl border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900 ${className}`}><div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">{icon}{title}</div>{children}</section>;
}
function RailCard({ rail, pulse, selected, onClick }: { rail: PaymentRail; pulse: boolean; selected: boolean; onClick: () => void }) {
  return <button type="button" onClick={onClick} className={`w-full rounded-xl border px-3 py-3 text-left transition ${selected ? "ring-2 ring-blue-400" : ""} ${pulse ? "bank-pulse" : ""} border-slate-200 bg-gradient-to-br from-slate-50 to-white dark:border-slate-800 dark:from-slate-950 dark:to-slate-900`}><div className="flex items-center justify-between gap-2"><span className="font-semibold text-slate-900 dark:text-white">{rail.display_name ?? rail.id}</span><span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold uppercase text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300">{rail.status ?? "operational"}</span></div><div className="mt-3 flex items-end justify-between"><div><div className="text-2xl font-semibold tabular-nums">{compactInt(rail.in_flight_count)}</div><div className="text-[11px] text-slate-500">in flight</div></div><div className="text-right text-[11px] text-slate-500"><div>{rail.id.replace("SYN-RAIL-", "")}</div><div>{duration(rail.settlement_window_minutes)}</div></div></div></button>;
}
function ClaimCard({ claim, evaluation, facts, awaitingHuman, selected, onClick }: { claim: FraudClaim; evaluation?: ReimbursementEvaluation; facts?: ClaimFacts; awaitingHuman: boolean; selected: boolean; onClick: () => void }) {
  const refused = Boolean(facts?.refusal) || claim.status === "refused";
  const reimbursed = evaluation?.reimbursed_gbp ?? (claim.status === "reimbursed" ? facts?.decidedValue : undefined);
  const capped = reimbursed !== undefined && reimbursed > 0 && reimbursed < claim.amount_gbp;
  let outcome: string;
  let tone = "text-slate-700 dark:text-slate-200";
  if (refused) {
    const role = facts?.refusal?.role;
    outcome = role ? `Refused by authority · needs ${roleLabel(role)}` : "Refused by authority";
    tone = "text-red-700 dark:text-red-300";
  } else if (reimbursed !== undefined) {
    outcome = `${capped ? "Reimbursed to the cap" : "Reimbursed in full"} · ${money(reimbursed)}`;
    tone = "text-emerald-700 dark:text-emerald-300";
  } else if (facts?.failure) {
    outcome = `Workflow failed · ${facts.failure}`;
    tone = "text-red-700 dark:text-red-300";
  } else if (awaitingHuman) {
    outcome = "Waiting for the fraud decision manager";
    tone = "text-amber-700 dark:text-amber-300";
  } else {
    outcome = facts?.workflowId ? "Agents investigating…" : "Raised · opening a case";
  }
  const status = refused ? "refused" : reimbursed !== undefined ? "reimbursed" : awaitingHuman ? "awaiting decision" : "in progress";
  const surface = refused
    ? "border-red-200 bg-red-50/70 dark:border-red-900 dark:bg-red-950/20"
    : awaitingHuman
      ? "border-amber-300 bg-amber-50/70 dark:border-amber-800 dark:bg-amber-950/20"
      : claim.vulnerability_flag
        ? "border-purple-200 bg-purple-50/70 dark:border-purple-900 dark:bg-purple-950/20"
        : "border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-950/50";
  return (
    <button type="button" data-testid={`claim-${claim.id}`} onClick={onClick} className={`rounded-xl border p-3 text-left transition ${selected ? "ring-2 ring-blue-400" : ""} ${surface}`}>
      <div className="flex items-center justify-between gap-2"><span className="font-mono text-xs font-semibold">{claim.id}</span><span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-semibold uppercase text-slate-600 dark:bg-slate-900 dark:text-slate-300">{status}</span></div>
      <div className="mt-2 text-xl font-semibold tabular-nums">{money(claim.amount_gbp)}</div>
      <div className="mt-1 text-[11px] text-slate-500">{claim.customer_id} · {claim.rail_id.replace("SYN-RAIL-", "")}</div>
      <div className="mt-2 flex flex-wrap gap-1.5">{claim.vulnerability_flag && <span className="rounded-full bg-purple-100 px-2 py-0.5 text-[10px] font-semibold text-purple-700 dark:bg-purple-950 dark:text-purple-300">vulnerable customer</span>}<span className="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-medium text-blue-700 dark:bg-blue-950 dark:text-blue-300">recoverable {money(claim.recoverable_gbp)}</span></div>
      <div data-testid={`claim-outcome-${claim.id}`} className={`mt-3 text-xs font-medium ${tone}`}>{outcome}</div>
    </button>
  );
}
function StatusChip({ label, status, onClick }: { label: string; status: string; onClick: () => void }) {
  const hot = status === "frozen" || status === "under_review";
  return <button type="button" onClick={onClick} className={`rounded-full border px-2 py-1 text-[10px] font-mono ${hot ? "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300" : "border-slate-200 bg-slate-50 text-slate-500 dark:border-slate-800 dark:bg-slate-950"}`}>{label} · {status}</button>;
}
function ExposureList({ exposures, limits, counterparties, onActor }: { exposures: Exposure[]; limits: CreditLimit[]; counterparties: Counterparty[]; onActor: (id: string) => void }) {
  const limitById = new Map(limits.map((limit) => [limit.id, limit]));
  const counterpartyById = new Map(counterparties.map((c) => [c.id, c]));
  const rows = exposures.map((exposure) => { const limit = exposure.limit_id ? limitById.get(exposure.limit_id) : limits.find((item) => item.counterparty_id === exposure.counterparty_id); const limitGbp = limit?.limit_gbp ?? 1; return { exposure, limitGbp, utilisation: (exposure.current_gbp ?? 0) / limitGbp, counterparty: counterpartyById.get(exposure.counterparty_id) }; }).sort((a, b) => b.utilisation - a.utilisation).slice(0, EXPOSURE_CAP);
  return <div className="space-y-2">{rows.map(({ exposure, limitGbp, utilisation, counterparty }) => <button key={exposure.id} type="button" onClick={() => onActor(exposure.id)} className="w-full rounded-lg border border-slate-100 bg-slate-50 px-2 py-2 text-left dark:border-slate-800 dark:bg-slate-950/50"><div className="flex items-center justify-between gap-2 text-xs"><span className="min-w-0 truncate font-mono font-semibold">{counterparty?.display_name ?? exposure.counterparty_id}</span><span className={`shrink-0 tabular-nums ${utilisation > 1 ? "text-red-600 dark:text-red-400" : utilisation > .8 ? "text-amber-600 dark:text-amber-400" : "text-slate-500"}`}>{pct(utilisation)}</span></div><div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800"><div className={`h-full ${utilisation > 1 ? "bg-red-500" : utilisation > .8 ? "bg-amber-500" : "bg-emerald-500"}`} style={{ width: `${Math.min(100, Math.max(3, utilisation * 100))}%` }} /></div><div className="mt-1 flex justify-between text-[11px] tabular-nums text-slate-500"><span>{money(exposure.current_gbp, true)}</span><span>limit {money(limitGbp, true)}</span></div></button>)}</div>;
}
function PositionList({ positions, counterparties, onActor }: { positions: Position[]; counterparties: Counterparty[]; onActor: (id: string) => void }) {
  const counterpartyById = new Map(counterparties.map((c) => [c.id, c]));
  return <div className="grid gap-2 sm:grid-cols-2">{positions.slice(0, POSITION_CAP).map((position) => { const mtm = position.mark_to_market_gbp ?? 0; return <button key={position.id} type="button" onClick={() => onActor(position.id)} className="rounded-lg border border-slate-100 bg-slate-50 px-2 py-2 text-left dark:border-slate-800 dark:bg-slate-950/50"><div className="flex items-center justify-between gap-2"><span className="font-mono text-xs font-semibold">{position.id}</span><span className={`text-sm font-semibold tabular-nums ${mtm >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"}`}>{money(mtm, true)}</span></div><div className="mt-1 text-[11px] text-slate-500">{position.instrument} · {counterpartyById.get(position.counterparty_id)?.display_name ?? position.counterparty_id}</div><div className="mt-1 text-[11px] tabular-nums text-slate-500">notional {money(position.notional_gbp, true)}</div></button>; })}</div>;
}
function Journal({ events, selectedActor, functionFilter, showRoutine, loading, onFunctionFilter, onRoutine, onActor, onClear }: { events: WorldEvent[]; selectedActor: string | null; functionFilter: FunctionFilter; showRoutine: boolean; loading: boolean; onFunctionFilter: (f: FunctionFilter) => void; onRoutine: (value: boolean) => void; onActor: (id: string) => void; onClear: () => void }) {
  return <section data-testid="banking-journal" className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900"><div className="flex flex-wrap items-center justify-between gap-2 pb-3"><div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500"><Sparkles size={15} /> Journal {loading && <span className="font-normal normal-case">refreshing…</span>}</div>{selectedActor && <button type="button" onClick={onClear} className="text-[11px] text-blue-600 hover:underline dark:text-blue-400">filtering {selectedActor} · clear</button>}</div><div className="mb-3 flex flex-wrap items-center gap-2">{FUNCTIONS.map((fn) => <button key={fn} type="button" onClick={() => onFunctionFilter(fn)} className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${functionFilter === fn ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"}`}>{fn}</button>)}<button type="button" onClick={() => onRoutine(!showRoutine)} className="rounded-full border border-slate-300 px-2.5 py-1 text-[11px] text-slate-600 dark:border-slate-700 dark:text-slate-300">{showRoutine ? "Hide routine activity" : "Show routine activity"}</button></div><ul className="divide-y divide-slate-100 font-mono text-[11px] dark:divide-slate-800">{events.length === 0 ? <li data-testid="banking-journal-empty" className="py-3 text-slate-400">no non-routine story events in the ring</li> : events.map((event) => <li key={event.seq} data-testid={`banking-event-${event.seq}`} className="flex items-center gap-2 py-1.5"><span className="w-12 shrink-0 tabular-nums text-slate-400">{n(event.sim_time)}m</span><span className="w-56 shrink truncate text-slate-700 dark:text-slate-200">{event.type}</span><span className="hidden w-28 shrink-0 truncate text-slate-400 sm:inline">{eventFunction(event)}</span>{event.actor_id ? <button type="button" onClick={() => onActor(event.actor_id as string)} className="shrink-0 truncate text-slate-600 hover:underline dark:text-slate-300">{event.actor_id}</button> : <span className="text-slate-400">—</span>}{event.target_id && <button type="button" onClick={() => onActor(event.target_id as string)} className="min-w-0 truncate text-slate-400 hover:underline">→ {event.target_id}</button>}</li>)}</ul></section>;
}
