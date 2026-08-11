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
    title: "Brand spend crosses threshold.",
    body:
      "Aurora, the spend-monitoring workflow, detects that the brand marketing budget has crossed its configured threshold. A durable checkpoint records the signal and opens an agent session to assess exposure across in-flight commitments.",
  },
  {
    label: "02 · Recommendation",
    title: "CFO observer recommends a freeze.",
    body:
      "The CFO observer agent reviews current run-rate, outstanding purchase orders and committed spend. It recommends a brand spend freeze and records its reasoning in the audit log. No action is taken yet — the recommendation waits at a human authority gate.",
  },
  {
    label: "03 · Decision",
    title: "Authority and person approve.",
    body:
      "The authority resolver matches the freeze action to the CFO role at this threshold. The CFO reviews the recommendation and approves. The approval is signed and written to the tamper-evident log. The durable workflow continues.",
  },
  {
    label: "04 · Policy",
    title: "Decision becomes active policy.",
    body:
      "The approved freeze is registered as active policy in the pack's policy store. Downstream workflows that consult the policy store will see the freeze. The decision is attributable, timestamped and auditable.",
  },
  {
    label: "05 · Escalation",
    title: "In-flight AP invoices escalate.",
    body:
      "The AP invoice workflow detects that pending brand-category invoices are now subject to the freeze policy. Invoices above threshold are escalated to the AP controller for individual review rather than processed automatically. The escalation path is set by the AP-003 authority rule.",
  },
  {
    label: "06 · Synthesis",
    title: "CEO synthesis sees changed posture.",
    body:
      "The CEO synthesis workflow surfaces the changed spending posture: freeze active, invoices escalated, CFO decision recorded. The synthesis is grounded in the durable record — not inferred from agent output alone.",
  },
];

export function AgencyStory() {
  return (
    <section className="section">
      <div className="column--wide stack-xl">
        <header className="argument__intro stack">
          <p className="subtitle">A signal that travels the whole organisation</p>
          <h2 className="section-title">
            Watch one signal travel across the organisation.
          </h2>
          <p className="body">
            The Aurora flow shows how a single spend signal moves from
            detection through CFO decision, active policy, AP invoice
            escalation and CEO synthesis — all in one connected durable
            execution. The operating data are synthetic; the Durable
            checkpoints, agent and tool calls, authority decision, audit
            and visible evidence are real runtime boundaries.
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
          Each boundary in this flow is a connection point. Replace synthetic
          Aurora data with your real spend feed, connect your real CFO approval
          channel, bring in your existing AP system — and the durable workflow
          stays the same.
        </p>
      </div>
    </section>
  );
}
