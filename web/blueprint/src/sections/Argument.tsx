
const captions: { label: string; title: string; body: string }[] = [
  {
    label: "01 · The harness",
    title: "Agentic segments inside deterministic workflows.",
    body:
      "A workflow is a sequence of segments. Each segment opens one short-lived agent session with a bounded set of skills and MCP tools, runs to a checkpoint, and closes. The segment boundaries, the order of segments, the human approval gates and the retry rules all live in orchestrator code that the model never sees. The model picks the next tool inside a segment; the orchestrator picks everything else.",
  },
  {
    label: "02 · Skills",
    title: "Modular units of know-how, governed in one place.",
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
      "Each skill runs under its own agent identity: a stable agent id and a per-skill Ed25519 signing key the substrate issues itself. Every MCP tool call is gated by an allow-list (the AGT capability set) checked at call time by a pre-tool hook, and denials surface to the model as a tool error. After each segment, a paired validator activity Pydantic-checks the output before the workflow moves on. Every step, including AGT denials, is written to an audit ledger signed with the calling skill's key. Policy lives in YAML so compliance can edit the rules directly. To be honest about what this is: there is no Entra Agent ID and no per-skill Entra identity in this substrate today; the identity, the signing key and the allow-list are all issued and enforced inside the substrate itself.",
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
