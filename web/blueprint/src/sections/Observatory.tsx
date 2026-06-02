import { useComposition } from "../lib/useComposition";
import { useReplayObservatory } from "../lib/useReplayObservatory";
import { getDemoUrl } from "../lib/useDemoUrl";
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

        <p className="body">
          The visualisation above is one panel of the control plane,
          embedded into this essay. The complete application is a web
          interface for operating the substrate, with dashboards for
          entities and accounts, a constellation view that maps every
          workflow domain, and a detail page for each workflow run that
          lets you open the reasoning of each agent as it executed. It is
          deployed to Azure Container Apps and the URL is open to
          visitors.
        </p>

        <p className="body">
          When you open it, you see the same recording that drives the
          visualisation on this page, presented through the full operator
          interface. You can navigate between pages, select a workflow to
          inspect its events in sequence, and open the side drawer to
          read each agent&apos;s reasoning. The system behaves the way it
          did when the workflows originally ran. Refreshing the page
          restarts the replay from the beginning of the recording.
        </p>

        <p className="body observatory__note">
          The link below opens the operator dashboard in a new tab — give
          it a few seconds to populate, then drill into any workflow row.
        </p>

        <p className="body">
          <a
            className="observatory__cta"
            href={getDemoUrl("observatory")}
            target="_blank"
            rel="noopener noreferrer"
          >
            Open the replay →
          </a>
        </p>
      </div>
    </section>
  );
}


