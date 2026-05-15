
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
    title: "One adapter per system. Used by every agent.",
    body:
      "Workday, SAP, Salesforce, Mediaocean, ServiceNow, Greenhouse, Graph, plus your third-party APIs, surfaced as MCP tools with negotiated auth, schemas and contracts. The MCP servers are not agentic themselves. They are pure capability. Agents borrow them.",
  },
  {
    label: "04 · The foundation",
    title: "Identity, validation, audit and policy. Built once.",
    body:
      "Every agent runs under its own identity. Every output is checked by a validator before it leaves. Every step writes itself to an immutable audit ledger. Policy lives in YAML rather than code, so compliance can edit the rules directly. Built into the substrate once, inherited by every domain after.",
  },
];

export function Argument() {
  return (
    <section className="section">
      <div className="column--wide stack-xl">
        <header className="argument__intro stack">
          <p className="subtitle">The architecture</p>
          <h2 className="section-title">
            What you ought to be using instead, and we&apos;ve built it.
          </h2>
          <p className="body">
            None of the four pieces below are revolutionary. Skills are recent.
            MCPs have been around but aren&apos;t widely used yet. The harness
            is the newest piece of the four. Together, and only together, they
            form a substrate.
          </p>
          <p className="body">
            A substrate is the ground layer that every agent runs on. It holds
            the things you don&apos;t want each project to re-invent: who an
            agent is, what it&apos;s allowed to do, where its actions get
            recorded, which policies apply. Build the substrate once and every
            domain you put on top inherits all of it for free. That&apos;s the
            thing that makes the cost of the next domain collapse. Not any one
            piece, but all four operating as a single ground layer.
          </p>
        </header>

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
        </ol>

        <p className="body">
          The mechanism that comes out of all this is composition, not
          construction. The alphabet is already cast. Each new domain is a
          new orchestrator class plus a small number of new skills, composed
          against the same MCPs, identity and governance that were built for
          the first one. Operators do not need retraining per agent.
        </p>
      </div>
    </section>
  );
}
