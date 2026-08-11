
const pieces: { label: string; title: string; body: string }[] = [
  {
    label: "Memory",
    title: "Where memory is enabled, one run can inform the next.",
    body:
      "Decisions, approvals and tool calls in a memory-enabled domain are written to a structured store. When the next workflow opens an agent session for that domain, the substrate retrieves the most relevant past entries and splices them into the system message. The agent benefits from accumulated precedent without requiring fine-tuning.",
  },
  {
    label: "Consolidation",
    title: "Configured consolidation turns repeated evidence into a smaller lesson set.",
    body:
      "At configured intervals, a consolidation pass reviews recent runs as a set — what worked, what did not, where the rule said one thing and the right answer was another. Patterns are written back as distilled entries, replacing the raw runs they came from. Consolidation is attributable and policy-bound; it runs only where configured.",
  },
  {
    label: "Knowledge graph",
    title: "Enabled workflows project people, money, decisions and time into one connected picture.",
    body:
      "For domains where the knowledge graph is active, every workflow projects the entities it touches — requester, approver, amount, cost centre, decision — onto a shared structured spine. When an approver opens a new request, the substrate can surface relevant precedents from across that graph.",
  },
];

export function Memory() {
  return (
    <section className="section">
      <div className="column--wide stack-xl">
        <header className="stack">
          <p className="subtitle">How the substrate gets better at its job</p>
          <h2 className="section-title">
            Context can carry between runs, where enabled.
          </h2>
        </header>

        <ol className="argument__list">
          {pieces.map((item) => (
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
          Where memory is enabled, the substrate can put the rule beside recent
          comparable decisions and lessons from earlier runs. A domain inherits
          that record only when its memory configuration says it should. The
          useful part is the precedent, not a claim that every workflow learns
          automatically.
        </p>
      </div>
    </section>
  );
}
