/**
 * Zava Bank's world for people who run banks: customers living their lives,
 * the fraud aimed at them, what the bank can and can't see, and how it
 * responds. Read from the world's own snapshot (BANKING_WORLD_LIFE=1). How the
 * simulation works (and the model behind it) is kept to one folded section.
 */
export interface LifeOption { id: string; label: string; p: number }
export interface LifeStep { by: string; question: string; chose: string; chose_label?: string; ms?: number | null; options: LifeOption[] }
export interface LifeDecision { t: number; when: string; kind: string; who?: string | null; profile?: string; title: string; steps: LifeStep[]; outcome: string }
export interface LifeEntry { t: number; when: string; who?: string | null; text: string; by: string; kind: string }
export interface UnreportedLoss { name: string; amount_gbp: number; scam: string; hours_ago: number }
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
  lost_gbp?: number;
  unreported_count?: number;
  unreported_gbp?: number;
  unreported?: UnreportedLoss[];
  claimants?: Record<string, string>;
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
const gbp = (value: number | undefined | null) => new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 }).format(Number(value ?? 0));

/** How a manager's decision was reached, in the bank's words. */
export const HOW_DECIDED: Record<string, string> = { laya: "quick check", llm: "closer review", rules: "standard rules" };

const STORY_TAGS: Record<string, { label: string; border: string }> = {
  scam: { label: "fraud", border: "border-red-400" },
  call: { label: "call", border: "border-amber-400" },
  life: { label: "life", border: "border-violet-400" },
  join: { label: "joined", border: "border-emerald-400" },
  leave: { label: "left", border: "border-slate-400" },
  stay: { label: "stayed", border: "border-slate-300" },
};

function Card({ testId, title, explain, children, className = "" }: { testId: string; title: string; explain?: string; children: React.ReactNode; className?: string }) {
  return (
    <section data-testid={testId} className={`rounded-xl border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900 ${className}`}>
      <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">{title}</h2>
      {explain && <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{explain}</p>}
      <div className="mt-2">{children}</div>
    </section>
  );
}

/** The day at Zava Bank, left to right: customers, fraud, losses, what the bank learns, decisions. */
export function TodayAtZava({ life, flagged, decided, refunded, waiting }: { life: Life; flagged: number; decided: number; refunded: number; waiting: number }) {
  const groups = Object.keys(life.crews ?? {}).length;
  const steps = [
    { title: "1 · Customers", value: num(life.people), unit: "customers",
      sub: `${num(life.joined)} joined · ${num(life.left)} left`,
      explain: "Wages in, rent and bills out, shopping, family. Some are going through things the bank hasn't been told about." },
    { title: "2 · Fraudsters target them", value: num(life.scams_tried), unit: Number(life.scams_tried ?? 0) === 1 ? "scam tried" : "scams tried",
      sub: `by ${count(groups, "criminal group", "criminal groups")}`,
      explain: "Impersonation, romance, investment and tax scams, each aimed at someone it might work on." },
    { title: "3 · Some are caught out", value: gbp(life.lost_gbp), unit: `lost by ${count(life.scams_paid, "customer", "customers")}`,
      sub: `${num(life.scams_stopped)} checked with us first · ${num(life.scams_ignored)} ignored it`,
      explain: "A warning on a large payment makes people stop and think. Not everyone does." },
    { title: "4 · The bank finds out", value: num(life.calls), unit: Number(life.calls ?? 0) === 1 ? "customer rang us" : "customers rang us",
      sub: `${count(flagged, "payment", "payments")} flagged by screening · ${count(life.unreported_count, "loss", "losses")} not reported yet`,
      explain: "The bank sees payments and what customers tell it. Nothing else." },
    { title: "5 · Investigated and decided", value: num(decided), unit: decided === 1 ? "claim decided" : "claims decided",
      sub: `${gbp(refunded)} refunded · ${num(waiting)} waiting for a manager`,
      explain: "Agents gather the evidence. An accountable manager decides, within the limits of their authority." },
  ];
  return (
    <section data-testid="bank-today" aria-label="Today at Zava Bank" className="grid gap-2 md:grid-cols-5">
      {steps.map((s, i) => (
        <div key={s.title} className="relative rounded-xl border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">{s.title}</div>
          <div className="mt-1 flex flex-wrap items-baseline gap-x-1.5"><span className="text-2xl font-semibold tabular-nums text-slate-900 dark:text-white">{s.value}</span><span className="text-xs text-slate-500">{s.unit}</span></div>
          <div className="mt-0.5 text-[11px] text-slate-600 dark:text-slate-300">{s.sub}</div>
          <p className="mt-2 text-[11px] leading-snug text-slate-500 dark:text-slate-400">{s.explain}</p>
          {i < steps.length - 1 && <span aria-hidden className="absolute -right-2.5 top-1/2 z-10 hidden -translate-y-1/2 text-lg text-slate-300 md:block dark:text-slate-600">›</span>}
        </div>
      ))}
    </section>
  );
}

function LikelihoodBar({ option, chosen }: { option: LifeOption; chosen: boolean }) {
  return (
    <li className="flex items-center gap-2 text-[11px]">
      <span className={`w-2/5 truncate ${chosen ? "font-semibold text-slate-900 dark:text-white" : "text-slate-600 dark:text-slate-300"}`}>{chosen ? "✓ " : ""}{option.label}</span>
      <span className="h-2 flex-1 rounded-full bg-slate-100 dark:bg-slate-800">
        <span className={`block h-2 rounded-full bg-blue-500 ${chosen ? "" : "opacity-40"}`} style={{ width: `${Math.max(2, Math.round(option.p * 100))}%` }} />
      </span>
      <span className="w-9 text-right tabular-nums text-slate-500">{pct(option.p)}</span>
    </li>
  );
}

function outcomeTone(decision: LifeDecision): string {
  if (decision.kind === "scam") return decision.outcome.startsWith("fell for") ? "text-red-700 dark:text-red-300" : "text-emerald-700 dark:text-emerald-300";
  if (decision.kind === "leave") return decision.outcome.startsWith("closes") ? "text-red-700 dark:text-red-300" : "text-slate-900 dark:text-white";
  return "text-slate-900 dark:text-white";
}

/** The three likeliest options, always including what was chosen: an unlikely choice is the interesting one. */
function shownOptions(step: LifeStep): LifeOption[] {
  const top = step.options.slice(0, 3);
  const chosen = step.options.find((o) => o.id === step.chose);
  return !chosen || top.includes(chosen) ? top : [...top.slice(0, 2), chosen];
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
          <div className="text-[11px] text-slate-700 dark:text-slate-200">{step.question}</div>
          <ul className="mt-1 space-y-0.5 pl-1">{shownOptions(step).map((option) => <LikelihoodBar key={option.id} option={option} chosen={option.id === step.chose} />)}</ul>
        </div>
      ))}
      <div className={`mt-2 text-xs font-medium ${outcomeTone(decision)}`}>→ {decision.outcome}</div>
    </article>
  );
}

/** Real choices as they happen: who the customer is, what weighed on it, what they did. */
export function CustomerDecisions({ life }: { life: Life }) {
  const scam = (life.scam_decisions ?? [])[0];
  const others = (life.decisions ?? []).slice(0, scam ? 2 : 3);
  return (
    <Card testId="customer-decisions" title="Why customers did what they did"
      explain="Each customer decides from who they are and what is going on in their life. The bars show how likely each choice was: the same moment can go either way.">
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
    <Card testId="life-stories" title="What's happening">
      {stories.length === 0 ? <div className="text-xs text-slate-400">Nothing yet.</div> : (
        <ul className="space-y-1">
          {stories.map((e, i) => {
            const tag = STORY_TAGS[e.kind] ?? { label: e.kind, border: "border-slate-300" };
            return (
              <li key={`${e.t}-${i}`} className={`flex items-baseline gap-2 border-l-2 pl-2 text-[11px] ${tag.border}`}>
                <span className="min-w-0 flex-1 text-slate-800 dark:text-slate-100">{e.text}</span>
                <span className="shrink-0 text-[10px] uppercase tracking-wide text-slate-400">{tag.label}</span>
              </li>
            );
          })}
        </ul>
      )}
      <div className="mt-3 text-[10px] font-semibold uppercase tracking-wide text-slate-400">Everyday banking</div>
      <ul className="mt-1 space-y-0.5">
        {spending.map((e, i) => <li key={`${e.t}-s${i}`} className="truncate text-[11px] text-slate-600 dark:text-slate-300">{e.text}</li>)}
      </ul>
    </Card>
  );
}

function hoursAgo(hours: number): string {
  if (hours < 1) return "under an hour ago";
  if (hours < 48) return `${Math.round(hours)} h ago`;
  return `${Math.round(hours / 24)} days ago`;
}

/** Scammed, but they haven't told the bank: to the bank it is still an ordinary payment. */
export function UnreportedLosses({ life }: { life: Life }) {
  const rows = life.unreported ?? [];
  return (
    <Card testId="unreported-losses" title="Losses nobody has reported yet"
      explain="These customers have been scammed but haven't called. Until they do, the bank sees an ordinary payment.">
      {rows.length === 0 ? <div className="text-xs text-slate-400">None right now.</div> : (
        <>
          <div data-testid="unreported-total" className="mb-1 text-xs font-medium text-red-700 dark:text-red-300">{count(life.unreported_count, "customer", "customers")} · {gbp(life.unreported_gbp)}</div>
          <ul className="space-y-0.5">
            {rows.map((r) => (
              <li key={`${r.name}-${r.hours_ago}`} className="flex items-baseline justify-between gap-2 text-[11px] text-slate-700 dark:text-slate-200">
                <span className="min-w-0 truncate"><span className="font-medium">{r.name}</span> · {r.scam}</span>
                <span className="shrink-0 tabular-nums text-slate-500">{gbp(r.amount_gbp)} · {hoursAgo(r.hours_ago)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </Card>
  );
}

export function UnknownToBank({ people }: { people: { name: string; circumstance: string }[] }) {
  return (
    <Card testId="unknown-to-bank" title="What the bank hasn't been told"
      explain="True in these customers' lives, missing from the bank's records. The bank only learns it if they mention it when they call.">
      {people.length === 0 ? <div className="text-xs text-slate-400">Nobody yet.</div> : (
        <ul className="space-y-0.5">{people.map((p) => <li key={p.name} className="text-[11px] text-slate-700 dark:text-slate-200"><span className="font-medium">{p.name}</span> {p.circumstance}</li>)}</ul>
      )}
    </Card>
  );
}

export function CrewBoard({ crews }: { crews: Life["crews"] }) {
  const rows = Object.entries(crews ?? {});
  return (
    <Card testId="crew-board" title="Criminal groups"
      explain="Organised groups targeting Zava customers. Each picks a scam to suit the person and repeats what works. Worked / tried.">
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

/** What a manager checked in the agent's reasoning before deciding the case on the strip. */
export function PersonaReadings({ persona, readings, concerns, decidedBy, summary }: {
  persona: string; readings: PersonaReading[]; concerns: string[]; decidedBy: string; summary?: string;
}) {
  return (
    <Card testId="persona-readings" title={`What the ${persona.toLowerCase()} checked before deciding`}
      explain="The manager tests the agent's reasoning against the case record. If the two disagree, the case is held for a closer look.">
      <ul className="space-y-1">
        {readings.map((r, i) => {
          const yes = (r.p_yes ?? 0) >= 0.5;
          const sure = yes ? r.p_yes ?? 0 : 1 - (r.p_yes ?? 0);
          return (
            <li key={r.id ?? i} className="flex items-center gap-2 text-[11px]">
              <span className="w-3/5 truncate text-slate-700 dark:text-slate-200">{r.question}</span>
              <span className="h-2 flex-1 rounded-full bg-slate-100 dark:bg-slate-800"><span className="block h-2 rounded-full bg-blue-500" style={{ width: `${Math.round(sure * 100)}%` }} /></span>
              <span className="w-20 text-right tabular-nums text-slate-500">{yes ? "Yes" : "No"} {pct(sure)}{r.clear === false ? " · unsure" : ""}</span>
            </li>
          );
        })}
      </ul>
      {concerns.length > 0 && <div className="mt-2 text-[11px] text-amber-700 dark:text-amber-300">Found: {concerns.join("; ")}</div>}
      <div className="mt-2 text-xs text-slate-800 dark:text-slate-100">Decision{summary ? `: ${summary}` : ""} <span className="text-[10px] uppercase tracking-wide text-slate-400">{HOW_DECIDED[decidedBy] ?? decidedBy}</span></div>
    </Card>
  );
}

/** The one place the page explains the simulation itself, folded away for the curious. */
export function AboutSimulation({ life, judged }: { life: Life; judged: JudgedCounts }) {
  const total = (life.decided_by_laya ?? 0) + (life.decided_by_rules ?? 0);
  return (
    <details data-testid="about-simulation" className="rounded-xl border border-slate-200 bg-white p-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
      <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">How this simulation works</summary>
      <div className="mt-2 max-w-4xl space-y-2 leading-relaxed">
        <p>Zava Bank and everyone in it are fictional. Each customer has a profile: age, household, work, temperament, and sometimes a hard time the bank knows nothing about.</p>
        <p>Their choices are made by Laya, a small language model running on this laptop: what to spend on, whether to fall for a scam, when to realise and ring the bank, whether to leave after a claim. Laya weighs the options and a seeded random draw picks one, so the same moment can go either way. Amounts, dates and limits are ordinary code.</p>
        <p>On the bank's side, agents investigate each case and managers decide within their delegated authority. The bank's rules (who can approve what, the £85,000 reimbursement cap, never refusing a vulnerable customer) are enforced in code that no model can override. A manager's quick check of the agent's reasoning also uses Laya; when that check is unclear, a larger model takes a closer look.</p>
        <p data-testid="about-numbers" className="text-slate-500 dark:text-slate-400">
          So far: {count(total, "customer choice", "customer choices")}, {total ? pct((life.decided_by_laya ?? 0) / total) : "0%"} by Laya{life.laya_avg_ms ? ` (about ${Math.round(life.laya_avg_ms)} ms each)` : ""}{life.decided_by_rules ? ", the rest by simple rules when it was unsure or busy" : ""}. None of them use cloud AI.
          {" "}Manager decisions: {count(judged.laya, "quick check", "quick checks")} · {count(judged.llm, "closer review", "closer reviews")} · {num(judged.rules)} by standard rules.
          {" "}The world opens at most {num(life.cases_per_hour)} cases an hour on its own ({num(life.cases_opened)} so far), because each one uses real agent time.
        </p>
      </div>
    </details>
  );
}
