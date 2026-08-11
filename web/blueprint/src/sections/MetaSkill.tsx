const COMPOSITION_STEPS = ["Research", "Design", "Build", "Prove"];

const readinessLevels: { label: string; title: string; body: string }[] = [
  {
    label: "Build ready",
    title: "Machine gates pass.",
    body:
      "Automated checks confirm the pack loads, domains register, authority resolves and durable workflows execute without error. This is a necessary precondition for anything else.",
  },
  {
    label: "Demo ready",
    title: "Build ready plus human seller review.",
    body:
      "A seller has reviewed the pack's reset sequence, pacing, visual and story. The reference runs end-to-end and can be shown to a customer. Build ready is necessary but not sufficient.",
  },
  {
    label: "Deployed",
    title: "Approved mode passes deployment preflight and smoke.",
    body:
      "An explicit deployment decision has been made. Deployment preflight and post-deploy smoke checks pass. Private-live and public-replay are separate approved modes.",
  },
];

export function MetaSkill() {
  return (
    <section className="section meta">
      <div className="column--wide stack-lg">
        <header className="stack">
          <p className="subtitle">How the type case extends itself</p>
          <h2 className="section-title">
            A new industry is not a reskin.
          </h2>
          <p className="body">
            <strong>compose-org</strong> is a guided pipeline that walks{" "}
            {COMPOSITION_STEPS.join(" → ")}. Research uses the
            organisation&apos;s public footprint. Design produces a
            pack-specific actor world, process map and authority model. Build
            assembles the pack-specific agents, capabilities and durable
            workflows. Prove runs machine gates against the assembled pack.
          </p>
          <p className="body">
            Packs share runtime contracts for durable execution, identity,
            audit, governance and proof. Business behaviour stays with the
            pack.
          </p>
          <p className="body">
            Existing investments connect at the same boundaries. A reference
            edge remains synthetic until a customer connects the corresponding
            system, policy, data source or person.
          </p>
        </header>

        <ol className="argument__list">
          {readinessLevels.map((item) => (
            <li key={item.label} className="argument__item">
              <div className="argument__item-label">{item.label}</div>
              <div className="argument__item-body">
                <h3 className="argument__item-title">{item.title}</h3>
                <p className="body">{item.body}</p>
              </div>
            </li>
          ))}
        </ol>

        <div className="meta__extension">
          <div className="meta__extension-text">
            <h3 className="passage-title">Two public steps, one executable org.</h3>
            <p className="body">
              <strong>zava-workspace-deploy</strong> takes proven output and
              requires an explicit choice: private-live (the reference
              implementation running on live Azure infrastructure with
              synthetic organisational activity) or public-replay (recorded
              telemetry inspectable without writable systems). The two modes
              share one codebase; the choice is a deploy-time flag.
            </p>
            <p className="body">
              See{" "}
              <a
                className="footer__link"
                href="https://aiappsgbb.github.io/zava-constellation/"
                target="_blank"
                rel="noopener noreferrer"
              >
                zava-constellation
              </a>
              {" "}for the companion skill library.
            </p>
          </div>

          <aside className="meta__sidebar">
            <div className="meta__sidebar-title">compose-org pipeline</div>
            <div className="meta__sidebar-list">
              {COMPOSITION_STEPS.join(" → ")}
            </div>
          </aside>
        </div>
      </div>
    </section>
  );
}
