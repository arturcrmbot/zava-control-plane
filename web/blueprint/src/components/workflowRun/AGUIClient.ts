import { HttpAgent } from "@ag-ui/client";
import type { BaseEvent } from "@ag-ui/core";

export interface RunSubscription {
  done: Promise<void>;
  cancel(): void;
}

interface ConnectOpts {
  agentFactory?: (runId: string) => { runAgent: HttpAgent["runAgent"] };
  baseUrl?: string;
}

export function connectWorkflowRun(
  runId: string,
  onEvent: (event: BaseEvent) => void,
  opts: ConnectOpts = {},
): RunSubscription {
  const base = opts.baseUrl ?? "";
  const factory =
    opts.agentFactory ??
    ((id: string) =>
      new HttpAgent({ url: `${base}/api/workflows/${id}/agui` }));
  const agent = factory(runId);
  const abortController = new AbortController();

  const subscriber = {
    onEvent: ({ event }: { event: BaseEvent }) => onEvent(event),
  };

  const done = (async () => {
    try {
      await agent.runAgent(
        {
          runId,
          threadId: runId,
          abortController,
          onEvent,
          signal: abortController.signal,
        } as any,
        subscriber as any,
      );
    } catch (err) {
      if (!(err instanceof DOMException && err.name === "AbortError")) {
        throw err;
      }
    }
  })();

  return { done, cancel: () => abortController.abort() };
}
