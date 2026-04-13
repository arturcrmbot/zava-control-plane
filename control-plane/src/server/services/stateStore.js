export class StateStore {
    workflows = new Map();
    phases = new Map();
    spans = new Map();
    exceptions = new Map();
    policies = new Map();
    amplifications = new Map();
    upsertWorkflow(w) { this.workflows.set(w.id, w); }
    getWorkflow(id) { return this.workflows.get(id); }
    listWorkflows(f = {}) {
        return [...this.workflows.values()].filter(w => (f.status == null || w.status === f.status) &&
            (f.phase == null || w.currentPhase === f.phase) &&
            (f.agency == null || w.agency === f.agency) &&
            (f.hasException == null || (f.hasException === !!w.activeExceptionId)));
    }
    appendPhase(workflowId, p) {
        const list = this.phases.get(workflowId) ?? [];
        list.push(p);
        this.phases.set(workflowId, list);
    }
    updatePhase(workflowId, name, patch) {
        const list = this.phases.get(workflowId) ?? [];
        const i = list.findIndex(p => p.name === name);
        if (i >= 0)
            list[i] = { ...list[i], ...patch };
    }
    getPhases(workflowId) { return this.phases.get(workflowId) ?? []; }
    appendSpan(s) {
        const key = s.attributes["workflow.id"];
        const list = this.spans.get(key) ?? [];
        list.push(s);
        this.spans.set(key, list);
    }
    getSpans(workflowId) { return this.spans.get(workflowId) ?? []; }
    upsertException(e) {
        this.exceptions.set(e.id, e);
        const w = this.workflows.get(e.workflowId);
        if (w && !e.resolvedAt)
            w.activeExceptionId = e.id;
    }
    getException(id) { return this.exceptions.get(id); }
    listExceptions(opts = {}) {
        return [...this.exceptions.values()].filter(e => opts.includeResolved || !e.resolvedAt);
    }
    resolveException(id, resolvedBy) {
        const e = this.exceptions.get(id);
        if (!e)
            return;
        e.resolvedAt = Date.now();
        e.resolvedBy = resolvedBy;
        const w = this.workflows.get(e.workflowId);
        if (w && w.activeExceptionId === id)
            w.activeExceptionId = undefined;
    }
    appendLedger(workflowId, entry) {
        const w = this.workflows.get(workflowId);
        if (w)
            w.actionLedger.push(entry);
    }
    upsertPolicy(p) { this.policies.set(p.id, p); }
    listPolicies() { return [...this.policies.values()]; }
    appendAmplification(workflowId, a) {
        const list = this.amplifications.get(workflowId) ?? [];
        list.push(a);
        this.amplifications.set(workflowId, list);
    }
    getAmplifications(workflowId) {
        return this.amplifications.get(workflowId) ?? [];
    }
}
