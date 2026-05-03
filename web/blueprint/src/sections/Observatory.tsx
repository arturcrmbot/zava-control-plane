import { useObservatory } from "../lib/useObservatory";
import { useDemoStream } from "../lib/useDemoStream";
import { useComposition } from "../lib/useComposition";
import { MindMap } from "../components/MindMap";
import type { ObservatoryEvent } from "../lib/types";

function fmtTime(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toTimeString().slice(0, 8);
}

function detail(e: ObservatoryEvent): string {
  const parts: string[] = [];
  if (e.skill) parts.push(e.skill);
  if (e.tool) parts.push(`→ ${e.tool}`);
  if (e.domain) parts.push(`· ${e.domain}`);
  if (e.workflow_id) parts.push(`(${e.workflow_id})`);
  return parts.join(" ");
}

function isValidatorEvent(t: string): boolean {
  return t === "durable.validator.blocked";
}

export function Observatory() {
  const { events, counters, status } = useObservatory({ bufferSize: 60 });
  const { data: composition } = useComposition();
  const { running, pending, start, stop } = useDemoStream();

  const statusLabel =
    status === "watching"
      ? "watching"
      : status === "connecting"
      ? "connecting"
      : "offline · backend not running";

  const buttonLabel = pending
    ? running
      ? "stopping…"
      : "starting…"
    : running
    ? "Stop the demo"
    : "Wake the observatory";

  return (
    <section className="section observatory">
      <div className="column--wide stack-lg">
        <header className="observatory__header">
          <div className="stack">
            <p className="subtitle">The observatory</p>
            <h2 className="section-title">
              <em>And here is what is happening, right now.</em>
            </h2>
          </div>
          <div className="observatory__header-right">
            <button
              type="button"
              className={`observatory__button${running ? " observatory__button--running" : ""}`}
              onClick={running ? stop : start}
              disabled={pending || status === "offline"}
            >
              {buttonLabel}
            </button>
            <div className={`observatory__status observatory__status--${status}`}>
              {statusLabel}
            </div>
          </div>
        </header>

        <p className="body">
          Each workflow lights up the map below. The active domain sits at the
          centre. Phases orbit it; skills bloom around the active phase as
          agents pick them up; calls travel out to the MCP tools on the rim.
          When a validator blocks, the line turns red. When nothing&apos;s
          firing, the map falls quiet.
        </p>

        <div className="observatory__counters">
          <div className="counter">
            <div className="counter__value">{counters.workflowsStarted}</div>
            <div className="counter__label">Workflows started</div>
          </div>
          <div className="counter">
            <div className="counter__value">{counters.agentInvocations}</div>
            <div className="counter__label">Agent invocations</div>
          </div>
          <div className="counter">
            <div className="counter__value">{counters.toolCalls}</div>
            <div className="counter__label">Tool calls</div>
          </div>
          <div className="counter">
            <div className="counter__value">{counters.validatorsBlocked}</div>
            <div className="counter__label">Validators blocked</div>
          </div>
          <div className="counter">
            <div className="counter__value">{counters.workflowsCompleted}</div>
            <div className="counter__label">Workflows completed</div>
          </div>
        </div>

        <div className="mindmap__frame">
          <MindMap events={events} status={status} composition={composition} />
        </div>

        <div className="feed">
          {events.length === 0 ? (
            <div className="feed__empty">
              {status === "offline"
                ? "no signal"
                : "no events yet — wake the observatory above"}
            </div>
          ) : (
            events.slice(0, 18).map((e, i) => (
              <div className="feed__row" key={`${e.ts}-${i}`}>
                <span className="feed__time">{fmtTime(e.ts)}</span>
                <span>
                  <span
                    className={`feed__type${
                      isValidatorEvent(e.type) ? " feed__type--validator" : ""
                    }`}
                  >
                    {e.type}
                  </span>
                  <span className="feed__detail"> {detail(e)}</span>
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </section>
  );
}
