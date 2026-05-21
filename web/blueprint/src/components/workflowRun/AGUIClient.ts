import type { BaseEvent } from "@ag-ui/core";

export interface RunSubscription {
  done: Promise<void>;
  cancel(): void;
}

interface ConnectOpts {
  /** Override for testing — supply a fake that calls onEvent directly. */
  agentFactory?: (runId: string) => { runAgent: (opts: any) => Promise<void> };
  baseUrl?: string;
}

/**
 * Connect to the AG-UI SSE stream for a workflow run.
 *
 * In production, opens a native EventSource against
 * `/api/workflows/{runId}/agui`. The backend emits SSE frames with
 * `data: {json}` payloads that are parsed and forwarded to `onEvent`.
 *
 * For tests, pass `agentFactory` to inject a fake.
 */
export function connectWorkflowRun(
  runId: string,
  onEvent: (event: BaseEvent) => void,
  opts: ConnectOpts = {},
): RunSubscription {
  // Test path — allow injection of a fake agent.
  if (opts.agentFactory) {
    const agent = opts.agentFactory(runId);
    const done = agent.runAgent({ threadId: runId, onEvent });
    return { done, cancel: () => {} };
  }

  // Production path — native EventSource (GET-based SSE).
  const base = opts.baseUrl ?? "";
  const url = `${base}/api/workflows/${runId}/agui`;
  const es = new EventSource(url);
  let resolveDone: () => void;
  const done = new Promise<void>((resolve) => { resolveDone = resolve; });

  es.onmessage = (msg) => {
    try {
      const ev = JSON.parse(msg.data) as BaseEvent;
      onEvent(ev);
      if (ev.type === "RUN_FINISHED" || ev.type === "RUN_ERROR") {
        es.close();
        resolveDone();
      }
    } catch { /* skip unparseable frames */ }
  };

  es.onerror = () => {
    // EventSource auto-reconnects; close only if readyState is CLOSED.
    if (es.readyState === EventSource.CLOSED) {
      resolveDone();
    }
  };

  return { done, cancel: () => { es.close(); resolveDone(); } };
}
