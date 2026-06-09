import { useEffect, useReducer, useMemo } from "react";
import { connectWorkflowRun } from "../components/workflowRun/AGUIClient";
import { RunPanel } from "../components/workflowRun/RunPanel";
import {
  initialRunState,
  applyEvent,
  type RunState,
} from "../components/workflowRun/runReducer";
import type { BaseEvent } from "@ag-ui/core";

function reducer(state: RunState, ev: BaseEvent) {
  return applyEvent(state, ev as any);
}

export function WorkflowRunPage() {
  const runId = useMemo(() => {
    const p = new URLSearchParams(window.location.search);
    return p.get("run_id") ?? "";
  }, []);
  const [state, dispatch] = useReducer(reducer, undefined, initialRunState);

  useEffect(() => {
    if (!runId) return;
    const sub = connectWorkflowRun(runId, (ev) => dispatch(ev));

    // Auto-trigger demo script if a ?demo= param is present.
    const demo = new URLSearchParams(window.location.search).get("demo");
    if (demo) {
      fetch(`/api/blueprint/_demo_emit?script=${demo}&interval_ms=800`, {
        method: "POST",
      }).catch(() => {});
    }

    return () => sub.cancel();
  }, [runId]);

  if (!runId) {
    return (
      <div className="run-page run-page--empty">
        <div className="run-page__empty-card">
          <h2 className="run-page__empty-title">No workflow run selected</h2>
          <p className="run-page__empty-body">
            This view drills into a single in-flight workflow. Pick one from the
            constellation or operator console first — the URL needs a
            <code> ?run_id=…</code> parameter to load.
          </p>
          <div className="run-page__empty-actions">
            <a href="/?view=constellation" className="run-page__empty-link">Open constellation</a>
            <a href="/" className="run-page__empty-link run-page__empty-link--ghost">Back to essay</a>
          </div>
        </div>
      </div>
    );
  }
  return <div className="run-page"><RunPanel runId={runId} state={state} /></div>;
}
