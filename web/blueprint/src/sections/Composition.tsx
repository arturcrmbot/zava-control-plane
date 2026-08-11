import { useComposition } from "../lib/useComposition";
import { CompositionMap } from "../components/CompositionMap";

export function Composition() {
  const { data } = useComposition();

  return (
    <section className="section composition">
      <div className="column--wide stack-lg">
        <header className="stack">
          <p className="subtitle">A working reference implementation</p>
          <h2 className="section-title">
            An agentic organisation you can inspect while it runs.
          </h2>
          <p className="body">
            The {data.vertical.display_name} organisation is the current
            proven reference. Each active vertical composes specialised
            skills, shared MCP adapters, durable workflows, personae,
            governance and observability through one control plane. The
            code is executable: organisational records and external systems
            are synthetic so the reference runs without a customer estate
            behind it.
          </p>
          <p className="body">
            The point is not that every decision should be delegated. It is
            that bounded capabilities working together — agents, humans,
            approvals, policy, memory — can be proven at this scope before
            you connect them to your own systems.
          </p>
          <p className="body">
            Tap or hover any tile to see what each workflow composes.
          </p>
        </header>

        <CompositionMap data={data} />

        <p className="body">
          A workflow&apos;s phases don&apos;t each get their own agent.
          Adjacent phases that share an approval boundary collapse into a
          single segment, so a ten-phase workflow might run as six
          segments with a human checkpoint between them. Inside a segment
          the model decides which skill to call next; the orchestrator
          decides segment order, approval gates and retries.
        </p>
      </div>
    </section>
  );
}
