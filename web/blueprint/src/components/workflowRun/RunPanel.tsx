import type { RunState } from "./runReducer";

export interface RunPanelProps {
  runId: string;
  state: RunState;
}

export function RunPanel({ runId, state }: RunPanelProps) {
  return (
    <div className="run-panel" data-testid="run-panel">
      <header className="run-panel__header">
        <h2>Workflow run: {runId}</h2>
        <span
          className={`run-panel__status run-panel__status--${
            state.finished ? "finished" : "live"
          }`}
        >
          {state.finished ? "finished" : "live"}
        </span>
      </header>

      {state.interrupt && (
        <div className="run-panel__interrupt" role="alert">
          Awaiting <strong>{state.interrupt.persona ?? "human"}</strong>:{" "}
          {state.interrupt.reason}
        </div>
      )}

      {state.error && (
        <div className="run-panel__error" role="alert">
          {state.error}
        </div>
      )}

      <section className="run-panel__messages">
        <h3>Reasoning</h3>
        <ul>
          {state.messages.map((m) => (
            <li key={m.id} className={`msg msg--${m.role}`}>
              <span className="msg__role">{m.role}</span>
              <p className="msg__text">{m.text}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="run-panel__tools">
        <h3>Tool calls</h3>
        <ul>
          {state.toolCalls.map((t) => (
            <li
              key={t.id}
              className={`tool tool--${t.closed ? "closed" : "open"}`}
            >
              <span className="tool__name">{t.name}</span>
              {t.args && <code className="tool__args">{t.args}</code>}
            </li>
          ))}
        </ul>
      </section>

      <section className="run-panel__state">
        <h3>State</h3>
        <pre>{JSON.stringify(state.state, null, 2)}</pre>
      </section>
    </div>
  );
}
