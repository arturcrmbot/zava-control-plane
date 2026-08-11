
const captions: { label: string; title: string; body: string }[] = [
  {
    label: "01 · Durable control",
    title: "Workflow order, checkpoints, retries and human gates.",
    body:
      "Every domain runs inside a durable workflow: segment order is declared, checkpoints survive infrastructure failures, retries are automatic, and human approval gates pause execution until a person acts. The orchestrator owns all of that; agents own what happens inside a segment.",
  },
  {
    label: "02 · Bounded agent work",
    title: "Short-lived sessions load approved skills and tools.",
    body:
      "A segment opens an agent session with an approved skill and tool list, runs to a checkpoint, and closes. Skills and tools are versioned and released like code. Changes to a skill go through the same review and deployment pipeline as any other code change.",
  },
  {
    label: "03 · Pack-scoped capabilities",
    title: "MCP adapters and typed commands belong to the selected vertical.",
    body:
      "The MCP adapters and command types available to a workflow belong to the active vertical pack. Authorised capabilities are available only to work that the pack's authority rules permit. A different pack selects different adapters and commands.",
  },
  {
    label: "04 · Governance and evidence",
    title: "Proposed calls are evaluated, recorded and configurable.",
    body:
      "Each proposed agent call is evaluated before it runs and written to a tamper-evident audit log. Evaluation workspaces can run in log-only mode — the default in .env.example is AGT_ENFORCE=0, which records denials without blocking them. In enforced mode, denied calls block. Configured validators gate outputs before the workflow continues.",
  },
];

export function Argument() {
  return (
    <section className="section">
      <div className="column--wide stack-xl">
        <header className="argument__intro stack">
          <p className="subtitle">The architecture</p>
          <h2 className="section-title">
            One workforce needs shared operating machinery.
          </h2>
          <p className="body">
            A substrate is the ground layer every agent runs on: who an agent
            is, what it&apos;s allowed to do, where its actions get recorded,
            which policies apply. Build it once and every domain you put on
            top inherits all of it. That&apos;s what makes the cost of the
            next domain drop.
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
          The identity, audit and policy layer uses Microsoft&apos;s
          open-source{" "}
          <a
            className="footer__link"
            href="https://github.com/microsoft/agent-governance-toolkit"
            target="_blank"
            rel="noopener noreferrer"
          >
            Agent Governance Toolkit
          </a>
          , wired in as the substrate&apos;s governance kernel.
        </p>

        <p className="body">
          Each new domain is composed from existing parts: a new orchestrator
          plus a small number of new skills, against the same identity and
          governance the first one used.
        </p>
      </div>
    </section>
  );
}
