import { describe, expect, it } from "vitest";
import {
  EXECUTOR_OVERRIDES,
  ENTITY_KIND_NOUNS,
  PERSONA_LABELS,
  RELATIONSHIP_LABELS,
  WORKFLOW_TYPE_LABELS,
  formatAge,
  formatOffset,
  formatRelative,
  humanRelationship,
  humanWorkflowType,
  humanizeLabel,
  isValidatorLabel,
  kindToVerb,
  pluralize,
  prettyActor,
  prettyNoun,
  titleCase,
  validatorTarget,
  verdictVerb,
} from "../humanize";

describe("humanizeLabel", () => {
  it("never echoes a raw snake_case or dotted id back to callers", () => {
    // Default branch invariant relied on by labelForCapability/labelForEntity:
    // an unknown event type must still produce a humanized string different
    // from the raw id, so raw `executor.*` / `entity.*` / `tool.*` /
    // `workflow.*` / `persona.*` ids never reach the activity rail unchanged.
    for (const raw of [
      "entity.something_new",
      "tool.unheard_of",
      "workflow.brand_new_lifecycle",
      "executor.unknown_agent_lookup",
      "persona.peeking",
    ]) {
      const { text } = humanizeLabel(raw);
      expect(text, raw).not.toBe(raw);
      expect(text.length, raw).toBeGreaterThan(0);
      // No bare snake_case word should survive — every `_` must be gone.
      expect(text, raw).not.toMatch(/_/);
    }
  });
});

describe("prettyActor", () => {
  it("resolves persona role ids via PERSONA_LABELS", () => {
    expect(prettyActor("cpo")).toBe("Chief Procurement Officer");
    expect(prettyActor("gc")).toBe("General Counsel");
    expect(prettyActor("dpo")).toBe("Data Protection Officer");
    expect(prettyActor("fpa_analyst")).toBe("FP&A Analyst");
    expect(prettyActor("comp_ben_analyst")).toBe("Comp & Ben Analyst");
    expect(prettyActor("vendor_kyc_finance_bp")).toBe("Finance BP (Vendor KYC)");
  });

  it("is case-insensitive on the persona key", () => {
    expect(prettyActor("CPO")).toBe("Chief Procurement Officer");
    expect(prettyActor("Hr_Bp")).toBe("HR BP");
  });

  it("falls back to title-case for unknown actors", () => {
    expect(prettyActor("some_other_role")).toBe("Some Other Role");
    expect(prettyActor("kyc_owner")).toBe("KYC Owner");
  });

  it("returns empty string for empty input", () => {
    expect(prettyActor("")).toBe("");
  });

  it("covers every persona shipped in api/server/personae", () => {
    // Spot-check the live roster ids — if a new persona lands without a label,
    // this list catches the regression and the catalogue stays in sync.
    const liveRoster = [
      "account_director", "ap_clerk", "candidate", "category_manager", "cfo",
      "change_manager", "claim_submitter", "comp_ben_analyst",
      "contract_finance_bp", "contract_line_manager", "contracts_counsel",
      "controller", "cpo", "creative_director", "dpo", "finance_bp",
      "finance_controller", "fpa_analyst", "gc", "hr_bp", "it_access_it_admin",
      "it_access_line_manager", "line_manager", "onboarding_it_admin",
      "perf_review_hr_bp", "perf_review_line_manager", "project_manager",
      "recruiter", "sourcing_lead", "ssc_reviewer", "treasurer",
      "vendor_kyc_finance_bp",
    ];
    for (const role of liveRoster) {
      expect(PERSONA_LABELS[role], `missing label for ${role}`).toBeTruthy();
    }
  });
});

describe("PERSONA_LABELS catalogue", () => {
  it("has a non-empty title-case label for every entry", () => {
    for (const [key, label] of Object.entries(PERSONA_LABELS)) {
      expect(label, `empty label for ${key}`).toBeTruthy();
      // First non-whitespace character of each space-separated word should be
      // upper case OR a digit OR an open paren — these are job titles, not
      // sentences. Punctuation tokens (&) get skipped.
      const firstChar = label.trim()[0];
      expect(/[A-Z0-9(]/.test(firstChar), `${key} → ${label}`).toBe(true);
    }
  });

  it("renders representative roles exactly as designed", () => {
    expect(PERSONA_LABELS.cpo).toBe("Chief Procurement Officer");
    expect(PERSONA_LABELS.cfo).toBe("CFO");
    expect(PERSONA_LABELS.fpa_analyst).toBe("FP&A Analyst");
    expect(PERSONA_LABELS.dpo).toBe("Data Protection Officer");
  });
});

describe("humanizeLabel branches", () => {
  it("returns the unknown-step default for empty input", () => {
    expect(humanizeLabel("")).toEqual({ text: "Unknown step", who: "System" });
  });

  it("handles workflow lifecycle labels", () => {
    expect(humanizeLabel("workflow.started")).toEqual({
      text: "Workflow started",
      who: "Orchestrator",
    });
    expect(humanizeLabel("suspended")).toEqual({
      text: "Paused — waiting for a person",
      who: "Orchestrator",
    });
    expect(humanizeLabel("resumed")).toEqual({ text: "Resumed", who: "Orchestrator" });
  });

  it("formats `phase.completed:Foo` as `Foo complete` by Workflow", () => {
    expect(humanizeLabel("phase.completed:Sourcing")).toEqual({
      text: "Sourcing complete",
      who: "Workflow",
    });
  });

  it("uses EXECUTOR_OVERRIDES with or without the `executor.` prefix", () => {
    expect(humanizeLabel("agent_jd_drafter").text).toBe("Drafted the job description");
    expect(humanizeLabel("executor.agent_jd_drafter").text).toBe(
      "Drafted the job description",
    );
  });

  it("treats `executor.validate_*_schema` as a passing schema check", () => {
    expect(humanizeLabel("executor.validate_offer_letter_schema")).toEqual({
      text: "Checked offer Letter",
      who: "AI agent",
    });
  });

  it("renders `gen_ai.*` labels as the AI generic", () => {
    expect(humanizeLabel("gen_ai.generate_content")).toEqual({
      text: "AI drafted text",
      who: "AI",
    });
    expect(humanizeLabel("gen_ai.something_brand_new")).toEqual({
      text: "AI generated something",
      who: "AI",
    });
  });

  it("applies suffix-verb rules in `whoForExecutor`", () => {
    expect(humanizeLabel("agent_offer_drafter")).toEqual({
      text: "Drafted offer",
      who: "AI agent",
    });
    expect(humanizeLabel("deterministic_employee_lookup").who).toBe("System");
    expect(humanizeLabel("agent_unknown_resolver").text).toBe("Resolved unknown");
    expect(humanizeLabel("agent_brief_synthesiser").text).toBe(
      "Synthesised the creative brief",
    );
    // Without override: synth verb fallback keeps reading naturally.
    expect(humanizeLabel("agent_offer_synthesizer").text).toBe("Synthesised offer");
    expect(humanizeLabel("agent_data_classifier").text).toBe("Classified data");
    expect(humanizeLabel("agent_event_dispatcher").text).toBe("Dispatched event");
  });

  it("falls back to `<Title> ran` for unknown executors", () => {
    expect(humanizeLabel("agent_some_brand_new_thing")).toEqual({
      text: "Some Brand New Thing ran",
      who: "AI agent",
    });
  });

  it("never echoes a raw snake_case or dotted id back to callers", () => {
    for (const raw of [
      "entity.something_new",
      "tool.unheard_of",
      "workflow.brand_new_lifecycle",
      "executor.unknown_agent_lookup",
      "persona.peeking",
    ]) {
      const { text } = humanizeLabel(raw);
      expect(text, raw).not.toBe(raw);
      expect(text.length, raw).toBeGreaterThan(0);
      expect(text, raw).not.toMatch(/_/);
    }
  });
});

describe("validator helpers", () => {
  it("recognises validator labels with or without prefix", () => {
    expect(isValidatorLabel("validate_offer_schema")).toBe(true);
    expect(isValidatorLabel("executor.validate_offer_schema")).toBe(true);
    expect(isValidatorLabel("agent_jd_drafter")).toBe(false);
  });

  it("turns a validator label into a pretty noun target", () => {
    expect(validatorTarget("executor.validate_kyc_schema")).toBe("KYC");
    expect(validatorTarget("validate_purchase_order_schema")).toBe("purchase Order");
  });
});

describe("titleCase / prettyNoun", () => {
  it("upper-cases every recognised abbreviation", () => {
    expect(titleCase("kyc_owner")).toBe("KYC Owner");
    expect(titleCase("api_url")).toBe("API URL");
  });
  it("title-cases plain snake_case", () => {
    expect(titleCase("some_other_role")).toBe("Some Other Role");
  });
  it("title-cases dotted identifiers", () => {
    expect(titleCase("tool.unheard_of")).toBe("Tool Unheard Of");
  });
  it("returns empty for empty input", () => {
    expect(titleCase("")).toBe("");
    expect(prettyNoun("")).toBe("");
  });
  it("lower-cases the first word for in-sentence use", () => {
    expect(prettyNoun("purchase_order")).toBe("purchase Order");
    expect(prettyNoun("kyc_check")).toBe("KYC Check");
  });
});

describe("WORKFLOW_TYPE_LABELS + humanWorkflowType", () => {
  // Pulled from api/shared/domains.py — keep in sync with the registered
  // workflow_type values.
  const REGISTERED = [
    "expense-claim", "hiring", "travel-preapproval", "vendor-kyc",
    "employee-onboarding", "it-access-request", "contract-renewal",
    "perf-review", "ap-invoice", "purchase-order", "contract-review",
    "privacy-dpia", "treasury-fx", "creative-campaign", "hire-to-productive",
    "vendor-risk-to-pay", "lead-to-cash", "fy-close", "board-prep",
  ];

  it("has a label for every workflow_type registered in the API", () => {
    for (const wt of REGISTERED) {
      expect(WORKFLOW_TYPE_LABELS[wt], `missing label for ${wt}`).toBeTruthy();
      expect(humanWorkflowType(wt)).toBe(WORKFLOW_TYPE_LABELS[wt]);
    }
  });

  it("falls back to title-case for unregistered workflow types", () => {
    expect(humanWorkflowType("brand-new-process")).toBe("Brand New Process");
    expect(humanWorkflowType("kyc-refresh")).toBe("KYC Refresh");
  });

  it("returns an explicit string for null/empty input", () => {
    expect(humanWorkflowType(undefined)).toBe("Unknown workflow");
    expect(humanWorkflowType(null)).toBe("Unknown workflow");
    expect(humanWorkflowType("")).toBe("Unknown workflow");
  });
});

describe("formatAge", () => {
  it("renders `just started` for 0s, sub-second, and missing values", () => {
    expect(formatAge(0)).toBe("just started");
    expect(formatAge(0.5)).toBe("just started");
    expect(formatAge(undefined)).toBe("just started");
    expect(formatAge(null)).toBe("just started");
    expect(formatAge(Number.NaN)).toBe("just started");
  });

  it("renders seconds, minutes, hours and days", () => {
    expect(formatAge(30)).toBe("30s old");
    expect(formatAge(5 * 60)).toBe("5m old");
    expect(formatAge(60 * 60)).toBe("1h old");
    expect(formatAge(60 * 60 + 15 * 60)).toBe("1h 15m old");
    expect(formatAge(24 * 60 * 60)).toBe("1d old");
    expect(formatAge(25 * 60 * 60)).toBe("1d 1h old");
  });

  it("treats negative / future values gracefully (no NaN, no negatives)", () => {
    expect(formatAge(-10)).toBe("just started");
  });
});

describe("formatOffset", () => {
  it("returns +0ms for non-positive input", () => {
    expect(formatOffset(0)).toBe("+0ms");
    expect(formatOffset(-3)).toBe("+0ms");
  });
  it("renders sub-second, second, minute, and hour offsets", () => {
    expect(formatOffset(0.123)).toBe("+123ms");
    expect(formatOffset(12)).toBe("+12s");
    expect(formatOffset(64)).toBe("+1m 4s");
    expect(formatOffset(120)).toBe("+2m");
    expect(formatOffset(2 * 3600 + 15 * 60)).toBe("+2h 15m");
    expect(formatOffset(2 * 3600)).toBe("+2h");
  });
});

describe("verdictVerb", () => {
  it("maps known verdicts to past-tense verbs", () => {
    expect(verdictVerb("approve")).toBe("approved");
    expect(verdictVerb("reject")).toBe("rejected");
    expect(verdictVerb("needs_more_info")).toBe("asked for more information on");
  });
  it("falls back to the raw verdict for unknowns", () => {
    expect(verdictVerb("waffle")).toBe("waffle");
  });
});

describe("EXECUTOR_OVERRIDES catalogue", () => {
  it("never has an empty override phrase", () => {
    for (const [key, value] of Object.entries(EXECUTOR_OVERRIDES)) {
      expect(value, `empty override for ${key}`).toBeTruthy();
    }
  });
});

describe("humanRelationship", () => {
  it("maps every registered relationship to a verb phrase", () => {
    for (const [rel, expected] of Object.entries(RELATIONSHIP_LABELS)) {
      expect(humanRelationship(rel)).toBe(expected);
    }
  });
  it("is case-insensitive on the relationship key", () => {
    expect(humanRelationship("employed_by")).toBe("employed by");
  });
  it("falls back to a lower-cased snake-free form for unknowns", () => {
    expect(humanRelationship("MET_WITH")).toBe("met with");
  });
  it("returns a safe default for empty input", () => {
    expect(humanRelationship(undefined)).toBe("linked to");
    expect(humanRelationship(null)).toBe("linked to");
    expect(humanRelationship("")).toBe("linked to");
  });
});

describe("pluralize", () => {
  it("uses the irregular plural for known entity kinds", () => {
    expect(pluralize(1, "Person")).toBe("1 person");
    expect(pluralize(5, "Person")).toBe("5 people");
    expect(pluralize(1, "Money")).toBe("1 money record");
    expect(pluralize(2, "Money")).toBe("2 money records");
  });
  it("applies the default `s` / `es` rule for unknown nouns", () => {
    expect(pluralize(1, "workflow")).toBe("1 workflow");
    expect(pluralize(2, "workflow")).toBe("2 workflows");
    expect(pluralize(2, "match")).toBe("2 matches");
    expect(pluralize(2, "city")).toBe("2 cities");
  });
  it("honours an explicit plural override", () => {
    expect(pluralize(2, "person", "persons")).toBe("2 persons");
  });
  it("has an irregular noun for every shipped entity kind", () => {
    for (const [kind, forms] of Object.entries(ENTITY_KIND_NOUNS)) {
      expect(forms.singular, `singular for ${kind}`).toBeTruthy();
      expect(forms.plural, `plural for ${kind}`).toBeTruthy();
    }
  });
});

describe("kindToVerb", () => {
  it("renders `<Title> record` for known kinds", () => {
    expect(kindToVerb("Person")).toBe("Person record");
    expect(kindToVerb("organisation")).toBe("Organisation record");
  });
  it("falls back to plain `Record` for empty input", () => {
    expect(kindToVerb(undefined)).toBe("Record");
    expect(kindToVerb(null)).toBe("Record");
    expect(kindToVerb("")).toBe("Record");
    expect(kindToVerb("   ")).toBe("Record");
  });
});

describe("formatRelative", () => {
  const NOW = 1_700_000_000_000;

  it("returns `just now` for very recent timestamps", () => {
    expect(formatRelative(NOW - 1_000, NOW)).toBe("just now");
    expect(formatRelative(NOW, NOW)).toBe("just now");
  });
  it("renders seconds, minutes, hours, and days ago", () => {
    expect(formatRelative(NOW - 30_000, NOW)).toBe("30s ago");
    expect(formatRelative(NOW - 5 * 60_000, NOW)).toBe("5m ago");
    expect(formatRelative(NOW - 3 * 3_600_000, NOW)).toBe("3h ago");
    expect(formatRelative(NOW - 2 * 86_400_000, NOW)).toBe("2d ago");
  });
  it("falls back to an ISO date for anything older than 30d", () => {
    const old = NOW - 60 * 86_400_000;
    expect(formatRelative(old, NOW)).toBe(new Date(old).toISOString().slice(0, 10));
  });
  it("returns empty string for missing input", () => {
    expect(formatRelative(undefined)).toBe("");
    expect(formatRelative(null)).toBe("");
    expect(formatRelative(Number.NaN)).toBe("");
  });
});
