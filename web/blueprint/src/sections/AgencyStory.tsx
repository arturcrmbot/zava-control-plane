/**
 * Section: AgencyStory
 *
 * A customer-facing worked example using the Aurora budget-freeze flow.
 * Operating records are synthetic; Durable checkpoints, agent/tool calls,
 * authority decisions, audit and visible evidence are real runtime boundaries.
 */

const steps: { label: string; title: string; body: string }[] = [
  {
    label: "01 · Signal",
    title: "A budget signal starts the response.",
    body:
      "The synthetic Aurora spending record reaches its configured threshold. The parent Durable workflow captures the budget facts so its recommendation and later actions refer to the same observation.",
  },
  {
    label: "02 · Recommendation",
    title: "An agent prepares the recommendation.",
    body:
      "A bounded agent skill assesses the observed budget position and explains its recommendation. Model output is recorded with the run. The agent cannot use that recommendation as permission to apply a policy.",
  },
  {
    label: "03 · Decision",
    title: "The CFO decision is explicit.",
    body:
      "The workflow pauses for an operator acting in the CFO role. The authority check uses the requested action and scope. Background personae cannot silently approve this gate. Approval, rejection and timeout remain different outcomes.",
  },
  {
    label: "04 · Policy",
    title: "Decision becomes active policy.",
    body:
      "Only an approved decision can create the governed freeze policy. Its decision ID links the operator outcome to the actual policy record. Rejection and timeout do not create a freeze.",
  },
  {
    label: "05 · Invoice reviews",
    title: "Queued AP invoices use the existing workflow.",
    body:
      "The parent starts real AP invoice child workflows against synthetic invoice records. Lookup, matching, approval and escalation follow that existing engine. Each child has its own execution ID and outcome; these are not simulated completion messages or real payments.",
  },
  {
    label: "06 · Synthesis",
    title: "The executive summary reports actual outcomes.",
    body:
      "The summary for the CEO is calculated from the policy result and child workflow outcomes. It reports what happened rather than asking another model to invent a successful ending. The same records remain available for inspection.",
  },
];

export function AgencyStory() {
  return (
    <section className="section">
      <div className="column--wide stack-xl">
        <header className="argument__intro stack">
          <p className="subtitle">A worked example</p>
          <h2 className="section-title">
            One spending decision, shared consequences.
          </h2>
          <p className="body">
            Aurora connects budget oversight with accounts payable through
            a real parent workflow and child executions. The operating data are synthetic.
            Workflow, authority and evidence are executable runtime boundaries,
            not a sequence of captions. The viewer distinguishes live work from
            recorded execution and exposes the selected run&apos;s evidence.
          </p>
        </header>

        <ol className="argument__list">
          {steps.map((step) => (
            <li key={step.label} className="argument__item">
              <div className="argument__item-label">{step.label}</div>
              <div className="argument__item-body">
                <h3 className="argument__item-title">{step.title}</h3>
                <p className="body">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>

        <p className="body">
          Those boundaries are the connection points. Replace Aurora&apos;s
          records with a spend feed, route approval to the CFO&apos;s channel
          and connect the AP system. The durable workflow can stay in place.
        </p>
      </div>
    </section>
  );
}
