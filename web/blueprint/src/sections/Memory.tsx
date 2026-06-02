
const pieces: { label: string; title: string; body: string }[] = [
  {
    label: "01 · Memory",
    title: "Every run leaves a trace the next run gets to read.",
    body:
      "Every decision an agent makes, every approval a persona gives, every tool call against an MCP gets written to a structured store, organised by domain. When the next workflow opens an agent session for that domain, the substrate finds the past entries most similar to the prompt and splices them into the system message before the model sees it. The agent acts as if it has been doing this job for a long time, because in aggregate it has.",
  },
  {
    label: "02 · Dreaming",
    title: "The system consolidates what it has learned in the quiet hours.",
    body:
      "Recall on its own gives the agent one anecdote at a time. So at quiet intervals the substrate runs a consolidation pass over recent runs and asks a slower model to look at them as a set: what worked, what didn't, where the rule said one thing and the right answer turned out to be another. The patterns get written back as new memory entries, replacing the raw runs they were distilled from. Anthropic invented this; they call it dreaming.",
  },
  {
    label: "03 · The knowledge graph",
    title: "People, money, decisions and time, in one connected picture.",
    body:
      "Memory is per-domain prose. The graph is the structured spine underneath it, shared across every domain. Every workflow projects the entities it touches — requester, approver, amount, cost centre, decision — onto that graph. When an HR director opens a training request, the substrate already knows which previous trainings that person has approved, which precedents apply, and what came of them.",
  },
];

export function Memory() {
  return (
    <section className="section">
      <div className="column--wide stack-xl">
        <header className="stack">
          <p className="subtitle">How the substrate gets better at its job</p>
          <h2 className="section-title">
            The institution that remembers itself.
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
          This is where the authority matrix stops being a static rulebook
          and starts behaving like institutional judgement. The substrate
          hands the approver the rule, the last few comparable decisions,
          and the lessons from the runs where escalation turned out to be
          the right call. Add the next domain on top and it inherits a
          living record of every comparable thing the organisation has ever
          done. That&apos;s the part that compounds.
        </p>
      </div>
    </section>
  );
}
