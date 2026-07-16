import { useComposition } from "../lib/useComposition";
import { CompositionMap } from "../components/CompositionMap";

export function Composition() {
  const { data } = useComposition();
  const liveDomainCount = data.domains.filter((d) => d.status === "live").length;

  return (
    <section className="section composition">
      <div className="column--wide stack-lg">
        <header className="stack">
          <p className="subtitle">What I built, and what it&apos;s for</p>
          <h2 className="section-title">
            A working model of the {data.vertical.display_name} organisation.
          </h2>
          <p className="body">
            I built a reference organisation on top of this substrate so
            the argument above has something concrete underneath it. The
            substrate today contains around {data.counts.skills} small
            specialised skills, {data.counts.mcps} MCP adapters into
            outside systems like Workday HR, Concur travel, a document
            intelligence service and the policy and identity stack, and{" "}
            {liveDomainCount} workflows wired up end-to-end.
          </p>
          <p className="body">
            This is not a proposal that every routine decision in your
            organisation should be made by an agent. The point of the
            model is to prove that the substrate holds at this scope
            and across this many domains. You&apos;ll keep the parts
            that matter to you and leave the rest.
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
