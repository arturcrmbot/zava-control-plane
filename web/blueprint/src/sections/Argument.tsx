
const captions: { label: string; title: string; body: string }[] = [
  {
    label: "01 · The harness",
    title: "Agents are spawned for a piece of work and torn down when it's finished.",
    body:
      "Agents are assembled with the right skills and MCP tools, do their work, and are torn down when finished. There are no thousands of standing agents to manage. It looks more like orchestration than an organisational structure.",
  },
  {
    label: "02 · Skills",
    title: "Modular units of know-how, governed centrally.",
    body:
      "A skill is a markdown file with a system prompt, a tool allow-list, and a model choice. Adding or replacing a skill is a small change to a single file rather than a redeployment of the system.",
  },
  {
    label: "03 · MCPs",
    title: "One adapter per system, shared across every agent.",
    body:
      "Workday HR, Concur travel, the policy and audit ledger, the delegated-authority matrix, identity and calendar services, document intelligence, and third-party sources like contract repositories, market pricing, vendor and sanctions screening, all surfaced as MCP tools with negotiated auth, schemas and contracts. The MCP servers are not agents themselves; they expose capability that agents borrow when they need it.",
  },
  {
    label: "04 · The foundation",
    title: "Identity, validation, audit and policy, built into the substrate once.",
    body:
      "Each agent runs under its own identity. A validator checks every output before it leaves the system, and every step is written to an immutable audit ledger. Policy lives in YAML rather than code, which means compliance can edit the rules directly. Once these pieces are in the substrate, every domain built on top of it inherits them.",
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
            domain you put on top inherits all of it for free. This is what
            makes the cost of the next domain drop sharply. It isn&apos;t any
            single piece; it&apos;s the four of them operating together as one
            ground layer.
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
          The result is that new work is composed from existing parts rather
          than constructed from scratch. Each new domain is a new
          orchestrator class plus a small number of new skills, composed
          against the same MCPs, identity and governance that were built for
          the first one. Operators don&apos;t need separate training for each
          new agent because they&apos;re all running on the same substrate.
        </p>
      </div>
    </section>
  );
}
