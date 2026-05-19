import { useComposition } from "../lib/useComposition";
import { useReplayObservatory } from "../lib/useReplayObservatory";
import { MindMap } from "../components/MindMap";

export function Observatory() {
  const { data: composition } = useComposition();
  const { events, counters, status } = useReplayObservatory();

  return (
    <section className="section observatory">
      <div className="column--wide stack-lg">
        <header className="observatory__header">
          <div className="stack">
            <p className="subtitle">The observatory</p>
            <h2 className="section-title">
              And here is what it looks like when it runs.
            </h2>
          </div>
        </header>

        <p className="body observatory__note">
          What you&apos;re watching is real telemetry. Workflows ran on my
          laptop against the same orchestrator, skills and MCP tools
          described above. Every event was captured. We&apos;re replaying
          the recording on this page so it reads continuously instead of
          waiting for live traffic. The events and their timing are the
          original ones, and none of it is animation.
        </p>

        <p className="body">
          Each workflow lights up the map. The active domain sits at the
          centre, phases around it, skills picked up by agents as they go,
          calls travelling out to the MCP tools on the rim. A validator
          block shows red.
        </p>

        <div className="observatory__counters">
          <div className="counter">
            <div className="counter__value">{counters.workflowsStarted}</div>
            <div className="counter__label">Workflows started</div>
          </div>
          <div className="counter">
            <div className="counter__value">{counters.skillsInvoked}</div>
            <div className="counter__label">Skills run</div>
          </div>
          <div className="counter">
            <div className="counter__value">{counters.toolCalls}</div>
            <div className="counter__label">MCP tool calls</div>
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
      </div>
    </section>
  );
}


