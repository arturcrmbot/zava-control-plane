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
    return () => sub.cancel();
  }, [runId]);

  if (!runId) {
    return <div className="run-page run-page--empty">
      Missing <code>run_id</code> query parameter.
    </div>;
  }
  return <div className="run-page"><RunPanel runId={runId} state={state} /></div>;
}
