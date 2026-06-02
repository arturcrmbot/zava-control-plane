import { useAuthority } from "../lib/useAuthority";

const SHOWN_FIELDS = [
  "rule_id",
  "action",
  "category",
  "value_band_gbp",
  "approver_role",
  "escalation_chain",
  "basis",
] as const;

function curatedJson<T extends object>(obj: T, keys: readonly (keyof T)[]): string {
  const picked: Partial<T> = {};
  for (const k of keys) picked[k] = obj[k];
  return JSON.stringify(picked, null, 2);
}

export function Authority() {
  const { data } = useAuthority();
  // AP-003 — material AP invoice routes to controller. Pairs directly with
  // the controller persona shown in the section above.
  const example = data.rules.find((r) => r.rule_id === "AP-003") ?? data.rules[0];

  return (
    <section className="section authority">
      <div className="column--wide stack-lg">
        <header className="stack">
          <p className="subtitle">Who is allowed to approve what</p>
          <h2 className="section-title">
            The delegated-authority matrix.
          </h2>
          <p className="body">
            The substrate&apos;s agent governance toolkit sits in{" "}
            <a
              className="footer__link"
              href="https://github.com/arturcrmbot/zava-control-plane/tree/main/api/server/services/governance"
              target="_blank"
              rel="noopener noreferrer"
            >
              <code className="mono">api/server/services/governance/</code>
            </a>
            . One piece of that is the delegated-authority matrix, which
            decides who can approve what at what threshold. It&apos;s a
            single JSON file (
            <a
              className="footer__link"
              href="https://github.com/arturcrmbot/zava-control-plane/blob/main/data/synthetic/authority/matrix.json"
              target="_blank"
              rel="noopener noreferrer"
            >
              <code className="mono">data/synthetic/authority/matrix.json</code>
            </a>
            ), {data.rule_count} rules covering every approval action in the
            organisation. Here&apos;s what one rule looks like:
          </p>

          <pre className="snippet">{curatedJson(example, SHOWN_FIELDS)}</pre>

          <p className="body">
            Compliance edits the file directly, and the substrate picks the
            change up on the next workflow without a redeploy. Any skill
            that needs to route a decision (human-driven or agent-driven)
            consults the matrix, gets back the matched rule, and proceeds.
            Thresholds live on the rule, not on the persona, which means
            the agent path and the human path resolve approvals through the
            same logic.
          </p>
        </header>
      </div>
    </section>
  );
}
