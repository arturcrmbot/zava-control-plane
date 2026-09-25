/**
 * The living world, explained: people make choices through Laya, the world
 * changes, the bank sees only records, and its personas decide with Laya too.
 * Everything here is read from the world's own snapshot (BANKING_WORLD_LIFE=1).
 */
export interface LifeOption { id: string; label: string; p: number }
export interface LifeStep { by: string; question: string; chose: string; chose_label?: string; ms?: number | null; options: LifeOption[] }
export interface LifeDecision { t: number; when: string; kind: string; who?: string | null; profile?: string; title: string; steps: LifeStep[]; outcome: string }
export interface LifeEntry { t: number; when: string; who?: string | null; text: string; by: string; kind: string }
export interface Life {
  people?: number;
  payments?: number;
  scams_tried?: number;
  scams_paid?: number;
  scams_stopped?: number;
  scams_ignored?: number;
  calls?: number;
  joined?: number;
  left?: number;
  life_events?: number;
  laya_share?: number;
  laya_avg_ms?: number | null;
  decided_by_laya?: number;
  decided_by_rules?: number;
  cases_opened?: number;
  cases_per_hour?: number;
  decisions?: LifeDecision[];
  scam_decisions?: LifeDecision[];
  unknown_to_bank?: { name: string; circumstance: string }[];
  crews?: Record<string, Record<string, { tried: number; paid: number }>>;
  feed?: LifeEntry[];
  stories?: LifeEntry[];
}

export interface PersonaReading { id?: string; question?: string; p_yes?: number; lead?: number; clear?: boolean }
export interface JudgedCounts { laya: number; llm: number; rules: number }

const num = (value: number | undefined | null) => new Intl.NumberFormat("en-GB").format(Number(value ?? 0));
const pct = (p: number) => `${Math.round(p * 100)}%`;
const count = (n: number | undefined | null, one: string, many: string) => `${num(n)} ${Number(n ?? 0) === 1 ? one : many}`;

const BY: Record<string, { label: string; chip: string; bar: string }> = {
  laya: { label: "Laya", chip: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-300", bar: "bg-emerald-500" },
  code: { label: "code", chip: "bg-sky-100 text-sky-800 dark:bg-sky-900/50 dark:text-sky-300", bar: "bg-sky-500" },
  rules: { label: "rules", chip: "bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200", bar: "bg-slate-400" },
  world: { label: "world", chip: "bg-violet-100 text-violet-800 dark:bg-violet-900/50 dark:text-violet-300", bar: "bg-violet-500" },
};
const STORY_TONES: Record<string, string> = {
  scam: "border-red-400", call: "border-amber-400", life: "border-violet-400", join: "border-sky-400", leave: "border-sky-400", stay: "border-slate-300",
};

function ByChip({ by, ms }: { by: string; ms?: number | null }) {
  const style = BY[by] ?? BY.rules;
  return <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold ${style.chip}`}>{style.label}{ms ? ` · ${ms} ms` : ""}</span>;
}

function Card({ testId, title, explain, children, className = "" }: { testId: string; title: string; explain?: string; children: React.ReactNode; className?: string }) {
  return (
    <section data-testid={testId} className={`rounded-xl border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900 ${className}`}>
      <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">{title}</h2>
      {explain && <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{explain}</p>}
      <div className="mt-2">{children}</div>
    </section>
  );
}

/** The loop, left to right, with what it has done so far. */
export function HowItWorks({ life, judged, flagged }: { life: Life; judged: JudgedCounts; flagged: number }) {
  const total = (life.decided_by_laya ?? 0) + (life.decided_by_rules ?? 0);
  const steps = [
    { title: "1 · People live here", value: num(life.people), unit: "people",
      sub: `${num(life.joined)} joined · ${num(life.left)} left · ${count(life.life_events, "life event", "life events")}`,
      explain: "Each has a private life: who they are, their money, what has happened to them. The bank can't see it." },
    { title: "2 · Laya reads their situation", value: num(life.decided_by_laya), unit: "choices by Laya",
      sub: `${total ? pct((life.decided_by_laya ?? 0) / total) : "0%"} of all choices${life.laya_avg_ms ? ` · ${Math.round(life.laya_avg_ms)} ms each` : ""} · no tokens`,
      explain: "A small model on this Mac gives odds over a short menu. A seeded draw picks. Code does any maths." },
    { title: "3 · The world changes", value: num(life.payments), unit: Number(life.payments ?? 0) === 1 ? "payment" : "payments",
      sub: `${count(life.scams_tried, "scam", "scams")} tried · ${num(life.scams_paid)} paid · ${num(life.scams_stopped)} stopped at the bank`,
      explain: "Choices become real records: payments, calls to the bank, accounts opened and closed." },
    { title: "4 · The bank notices", value: num(flagged), unit: flagged === 1 ? "payment flagged" : "payments flagged",
      sub: `${count(life.calls, "customer", "customers")} rang the bank · ${count(life.cases_opened, "case", "cases")} opened (limit ${num(life.cases_per_hour)}/h)`,
      explain: "The bank only sees records. Its screening reads payment references; victims' calls become claims." },
    { title: "5 · Personas decide", value: num(judged.laya + judged.llm + judged.rules), unit: judged.laya + judged.llm + judged.rules === 1 ? "decision" : "decisions",
      sub: `${num(judged.laya)} fast judgement · ${num(judged.llm)} deep review · ${num(judged.rules)} rules`,
      explain: "Agents investigate; personas read the agent's reasoning with Laya. The rules still cap what they can approve." },
  ];
  return (
    <section data-testid="how-it-works" aria-label="How the world works" className="grid gap-2 md:grid-cols-5">
      {steps.map((s, i) => (
        <div key={s.title} className="relative rounded-xl border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">{s.title}</div>
          <div className="mt-1 flex items-baseline gap-1.5"><span className="text-2xl font-semibold tabular-nums text-slate-900 dark:text-white">{s.value}</span><span className="text-xs text-slate-500">{s.unit}</span></div>
          <div className="mt-0.5 text-[11px] text-slate-600 dark:text-slate-300">{s.sub}</div>
          <p className="mt-2 text-[11px] leading-snug text-slate-500 dark:text-slate-400">{s.explain}</p>
          {i < steps.length - 1 && <span aria-hidden className="absolute -right-2.5 top-1/2 z-10 hidden -translate-y-1/2 text-lg text-slate-300 md:block dark:text-slate-600">›</span>}
        </div>
      ))}
    </section>
  );
}

function OddsBar({ option, chosen, by }: { option: LifeOption; chosen: boolean; by: string }) {
  const style = BY[by] ?? BY.rules;
  return (
    <li className="flex items-center gap-2 text-[11px]">
      <span className={`w-2/5 truncate ${chosen ? "font-semibold text-slate-900 dark:text-white" : "text-slate-600 dark:text-slate-300"}`}>{chosen ? "✓ " : ""}{option.label}</span>
      <span className="h-2 flex-1 rounded-full bg-slate-100 dark:bg-slate-800">
        <span className={`block h-2 rounded-full ${style.bar} ${chosen ? "" : "opacity-40"}`} style={{ width: `${Math.max(2, Math.round(option.p * 100))}%` }} />
      </span>
      <span className="w-9 text-right tabular-nums text-slate-500">{pct(option.p)}</span>
    </li>
  );
}

export function DecisionCard({ decision }: { decision: LifeDecision }) {
  return (
    <article data-testid={`decision-${decision.kind}`} className="rounded-lg border border-slate-200 p-2.5 dark:border-slate-800">
      <header className="flex items-baseline justify-between gap-2">
        <span className="text-sm font-semibold text-slate-900 dark:text-white">{decision.title}</span>
        <span className="shrink-0 text-[10px] text-slate-400">{decision.when}</span>
      </header>
      {decision.profile && <p className="mt-0.5 text-[11px] italic text-slate-500 dark:text-slate-400">{decision.profile}</p>}
      {decision.steps.map((step, i) => (
        <div key={i} className="mt-2">
          <div className="flex items-center gap-1.5 text-[11px]"><ByChip by={step.by} ms={step.ms} /><span className="text-slate-700 dark:text-slate-200">{step.question}</span></div>
          <ul className="mt-1 space-y-0.5 pl-1">{step.options.map((option) => <OddsBar key={option.id} option={option} chosen={option.id === step.chose} by={step.by} />)}</ul>
        </div>
      ))}
      <div className="mt-2 text-xs font-medium text-slate-900 dark:text-white">→ {decision.outcome}</div>
    </article>
  );
}

/** Real choices, as they happen: the question, Laya's odds, the draw, what followed. */
export function LayaDecisions({ life }: { life: Life }) {
  const scam = (life.scam_decisions ?? [])[0];
  const others = (life.decisions ?? []).slice(0, scam ? 2 : 3);
  return (
    <Card testId="laya-decisions" title="Watch Laya decide"
      explain="For each choice Laya reads who the person is and gives odds over a short menu; a seeded draw picks and code makes the record. Steps marked code are ordinary arithmetic, rules is the fallback when Laya is unsure or down. Laya never moves the bank's money.">
      {!scam && others.length === 0 ? <div className="text-xs text-slate-400">Waiting for the first choices…</div> : (
        <div className="space-y-2">
          {scam && <DecisionCard decision={scam} />}
          {others.map((d) => <DecisionCard key={`${d.t}-${d.title}`} decision={d} />)}
        </div>
      )}
    </Card>
  );
}

export function LifeStories({ life }: { life: Life }) {
  const stories = (life.stories ?? []).slice(0, 9);
  const spending = (life.feed ?? []).filter((e) => e.kind === "payment" || e.kind === "money").slice(0, 5);
  return (
    <Card testId="life-stories" title="What is happening to people">
      {stories.length === 0 ? <div className="text-xs text-slate-400">Nothing yet.</div> : (
        <ul className="space-y-1">
          {stories.map((e, i) => (
            <li key={`${e.t}-${i}`} className={`flex items-baseline gap-2 border-l-2 pl-2 text-[11px] ${STORY_TONES[e.kind] ?? "border-slate-300"}`}>
              <span className="min-w-0 flex-1 text-slate-800 dark:text-slate-100">{e.text}</span>
              <ByChip by={e.by} />
            </li>
          ))}
        </ul>
      )}
      <div className="mt-3 text-[10px] font-semibold uppercase tracking-wide text-slate-400">Everyday spending</div>
      <ul className="mt-1 space-y-0.5">
        {spending.map((e, i) => <li key={`${e.t}-s${i}`} className="truncate text-[11px] text-slate-600 dark:text-slate-300">{e.text}</li>)}
      </ul>
    </Card>
  );
}

export function UnknownToBank({ people }: { people: { name: string; circumstance: string }[] }) {
  return (
    <Card testId="unknown-to-bank" title="What the bank doesn't know"
      explain="True in the world, missing from the bank's records. If one of them calls, the agent reads the record while the customer describes their life.">
      {people.length === 0 ? <div className="text-xs text-slate-400">Nobody yet.</div> : (
        <ul className="space-y-0.5">{people.map((p) => <li key={p.name} className="text-[11px] text-slate-700 dark:text-slate-200"><span className="font-medium">{p.name}</span> {p.circumstance}</li>)}</ul>
      )}
    </Card>
  );
}

export function CrewBoard({ crews }: { crews: Life["crews"] }) {
  const rows = Object.entries(crews ?? {});
  return (
    <Card testId="crew-board" title="Scam crews"
      explain="Each crew matches a scam to its target (Laya reads the target) and leans towards what has worked. Paid / tried.">
      {rows.length === 0 ? <div className="text-xs text-slate-400">No attempts yet.</div> : (
        <div className="space-y-1.5">
          {rows.map(([crew, tactics]) => (
            <div key={crew} className="text-[11px]">
              <span className="font-medium text-slate-800 dark:text-slate-100">{crew}</span>
              <span className="ml-2 inline-flex flex-wrap gap-1 align-middle">
                {Object.entries(tactics).map(([label, t]) => (
                  <span key={label} className={`rounded px-1.5 py-0.5 ${t.paid > 0 ? "bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300" : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"}`}>{label} {t.paid}/{t.tried}</span>
                ))}
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

/** How a persona read the agent's reasoning for the case on the strip. */
export function PersonaReadings({ persona, readings, concerns, decidedBy, layaMs, reviewMs, summary }: {
  persona: string; readings: PersonaReading[]; concerns: string[]; decidedBy: string; layaMs?: number; reviewMs?: number; summary?: string;
}) {
  const how = decidedBy === "laya" ? `fast judgement${layaMs ? ` in ${Math.round(layaMs)} ms` : ""}`
    : decidedBy === "llm" ? `deep review${reviewMs ? ` in ${(reviewMs / 1000).toFixed(1)} s` : ""}` : "the rules";
  return (
    <Card testId="persona-readings" title={`How the ${persona.toLowerCase()} read the agent's reasoning`}
      explain="Narrow yes/no questions to Laya about the agent's text; code compares the answers with the record. A clear contradiction holds the case; an unclear one goes to a larger model.">
      <ul className="space-y-1">
        {readings.map((r, i) => (
          <li key={r.id ?? i} className="flex items-center gap-2 text-[11px]">
            <span className="w-3/5 truncate text-slate-700 dark:text-slate-200">{r.question}</span>
            <span className="h-2 flex-1 rounded-full bg-slate-100 dark:bg-slate-800"><span className="block h-2 rounded-full bg-emerald-500" style={{ width: `${Math.round((r.p_yes ?? 0) * 100)}%` }} /></span>
            <span className="w-16 text-right tabular-nums text-slate-500">{pct(r.p_yes ?? 0)} yes{r.clear === false ? " ?" : ""}</span>
          </li>
        ))}
      </ul>
      {concerns.length > 0 && <div className="mt-2 text-[11px] text-amber-700 dark:text-amber-300">Found: {concerns.join("; ")}</div>}
      <div className="mt-2 text-xs text-slate-800 dark:text-slate-100">Decided by <span className="font-semibold">{how}</span>{summary ? `: ${summary}` : ""}</div>
    </Card>
  );
}
