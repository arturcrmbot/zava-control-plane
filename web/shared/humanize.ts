/**
 * Single source of truth for plain-English labels of orchestration vocabulary.
 *
 * The runtime emits technical names like `executor.agent_kyc_diligence_checker`,
 * `gen_ai.generate_content`, or `validate_budget_schema`. Any UI surface that
 * shows these to a non-technical reader (workflow drawer, fleet rail, cosmic
 * lens flashes, …) MUST go through `humanizeLabel()` — that way wording stays
 * consistent and we have one place to add a new agent's friendly name.
 *
 * To add wording for a new agent / executor / tool: add an entry to
 * `EXECUTOR_OVERRIDES` below, keyed by the trailing label (without the
 * `executor.` prefix). If the suffix-verb fallback already produces an
 * acceptable phrase, you do not need an override.
 *
 * See `docs/visualisation.md` § "Visualisation Contributor Guide" →
 * "To add wording for a new
 * agent or executor" for the contributor checklist.
 */

// --- public API ------------------------------------------------------------

export interface HumanLabel {
  /** Short sentence: "Drafted the job description". */
  text: string;
  /** Who did it: "AI agent", "AI", "System", "Workflow", "Orchestrator", or a persona name. */
  who: string;
}

/** Convert any orchestration label into plain English + an actor descriptor. */
export function humanizeLabel(rawLabel: string): HumanLabel {
  if (!rawLabel) return { text: "Unknown step", who: "System" };

  // Lifecycle.
  if (rawLabel === "workflow.started") return { text: "Workflow started", who: "Orchestrator" };
  if (rawLabel === "suspended")        return { text: "Paused — waiting for a person", who: "Orchestrator" };
  if (rawLabel === "resumed")          return { text: "Resumed", who: "Orchestrator" };

  // phase.completed:Foo → "Foo complete"
  if (rawLabel.startsWith("phase.completed:")) {
    return { text: `${rawLabel.slice("phase.completed:".length)} complete`, who: "Workflow" };
  }

  return { text: humanizeExecutor(rawLabel), who: whoForExecutor(rawLabel) };
}

/** True when the label is a schema validator (folded away when passing). */
export function isValidatorLabel(label: string): boolean {
  return /^(executor\.)?validate_.+_schema$/.test(label);
}

/** Pretty noun for the validator's target (used in failure messages). */
export function validatorTarget(label: string): string {
  return prettyNoun(
    label
      .replace(/^executor\./, "")
      .replace(/^validate_/, "")
      .replace(/_schema$/, ""),
  );
}

// --- override map ----------------------------------------------------------
// Add an entry whenever the auto-generated phrase is awkward. Key is the label
// WITHOUT the `executor.` prefix.

export const EXECUTOR_OVERRIDES: Record<string, string> = {
  // Generic
  "gen_ai.generate_content":                "AI drafted text",

  // Hiring
  "agent_budget_checker":                   "Checked the budget",
  "agent_jd_drafter":                       "Drafted the job description",
  "agent_sourcing_orchestrator":            "Sourced candidates",
  "agent_cv_crystalliser":                  "Refined candidate profiles",
  "agent_auto_shortlister":                 "Auto-shortlisted candidates",
  "agent_voice_screener":                   "Screened candidate by voice",

  // Vendor KYC
  "deterministic_vendor_intake":            "Captured vendor details",
  "agent_kyc_diligence_checker":            "Ran KYC diligence checks",
  "agent_ubo_resolver":                     "Resolved ultimate beneficial owners",

  // Contract renewal
  "deterministic_contract_lookup":          "Looked up the contract",
  "agent_market_benchmarker":               "Compared against market rates",
  "agent_renewal_terms_drafter":            "Drafted renewal terms",

  // Performance review
  "agent_calibration_drafter":              "Drafted the calibration",
  "agent_perf_review_drafter":              "Drafted the performance review",
  // Creative brief / campaign
  "agent_brief_synthesiser":               "Synthesised the creative brief",
  "agent_insight_audience":                "Analysed the audience insights",
  "agent_concept_curator":                 "Curated creative concepts",
  "agent_brand_guardian":                  "Reviewed against brand guidelines",
  "agent_storyboard_curator":              "Built the storyboard",

  // IT access
  "agent_rbac_resolver":                   "Resolved access permissions",
  "agent_risk_assessor":                   "Assessed access risk",

  // Invoice / PO
  "deterministic_invoice_lookup":          "Looked up the invoice",
  "deterministic_po_lookup":               "Looked up the purchase order",
  "deterministic_employee_lookup":         "Looked up the employee record",
  "deterministic_supplier_check":          "Checked the supplier",
  "deterministic_three_way_match":         "Matched invoice, PO and receipt",
  "deterministic_authority_resolve":       "Resolved approval authority",};

// --- naming -> phrase ------------------------------------------------------

const SUFFIX_VERBS: Array<[RegExp, (rest: string) => string]> = [
  [/_checker$/,                             (r) => `Checked ${r}`],
  [/_drafter$/,                             (r) => `Drafted ${r}`],
  [/_lookup$/,                              (r) => `Looked up ${r}`],
  [/_resolver$/,                            (r) => `Resolved ${r}`],
  [/_resolve$/,                             (r) => `Resolved ${r}`],
  [/_screener$/,                            (r) => `Screened ${r}`],
  [/_shortlister$/,                         (r) => `Shortlisted ${r}`],
  [/_(crystalliser|crystallizer)$/,         (r) => `Refined ${r}`],
  [/_benchmarker$/,                         (r) => `Benchmarked ${r}`],
  [/_orchestrator$/,                        (r) => `Coordinated ${r}`],
  [/_(validator|validate)$/,                (r) => `Validated ${r}`],
  [/_classifier$/,                          (r) => `Classified ${r}`],
  [/_extractor$/,                           (r) => `Extracted ${r}`],
  [/_(summarizer|summariser)$/,             (r) => `Summarised ${r}`],
  [/_router$/,                              (r) => `Routed ${r}`],
  [/_dispatcher$/,                          (r) => `Dispatched ${r}`],
  [/_scorer$/,                              (r) => `Scored ${r}`],
  [/_(generator|generate)$/,                (r) => `Generated ${r}`],
  [/_parser$/,                              (r) => `Parsed ${r}`],
  [/_matcher$/,                             (r) => `Matched ${r}`],
  [/_match$/,                               (r) => `Matched ${r}`],
  [/_(synthesiser|synthesizer)$/,           (r) => `Synthesised ${r}`],
  [/_curator$/,                             (r) => `Curated ${r}`],
  [/_guardian$/,                            (r) => `Reviewed ${r}`],
  [/_assessor$/,                            (r) => `Assessed ${r}`],
  [/_check$/,                               (r) => `Checked ${r}`],
  [/_intake$/,                              (r) => `${titleCase(r)} intake`],
];

function humanizeExecutor(rawLabel: string): string {
  const stripped = rawLabel.startsWith("executor.")
    ? rawLabel.slice("executor.".length)
    : rawLabel;

  const override = EXECUTOR_OVERRIDES[stripped] ?? EXECUTOR_OVERRIDES[rawLabel];
  if (override) return override;

  if (isValidatorLabel(stripped)) return `Checked ${validatorTarget(stripped)}`;
  if (stripped.startsWith("gen_ai.")) return "AI generated something";

  const body = stripped.replace(/^agent_/, "").replace(/^deterministic_/, "");
  for (const [rx, fn] of SUFFIX_VERBS) {
    if (rx.test(body)) {
      const rest = body.replace(rx, "");
      return fn(prettyNoun(rest));
    }
  }
  // Final fallback: full title-case so the first word is capitalised
  // ("Brief Synthesiser ran", not "brief Synthesiser ran").
  return `${titleCase(body)} ran`;
}

function whoForExecutor(rawLabel: string): string {
  if (rawLabel.startsWith("gen_ai.")) return "AI";
  if (rawLabel.includes("deterministic_")) return "System";
  return "AI agent";
}

// --- string helpers --------------------------------------------------------

const ABBREV = new Set(["KYC", "UBO", "JD", "CV", "SLA", "AI", "ID", "API", "URL", "PDF", "MCP", "HR", "BP"]);

export function titleCase(snake: string): string {
  return snake
    .split(/[._\s-]+/)
    .filter(Boolean)
    .map((w) => (ABBREV.has(w.toUpperCase()) ? w.toUpperCase() : w[0].toUpperCase() + w.slice(1)))
    .join(" ");
}

/** Title-case but lower-case the first word so it reads naturally inside a sentence. */
export function prettyNoun(snake: string): string {
  const tc = titleCase(snake);
  if (!tc) return "";
  const [first, ...rest] = tc.split(" ");
  const head = ABBREV.has(first.toUpperCase()) ? first.toUpperCase() : first.toLowerCase();
  return [head, ...rest].join(" ");
}

/**
 * Plain-English labels for every persona role id.
 *
 * Source of truth: `api/server/personae/<role>/SKILL.md` (each role's
 * frontmatter `description`). The auto title-cased fallback (e.g.
 * `cpo` → "Cpo", `gc` → "Gc") is unreadable, so any persona surfaced in the
 * UI MUST get an explicit label here.
 *
 * The keys cover both the live persona catalogue under `api/server/personae/`
 * and the canonical fallback list in `api/server/routes/cities.py`
 * (`_gather_personas`) so every role id the city roster can emit resolves.
 *
 * To add a new persona: drop the role id below with a label that reads as
 * a job title. Keep wording aligned with each persona's SKILL.md description.
 */
export const PERSONA_LABELS: Record<string, string> = {
  // --- live personae (api/server/personae/*) ---
  account_director:           "Account Director",
  ap_clerk:                   "AP Clerk",
  candidate:                  "Candidate",
  category_manager:           "Category Manager",
  cfo:                        "CFO",
  change_manager:             "Change Manager",
  claim_submitter:            "Claim Submitter",
  comp_ben_analyst:           "Comp & Ben Analyst",
  contract_finance_bp:        "Contract Finance BP",
  contract_line_manager:      "Contract Line Manager",
  contracts_counsel:          "Contracts Counsel",
  controller:                 "Controller",
  cpo:                        "Chief Procurement Officer",
  creative_director:          "Creative Director",
  dpo:                        "Data Protection Officer",
  finance_bp:                 "Finance BP",
  finance_controller:         "Finance Controller",
  fpa_analyst:                "FP&A Analyst",
  gc:                         "General Counsel",
  hr_bp:                      "HR BP",
  it_access_it_admin:         "IT Admin (Access)",
  it_access_line_manager:     "Line Manager (IT Access)",
  line_manager:               "Line Manager",
  onboarding_it_admin:        "IT Admin (Onboarding)",
  perf_review_hr_bp:          "HR BP (Performance Review)",
  perf_review_line_manager:   "Line Manager (Performance Review)",
  project_manager:            "Project Manager",
  recruiter:                  "Recruiter",
  sourcing_lead:              "Sourcing Lead",
  ssc_reviewer:               "SSC Reviewer",
  treasurer:                  "Treasurer",
  vendor_kyc_finance_bp:      "Finance BP (Vendor KYC)",

  // --- canonical fallback roster (api/server/routes/cities.py) ---
  brand_steward:              "Brand Steward",
  campaign_manager:           "Campaign Manager",
  cdo:                        "Chief Data Officer",
  ceo:                        "CEO",
  chro:                       "Chief HR Officer",
  cmo:                        "Chief Marketing Officer",
  compliance_officer:         "Compliance Officer",
  coo:                        "COO",
  cto:                        "CTO",
  general_counsel:            "General Counsel",
  hiring_manager:             "Hiring Manager",
  interviewer:                "Interviewer",
  legal_counsel:              "Legal Counsel",
  people_partner:             "People Partner",
  policy_owner:               "Policy Owner",
  support_lead:               "Support Lead",
  talent_lead:                "Talent Lead",
  vendor_owner:               "Vendor Owner",
};

/**
 * "finance_bp" → "Finance BP". Used for persona / actor display.
 *
 * Consults `PERSONA_LABELS` first so role ids that don't title-case nicely
 * (`cpo`, `gc`, `fpa_analyst`, `comp_ben_analyst`, …) still render as the
 * job title a non-technical reader expects. Falls back to `titleCase` for
 * unknown actors so callers passing arbitrary strings keep working.
 */
export function prettyActor(actor: string): string {
  if (!actor) return "";
  const key = actor.toLowerCase();
  if (PERSONA_LABELS[key]) return PERSONA_LABELS[key];
  return titleCase(actor);
}

/** "+45ms", "+12s", "+1m 4s", "+2h 15m" — workflow-relative time. */
export function formatOffset(sec: number): string {
  if (sec <= 0) return "+0ms";
  if (sec < 1) return `+${Math.round(sec * 1000)}ms`;
  if (sec < 60) return `+${Math.round(sec)}s`;
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  if (m < 60) return s ? `+${m}m ${s}s` : `+${m}m`;
  const h = Math.floor(m / 60);
  const rem = m % 60;
  return rem ? `+${h}h ${rem}m` : `+${h}h`;
}

/**
 * Plain-English labels for every workflow_type id registered in the API.
 *
 * Source of truth: each `Domain.workflow_type` in `api/shared/domains.py`.
 * Any UI surface that shows a workflow_type to a non-technical reader (the
 * cosmic lens workflow drawer, fleet rail, etc.) MUST go through
 * `humanWorkflowType()` so wording stays consistent and we have one place
 * to add a new domain's friendly name.
 *
 * To add a new domain: drop the workflow_type id below with a label that
 * reads as a sentence noun ("Vendor KYC", not "vendor-kyc").
 */
export const WORKFLOW_TYPE_LABELS: Record<string, string> = {
  "expense-claim":        "Expense claim",
  "hiring":               "Hiring",
  "travel-preapproval":   "Travel pre-approval",
  "vendor-kyc":           "Vendor KYC",
  "employee-onboarding":  "Employee onboarding",
  "it-access-request":    "IT access request",
  "contract-renewal":     "Contract renewal",
  "perf-review":          "Performance review",
  "ap-invoice":           "AP invoice",
  "purchase-order":       "Purchase order",
  "contract-review":      "Contract review",
  "privacy-dpia":         "Privacy DPIA",
  "treasury-fx":          "Treasury FX",
  "creative-campaign":    "Creative campaign",
  "hire-to-productive":   "Hire to productive",
  "vendor-risk-to-pay":   "Vendor risk to pay",
  "lead-to-cash":         "Lead to cash",
  "fy-close":             "FY close",
  "board-prep":           "Board prep",
};

/**
 * "vendor-kyc" → "Vendor KYC". Falls back to a Title-Cased version of the
 * raw id (with hyphens treated like underscores) so unregistered workflow
 * types still render readably instead of as a raw kebab-case slug.
 */
export function humanWorkflowType(workflowType: string | undefined | null): string {
  if (!workflowType) return "Unknown workflow";
  const known = WORKFLOW_TYPE_LABELS[workflowType];
  if (known) return known;
  return titleCase(workflowType.replace(/-/g, "_"));
}

/**
 * Plain-English age for a duration in seconds since a workflow started.
 *
 * Examples: 0 → "just started", 12 → "12s old", 305 → "5m old",
 * 4500 → "1h 15m old", 90000 → "1d 1h old". Designed for compact metadata
 * rows (workflow drawer, fleet rail) — the returned string already includes
 * the trailing "old" / "started" so callers can drop it straight into a row.
 */
export function formatAge(seconds: number | undefined | null): string {
  if (seconds === undefined || seconds === null || !Number.isFinite(seconds) || seconds < 1) {
    return "just started";
  }
  const s = Math.floor(seconds);
  if (s < 60) return `${s}s old`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m old`;
  const h = Math.floor(m / 60);
  const remM = m % 60;
  if (h < 24) return remM ? `${h}h ${remM}m old` : `${h}h old`;
  const d = Math.floor(h / 24);
  const remH = h % 24;
  return remH ? `${d}d ${remH}h old` : `${d}d old`;
}

/**
 * Plain-English labels for every relationship type stored in the entity graph.
 *
 * Source of truth: `_REL_TABLES` and `_DECIDED_REL_BY_KIND` in
 * `api/server/services/entity_graph.py`. Any UI surface that shows a raw
 * relationship name to a non-technical reader (city drawer, entity drawer,
 * cosmic lens flashes, …) MUST go through `humanRelationship()` so wording
 * stays consistent.
 *
 * Each label is a verb phrase that fits the sentence "X <label> Y", e.g.
 * "Person OWNS Asset" → "owns".
 */
export const RELATIONSHIP_LABELS: Record<string, string> = {
  EMPLOYED_BY:      "employed by",
  MANAGES:          "manages",
  OWNS:             "owns",
  TRANSACTS:        "transacts with",
  BELONGS_TO:       "belongs to",
  LOCATED_IN:       "located in",
  DECIDED_ON:       "decided about",
  DECIDED_PERSON:   "decided about",
  DECIDED_MONEY:    "decided about",
  DECIDED_ASSET:    "decided about",
  DECIDED_ORG:      "decided about",
  DECIDED_PERIOD:   "decided about",
  DECIDED_PLACE:    "decided about",
  PRECEDENT_OF:     "precedent of",
  TOUCHED:          "touched",
  SUB_WORKFLOW_OF:  "sub-workflow of",
  // pitch-e1: agency-domain rels
  BRAND_OF:         "represents",
  CAMPAIGN_FOR:     "campaign for",
  EXECUTED_BY:      "executed by",
  SUPPLIED_BY:      "supplied by",
  PITCH_FOR:        "pitched to",
  RESULTED_IN:      "resulted in",
  PART_OF:          "part of",
  DECIDED_BRAND:    "decided about",
  DECIDED_CAMPAIGN: "decided about",
  DECIDED_PITCH:    "decided about",
  DECIDED_MEDIAPLAN:"decided about",
  DECIDED_SUBSIDIARY:"decided about",
};

/**
 * "DECIDED_PERSON" → "decided about". Falls back to a lower-cased, snake-free
 * form of the raw rel name so unregistered relationships still read as plain
 * English ("MET_WITH" → "met with") rather than as a SHOUTING_SCHEMA_TOKEN.
 */
export function humanRelationship(rel: string | undefined | null): string {
  if (!rel) return "linked to";
  const known = RELATIONSHIP_LABELS[rel.toUpperCase()];
  if (known) return known;
  return rel.toLowerCase().replace(/_/g, " ");
}

/**
 * Plain-English singular + plural pair for every entity kind shipped in the
 * graph schema (`_NODE_TABLES` in `api/server/services/entity_graph.py`).
 *
 * Used by `pluralize()` so a `partner_kind` like "Person" renders as
 * "1 person" / "5 people" rather than the raw schema-cased "Person"/"Persons".
 */
export const ENTITY_KIND_NOUNS: Record<string, { singular: string; plural: string }> = {
  Person:        { singular: "person",       plural: "people" },
  Organisation:  { singular: "organisation", plural: "organisations" },
  Asset:         { singular: "asset",        plural: "assets" },
  Money:         { singular: "money record", plural: "money records" },
  Decision:      { singular: "decision",     plural: "decisions" },
  Place:         { singular: "place",        plural: "places" },
  Period:        { singular: "period",       plural: "periods" },
  Workflow:      { singular: "workflow",     plural: "workflows" },
  // pitch-e1: agency-domain kinds
  Brand:         { singular: "brand",        plural: "brands" },
  Campaign:      { singular: "campaign",     plural: "campaigns" },
  Pitch:         { singular: "pitch",        plural: "pitches" },
  MediaPlan:     { singular: "media plan",   plural: "media plans" },
  Subsidiary:    { singular: "subsidiary",   plural: "subsidiaries" },
};

/**
 * Render `count` together with the right form of `noun`. Looks up
 * `ENTITY_KIND_NOUNS` first so schema kinds get their irregular plurals
 * ("1 person" / "2 people"). Otherwise applies a simple `s` / `es` rule.
 *
 * Examples:
 *   pluralize(1, "Person")    → "1 person"
 *   pluralize(3, "Person")    → "3 people"
 *   pluralize(2, "workflow")  → "2 workflows"
 *   pluralize(1, "match")     → "1 match"
 *   pluralize(2, "match")     → "2 matches"
 */
export function pluralize(count: number, noun: string, pluralOverride?: string): string {
  const known = ENTITY_KIND_NOUNS[noun];
  if (known) {
    return `${count} ${count === 1 ? known.singular : known.plural}`;
  }
  if (count === 1) return `${count} ${noun}`;
  const plural = pluralOverride ?? defaultPlural(noun);
  return `${count} ${plural}`;
}

function defaultPlural(noun: string): string {
  if (/(s|x|z|ch|sh)$/i.test(noun)) return `${noun}es`;
  if (/[^aeiou]y$/i.test(noun)) return `${noun.slice(0, -1)}ies`;
  return `${noun}s`;
}

/**
 * Short verb-phrase noun for an entity kind, used in drawer subtitles and
 * narrative copy. e.g. "Person" → "Person record", "Invoice" → "Invoice
 * record". Falls back to "<Title> record" so unknown kinds still read as
 * plain English instead of leaking the raw schema token.
 */
/** Per-kind override for `kindToVerb` so multi-word schema kinds (e.g.
 *  `MediaPlan`) render with proper spacing instead of "Mediaplan". */
const KIND_VERB_OVERRIDES: Record<string, string> = {
  Brand:      "Brand",
  Campaign:   "Campaign",
  Pitch:      "Pitch",
  MediaPlan:  "Media plan",
  Subsidiary: "Subsidiary",
};

export function kindToVerb(kind: string | undefined | null): string {
  if (!kind) return "Record";
  const k = kind.trim();
  if (!k) return "Record";
  const label = KIND_VERB_OVERRIDES[k] ?? titleCase(k);
  return `${label} record`;
}

/**
 * Plain-English age for a wallclock millisecond timestamp, suitable for
 * "created 5m ago" / "touched 2h ago" rows. Returns "just now" for very
 * recent (<5s) timestamps and falls back to a short ISO date for anything
 * older than ~30 days.
 */
export function formatRelative(targetMs: number | undefined | null, nowMs: number = Date.now()): string {
  if (targetMs === undefined || targetMs === null || !Number.isFinite(targetMs)) return "";
  const diff = Math.max(0, Math.floor((nowMs - targetMs) / 1000));
  if (diff < 5) return "just now";
  if (diff < 60) return `${diff}s ago`;
  const m = Math.floor(diff / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 30) return `${d}d ago`;
  const date = new Date(targetMs);
  return date.toISOString().slice(0, 10);
}

/** Verb form for a persona decision verdict. */
export function verdictVerb(verdict: string): string {
  const map: Record<string, string> = {
    approve:        "approved",
    reject:         "rejected",
    needs_more_info: "asked for more information on",
    escalate:       "escalated",
    hold:           "put on hold",
  };
  return map[verdict] ?? verdict;
}
