import { ArchitectureDiagram } from "../components/ArchitectureDiagram";

const captions: { label: string; title: string; body: string }[] = [
  {
    label: "01 · The harness",
    title: "Spawn an agent. Tear it down when done.",
    body:
      "Agents are assembled with the right skills and MCP tools, do their work, and are torn down when finished. There are no thousands of standing agents to manage. It is orchestration, not an org chart.",
  },
  {
    label: "02 · Skills",
    title: "Modular units of know-how, governed centrally.",
    body:
      "A skill is a markdown file with a system prompt, a tool allow-list, and a model choice. Adding a skill is not a project. Replacing one does not require redeploying the system.",
  },
  {
    label: "03 · MCPs",
    title: "A federated capability layer over your real systems.",
    body:
      "Workday, Concur, ServiceNow, Greenhouse, Graph — and your third-party APIs — surfaced as MCP tools with negotiated auth, schemas and contracts. The MCP servers are not agentic themselves. They are pure capability. Agents borrow them.",
  },
  {
    label: "04 · Governance",
    title: "Blessed once. Not per project.",
    body:
      "Identity, audit, hooks on non-revocable sends, validators, policy-driven behaviour, cost attribution. The bit legal and risk have to bless once. The same spine carries every domain that follows.",
  },
];

export function Argument() {
  return (
    <section className="section">
      <div className="column--wide stack-xl">
        <header className="argument__intro stack">
          <p className="subtitle">The architecture</p>
          <h2 className="section-title">
            What ought to exist instead — <em>the four pieces, and the spine they share.</em>
          </h2>
          <p className="body">
            None of the four pieces are interesting on their own. Together they
            make a working environment that runs in your cloud. The harness
            sits on top. Skills and MCPs and the systems they reach are stacked
            beneath it. Identity and governance run down the side.
          </p>
        </header>

        <div className="arch__frame">
          <ArchitectureDiagram />
        </div>

        <ol className="argument__list">
          {captions.map((item) => (
            <li key={item.label} className="argument__item">
              <div className="argument__item-label">{item.label}</div>
              <div className="argument__item-body">
                <h3 className="argument__item-title">{item.title}</h3>
                <p className="body">{item.body}</p>
              </div>
            </li>
          ))}
          <li className="argument__item">
            <div className="argument__item-label">05 · The mechanism</div>
            <div className="argument__item-body">
              <h3 className="argument__item-title">Composition, not construction.</h3>
              <p className="body">
                The cost of the next domain collapses because the alphabet is
                already cast. Each new domain is a new orchestrator class plus
                a small number of new skills, composed against the same MCPs,
                identity and governance that were blessed for the first one.
                Operators do not need retraining per agent.
              </p>
            </div>
          </li>
        </ol>
      </div>
    </section>
  );
}
