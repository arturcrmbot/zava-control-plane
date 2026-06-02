
const captions: { label: string; title: string; body: string }[] = [
  {
    label: "01 · The harness",
    title: "Agentic segments inside deterministic workflows.",
    body:
      "A workflow is a sequence of segments. Each segment opens a short-lived agent session, runs to a checkpoint, and closes. The model picks the next tool inside a segment; the orchestrator picks everything else.",
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
      "The outside systems the workflows depend on — Workday, Concur, the policy and audit ledger, the delegated-authority matrix, identity, document intelligence, and external sources like contract repositories and market pricing — are all surfaced as MCP tools with a shared way of authenticating and a shared shape for their inputs and outputs. Every agent uses the same adapter for the same system.",
  },
  {
    label: "04 · The foundation",
    title: "Identity, validation, audit and policy, built into the substrate once.",
    body:
      "Each agent has its own identity, its own signing key, and an allow-list of tools it's permitted to call. Every tool call is checked against that allow-list before it runs, every output is structurally validated before the workflow continues, and every call gets written to a tamper-evident audit log signed by the calling skill. Policy lives in a YAML file that compliance can edit directly.",
  },
];

export function Argument() {
  return (
    <section className="section">
      <div className="column--wide stack-xl">
        <header className="argument__intro stack">
          <p className="subtitle">The architecture</p>
          <h2 className="section-title">
            What you ought to be using instead.
          </h2>
          <p className="body">
            A substrate is the ground layer every agent runs on: who an agent
            is, what it&apos;s allowed to do, where its actions get recorded,
            which policies apply. Build it once and every domain you put on
            top inherits all of it. That&apos;s what makes the cost of the
            next domain drop sharply.
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
          Identity, audit and policy enforcement for agents is a known
          problem with an open-source reference: Microsoft&apos;s{" "}
          <a
            className="footer__link"
            href="https://github.com/microsoft/agent-governance-toolkit"
            target="_blank"
            rel="noopener noreferrer"
          >
            Agent Governance Toolkit
          </a>{" "}
          covers this ground in production. The substrate here implements
          the same primitives directly so the model in this article stands
          on its own.
        </p>

        <p className="body">
          Each new domain is composed from existing parts: a new orchestrator
          plus a small number of new skills, against the same MCPs, identity
          and governance the first one used.
        </p>
      </div>
    </section>
  );
}
