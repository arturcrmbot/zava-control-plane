
const pieces: { label: string; title: string; body: string }[] = [
  {
    label: "01 · Memory",
    title: "Every run leaves a trace the next run gets to read.",
    body:
      "Every decision an agent makes, every approval a persona gives, every tool call against an MCP — all of it gets written to a structured store, organised by domain. When the next workflow opens an agent session for that same domain, the substrate looks at the prompt, finds the handful of past entries most similar to what's being asked now, and quietly splices them into the system message before the model sees it. The agent doesn't have to know that memory exists. It just acts as if it has been doing this job for a long time, because in aggregate it has.",
  },
  {
    label: "02 · Dreaming",
    title: "The system consolidates what it has learned in the quiet hours.",
    body:
      "Pulling individual past cases back at decision time is useful, but it leaves the agent reading one anecdote at a time. So at intervals — usually when the load is low — the substrate runs a consolidation pass over recent runs and asks a slower, more reflective model to look at them as a set. What worked, what didn't, where the persona hesitated, where the rule said one thing and the right answer turned out to be another. The patterns it finds get written back into the memory store as new entries, often replacing the raw runs they were distilled from. By the next morning, recall on a similar prompt returns the lesson rather than the noise. I call this a dream pass. It is the part of the substrate that turns activity into improvement without anyone retraining a model.",
  },
  {
    label: "03 · The knowledge graph",
    title: "People, money, decisions and time, in one connected picture.",
    body:
      "Memory is per-domain prose. The graph is the structured spine that sits underneath it. Every workflow projects the entities it touches — the requester, the approver, the amount, the cost centre, the dates, the decision itself — onto a single graph shared across every domain. When an HR director opens a training request, the substrate already knows which previous trainings that person has approved, which precedents are on file for this category, which rule fired last time, and what came of it. The graph is how the past stays addressable. The personae's UI cards and the agents' recall both read from it at the moment of decision.",
  },
];

export function Memory() {
  return (
    <section className="section">
      <div className="column--wide stack-xl">
        <header className="argument__intro stack">
          <p className="subtitle">How the substrate gets better at its job</p>
          <h2 className="section-title">
            The institution that remembers itself.
          </h2>
          <p className="body">
            Memory — and the graph underneath it, and the consolidation
            loop on top.
          </p>
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
          This is also where the authority matrix stops being a static rulebook
          and starts behaving like institutional judgement. A rule by itself
          says &ldquo;the HR director may approve standard training up to
          &pound;1,500.&rdquo; The substrate hands the approver the rule, the
          last five comparable decisions for similar requests, the lessons
          distilled from the runs where escalation turned out to be the right
          call, and the precedent for the proposed answer. The same is true
          for the agents that draft a recommendation before the human sees it:
          they reason against the rule and the history at the same time.
          Policy decisions don&apos;t happen in a vacuum, and on this
          substrate they don&apos;t have to.
        </p>

        <p className="body">
          Memory, dreaming and the graph aren&apos;t a feature bolted onto one
          domain. They&apos;re the layer every domain shares, every agent
          inherits, every approver leans on. Add the next domain on top and
          it doesn&apos;t just get the harness and the skills and the
          governance — it gets a living record of every comparable thing the
          organisation has ever done. That&apos;s the part that compounds.
        </p>
      </div>
    </section>
  );
}
