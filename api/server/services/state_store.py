from __future__ import annotations
from api.shared.types import (
    Workflow, Phase, OtelSpan, Exception_ as Exception, ActionLedgerEntry,
    AutonomyPolicy, SkillAmplification, McpCall
)
from api.server.services.replay.mutation_bus import emit_mutation


class StateStore:
    def __init__(self) -> None:
        self._workflows: dict[str, Workflow] = {}
        self._phases: dict[str, list[Phase]] = {}
        self._spans: dict[str, list[OtelSpan]] = {}
        self._exceptions: dict[str, Exception] = {}
        self._policies: dict[str, AutonomyPolicy] = {}
        self._amplifications: dict[str, list[SkillAmplification]] = {}
        self._mcp_calls: dict[str, list[McpCall]] = {}
        # Candidate-portal state — keyed by candidate_id ("C-XXXXXXXX"). Each
        # entry stashes the dict that the /apply route built (id, name, email,
        # cv_url, role_id), plus a `workflow_id` once attach_candidate_to_role
        # binds it to a HiringOrchestrator workflow, plus an optional
        # `voice_transcript` list once the screening voice agent emits turns.
        self._candidates: dict[str, dict] = {}
        # Reverse index for attach: role_id -> first matching workflow_id.
        # Multiple workflows per role_id are allowed; last-seeded wins.
        self._role_index: dict[str, str] = {}

    def upsert_workflow(self, w: Workflow) -> None:
        self._workflows[w.id] = w
        # Maintain the role_id -> workflow_id reverse index so the candidate
        # portal's /apply route can attach a candidate to the matching seeded
        # HiringOrchestrator workflow without scanning every workflow each call.
        role_id = (w.metadata or {}).get("role_id") if hasattr(w, "metadata") else None
        if role_id:
            self._role_index[role_id] = w.id
        emit_mutation(
            op="upsert",
            kind="workflow",
            id=w.id,
            patch=w.model_dump(by_alias=True, mode="json"),
        )

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
        emit_mutation(
            op="upsert",
            kind="exception",
            id=e.id,
            patch=e.model_dump(by_alias=True, mode="json"),
        )

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

    def append_agent_reasoning(self, workflow_id: str, entry: dict) -> None:
        """Persist one agent.completed reasoning entry on the workflow.

        Each entry should carry the canonical wrapper shape — `agent_label`,
        `phase` (when known), `started_at`, `completed_at`, `messages` (full
        chat-completion message stream), `tool_calls` (input/output of each
        tool the agent invoked), `extracted_json` (the structured output the
        agent produced), `latency_ms`, `tokens_in`/`tokens_out`. Surfaces in
        the admin Traces tab and any domain view (recruiter candidate page,
        reviewer queue, …) so we always know what the AI thought, not just
        that it ran.

        Append-only: re-runs of the same agent on the same workflow each get
        their own entry. Last entry per agent_label is the authoritative
        verdict for downstream UI. No-op if the workflow is unknown.
        """
        w = self._workflows.get(workflow_id)
        if w is None:
            return
        if not hasattr(w, "agent_reasoning") or w.agent_reasoning is None:
            try:
                w.agent_reasoning = []
            except Exception:
                # Pydantic immutable field — fall back to dict-style mutation
                # via the model's __dict__. Workflow uses arbitrary types
                # in tests so this is the conservative path.
                w.__dict__["agent_reasoning"] = []
        w.agent_reasoning.append(entry)

    def get_agent_reasoning(self, workflow_id: str) -> list[dict]:
        w = self._workflows.get(workflow_id)
        if w is None:
            return []
        return list(getattr(w, "agent_reasoning", None) or [])

    # ----------------------------------------------------------------- candidates
    # Candidate-portal surface (POC2 §4 demo-ready scope). Candidates submit
    # an application via the public /api/portal/apply route; we persist their
    # dict here and bind them to an existing HiringOrchestrator workflow keyed
    # by role_id. The workflow's `metadata.candidate_id` is updated so the
    # downstream Triage / Screening phases find the right CV.

    def attach_candidate_to_role(
        self, role_id: str, candidate: dict
    ) -> str | None:
        """Bind a freshly-submitted candidate to the seeded workflow for `role_id`.

        Returns the workflow_id we attached to, or None if no workflow exists
        for this role yet (the /apply route turns that into a 404).
        """
        workflow_id = self._role_index.get(role_id)
        if workflow_id is None:
            return None
        w = self._workflows.get(workflow_id)
        if w is None:
            # Stale index pointing at a removed workflow — drop the entry so
            # subsequent calls don't keep hitting the same dead row.
            self._role_index.pop(role_id, None)
            return None
        # Copy the candidate dict so caller mutations don't leak into our store
        record = dict(candidate)
        record["workflow_id"] = workflow_id
        record.setdefault("role_id", role_id)
        record["instance_id"] = w.orchestration_instance_id
        self._candidates[record["id"]] = record
        # Reflect onto the workflow metadata so the agent layer (cv_crystalliser
        # et al.) can pick up the candidate id without a separate lookup.
        w.metadata = dict(w.metadata or {})
        w.metadata["candidate_id"] = record["id"]
        w.metadata["candidate_name"] = record.get("name")
        w.metadata["candidate_email"] = record.get("email")
        w.metadata["cv_url"] = record.get("cv_url")
        return workflow_id

    def get_candidate(self, candidate_id: str) -> dict | None:
        rec = self._candidates.get(candidate_id)
        return dict(rec) if rec else None

    def upsert_candidate(self, candidate: dict) -> None:
        """Replace the stored candidate record with a copy of `candidate`.
        Used by portal_orchestration to write back the durable instance_id
        once the HiringOrchestrator is spawned."""
        cid = candidate.get("id")
        if not cid:
            return
        self._candidates[cid] = dict(candidate)

    def list_candidates(self) -> list[dict]:
        return [dict(r) for r in self._candidates.values()]

    def append_voice_transcript(self, candidate_id: str, turn: dict) -> None:
        """Append a single voice-screening transcript turn onto the candidate
        record so the portal /status page can replay the conversation. No-op
        if the candidate is unknown — voice turns without an applicant record
        have nowhere to land."""
        rec = self._candidates.get(candidate_id)
        if rec is None:
            return
        rec.setdefault("voice_transcript", []).append(dict(turn))
