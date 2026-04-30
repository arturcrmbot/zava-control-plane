from __future__ import annotations
from api.shared.types import (
    Workflow, Phase, OtelSpan, Exception_ as Exception, ActionLedgerEntry,
    AutonomyPolicy, SkillAmplification, McpCall
)


class StateStore:
    def __init__(self) -> None:
        self._workflows: dict[str, Workflow] = {}
        self._phases: dict[str, list[Phase]] = {}
        self._spans: dict[str, list[OtelSpan]] = {}
        self._exceptions: dict[str, Exception] = {}
        self._policies: dict[str, AutonomyPolicy] = {}
        self._amplifications: dict[str, list[SkillAmplification]] = {}
        self._mcp_calls: dict[str, list[McpCall]] = {}

    def upsert_workflow(self, w: Workflow) -> None:
        self._workflows[w.id] = w

    def get_workflow(self, id: str) -> Workflow | None:
        return self._workflows.get(id)

    def list_workflows(
        self,
        status: str | None = None,
        phase: str | None = None,
        agency: str | None = None,
        has_exception: bool | None = None,
    ) -> list[Workflow]:
        out = []
        for w in self._workflows.values():
            if status is not None and w.status != status: continue
            if phase is not None and w.current_phase != phase: continue
            if agency is not None and w.agency != agency: continue
            if has_exception is not None:
                if has_exception != bool(w.active_exception_id): continue
            out.append(w)
        return out

    def append_phase(self, workflow_id: str, p: Phase) -> None:
        self._phases.setdefault(workflow_id, []).append(p)

    def update_phase(self, workflow_id: str, name: str, **patch) -> None:
        for p in self._phases.get(workflow_id, []):
            if p.name == name:
                for k, v in patch.items():
                    setattr(p, k, v)
                return

    def get_phases(self, workflow_id: str) -> list[Phase]:
        return self._phases.get(workflow_id, [])

    def append_span(self, s: OtelSpan) -> None:
        wid = s.attributes.get("workflow.id")
        if wid:
            self._spans.setdefault(wid, []).append(s)

    def get_spans(self, workflow_id: str) -> list[OtelSpan]:
        return self._spans.get(workflow_id, [])

    def append_mcp_call(self, c: McpCall) -> None:
        self._mcp_calls.setdefault(c.workflow_id, []).append(c)

    def get_mcp_calls(self, workflow_id: str) -> list[McpCall]:
        return self._mcp_calls.get(workflow_id, [])

    def upsert_exception(self, e: Exception) -> None:
        self._exceptions[e.id] = e
        w = self._workflows.get(e.workflow_id)
        if w and not e.resolved_at:
            w.active_exception_id = e.id

    def get_exception(self, id: str) -> Exception | None:
        return self._exceptions.get(id)

    def list_exceptions(self, include_resolved: bool = False) -> list[Exception]:
        return [e for e in self._exceptions.values() if include_resolved or not e.resolved_at]

    def resolve_exception(self, id: str, resolved_by: str) -> None:
        import time as _time
        e = self._exceptions.get(id)
        if not e: return
        e.resolved_at = _time.time()
        e.resolved_by = resolved_by
        w = self._workflows.get(e.workflow_id)
        if w and w.active_exception_id == id:
            w.active_exception_id = None

    def append_ledger(self, workflow_id: str, entry: ActionLedgerEntry) -> None:
        w = self._workflows.get(workflow_id)
        if w:
            w.action_ledger.append(entry)

    def upsert_policy(self, p: AutonomyPolicy) -> None:
        self._policies[p.id] = p

    def list_policies(self) -> list[AutonomyPolicy]:
        return list(self._policies.values())

    def append_amplification(self, workflow_id: str, a: SkillAmplification) -> None:
        self._amplifications.setdefault(workflow_id, []).append(a)

    def get_amplifications(self, workflow_id: str) -> list[SkillAmplification]:
        return self._amplifications.get(workflow_id, [])

    def append_agent_output(self, workflow_id: str, agent: str, output: dict) -> None:
        """POC2 §4.21 AG-UI: lift a structured agent output onto the
        workflow's `agent_outputs` map so the Control Plane can render any
        `component_spec` entries in WorkflowDetail.

        No-op if the workflow is unknown — agent outputs without a workflow
        record have nowhere to land. The map is keyed by agent name (last
        write wins per agent; downstream re-runs replace earlier outputs).
        """
        w = self._workflows.get(workflow_id)
        if w is None:
            return
        w.agent_outputs[agent] = output

    def get_agent_outputs(self, workflow_id: str) -> dict:
        w = self._workflows.get(workflow_id)
        return dict(w.agent_outputs) if w else {}
