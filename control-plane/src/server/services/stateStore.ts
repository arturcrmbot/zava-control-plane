import type {
  Workflow, Phase, OtelSpan, Exception, ActionLedgerEntry,
  AutonomyPolicy, SkillAmplification
} from "@shared/types";

export interface WorkflowFilters {
  status?: Workflow["status"];
  phase?: Workflow["currentPhase"];
  agency?: string;
  hasException?: boolean;
}

export class StateStore {
  private workflows = new Map<string, Workflow>();
  private phases = new Map<string, Phase[]>();
  private spans = new Map<string, OtelSpan[]>();
  private exceptions = new Map<string, Exception>();
  private policies = new Map<string, AutonomyPolicy>();
  private amplifications = new Map<string, SkillAmplification[]>();

  upsertWorkflow(w: Workflow): void { this.workflows.set(w.id, w); }
  getWorkflow(id: string): Workflow | undefined { return this.workflows.get(id); }
  listWorkflows(f: WorkflowFilters = {}): Workflow[] {
    return [...this.workflows.values()].filter(w =>
      (f.status == null || w.status === f.status) &&
      (f.phase == null || w.currentPhase === f.phase) &&
      (f.agency == null || w.agency === f.agency) &&
      (f.hasException == null || (f.hasException === !!w.activeExceptionId))
    );
  }

  appendPhase(workflowId: string, p: Phase): void {
    const list = this.phases.get(workflowId) ?? [];
    list.push(p); this.phases.set(workflowId, list);
  }
  updatePhase(workflowId: string, name: Phase["name"], patch: Partial<Phase>): void {
    const list = this.phases.get(workflowId) ?? [];
    const i = list.findIndex(p => p.name === name);
    if (i >= 0) list[i] = { ...list[i], ...patch };
  }
  getPhases(workflowId: string): Phase[] { return this.phases.get(workflowId) ?? []; }

  appendSpan(s: OtelSpan): void {
    const key = s.attributes["workflow.id"];
    const list = this.spans.get(key) ?? [];
    list.push(s); this.spans.set(key, list);
  }
  getSpans(workflowId: string): OtelSpan[] { return this.spans.get(workflowId) ?? []; }

  upsertException(e: Exception): void {
    this.exceptions.set(e.id, e);
    const w = this.workflows.get(e.workflowId);
    if (w && !e.resolvedAt) w.activeExceptionId = e.id;
  }
  getException(id: string): Exception | undefined { return this.exceptions.get(id); }
  listExceptions(opts: { includeResolved?: boolean } = {}): Exception[] {
    return [...this.exceptions.values()].filter(e => opts.includeResolved || !e.resolvedAt);
  }
  resolveException(id: string, resolvedBy: string): void {
    const e = this.exceptions.get(id);
    if (!e) return;
    e.resolvedAt = Date.now();
    e.resolvedBy = resolvedBy;
    const w = this.workflows.get(e.workflowId);
    if (w && w.activeExceptionId === id) w.activeExceptionId = undefined;
  }

  appendLedger(workflowId: string, entry: ActionLedgerEntry): void {
    const w = this.workflows.get(workflowId);
    if (w) w.actionLedger.push(entry);
  }

  upsertPolicy(p: AutonomyPolicy): void { this.policies.set(p.id, p); }
  listPolicies(): AutonomyPolicy[] { return [...this.policies.values()]; }

  appendAmplification(workflowId: string, a: SkillAmplification): void {
    const list = this.amplifications.get(workflowId) ?? [];
    list.push(a); this.amplifications.set(workflowId, list);
  }
  getAmplifications(workflowId: string): SkillAmplification[] {
    return this.amplifications.get(workflowId) ?? [];
  }
}
