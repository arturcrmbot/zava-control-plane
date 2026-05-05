// mocks/authority-mcp/test/resolver.test.ts
//
// Unit tests for the authority resolver. Covers:
//   (a) exact match wins
//   (b) wildcard fallback
//   (c) value-band edge cases (min, max inclusive)
//   (d) no-match behaviour
//   (e) one canonical resolution per existing domain (8 cases)
//   (f) checkAuthority for primary + escalation + denied
//
// Run: tsx --test mocks/authority-mcp/test/resolver.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { resolve, checkAuthority, AuthorityRule } from "../resolver.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const matrixPath = path.resolve(here, "..", "..", "..", "data", "synthetic", "authority", "matrix.json");
const matrix = JSON.parse(readFileSync(matrixPath, "utf-8")) as AuthorityRule[];

// (a) exact match wins
test("exact match wins over later wildcard", () => {
  const r = resolve(matrix, {
    action: "expense_claim_approval",
    category: "production",
    business_unit: "production",
    geography: "AMER",
    value: 30000,
  });
  assert.equal(r.matched, true);
  if (r.matched) {
    assert.equal(r.rule_id, "EXP-040-PROD-AMER");
    assert.equal(r.approver_role, "line_manager");
  }
});

// (b) wildcard fallback when no specific rule matches
test("wildcard rule matches when specific scope absent", () => {
  const r = resolve(matrix, {
    action: "expense_claim_approval",
    category: "meals",
    business_unit: "anything-not-listed",
    geography: "ANT",
    value: 75,
  });
  assert.equal(r.matched, true);
  if (r.matched) {
    assert.equal(r.rule_id, "EXP-001");
  }
});

// (c) value-band edge cases — min and max inclusive
test("value-band lower bound is inclusive", () => {
  const r = resolve(matrix, {
    action: "expense_claim_approval",
    category: "meals",
    value: 100,
  });
  // 100 sits at the seam between EXP-001 (0..100) and EXP-002 (100..500).
  // EXP-001 comes first and 100 <= max → first-match wins.
  assert.equal(r.matched, true);
  if (r.matched) assert.equal(r.rule_id, "EXP-001");
});

test("value-band upper bound is inclusive", () => {
  const r = resolve(matrix, {
    action: "expense_claim_approval",
    category: "meals",
    value: 500,
  });
  // 500 is at the boundary; EXP-002's max is 500 inclusive.
  // EXP-001 max is 100, doesn't match. EXP-002 wins.
  assert.equal(r.matched, true);
  if (r.matched) assert.equal(r.rule_id, "EXP-002");
});

test("open-ended max (null) catches arbitrarily large values", () => {
  const r = resolve(matrix, {
    action: "expense_claim_approval",
    category: "meals",
    value: 99_999_999,
  });
  assert.equal(r.matched, true);
  if (r.matched) assert.equal(r.rule_id, "EXP-004");
});

// (d) no-match behaviour
test("unknown action returns matched=false", () => {
  const r = resolve(matrix, { action: "no_such_action_exists" });
  assert.equal(r.matched, false);
  if (!r.matched) assert.match(r.reason, /no rule matched/);
});

// (e) canonical resolution per existing domain (8 cases)
const canonical: Array<{ name: string; req: any; expectRule: string; expectApprover: string }> = [
  {
    name: "expense-claim · meals £180",
    req: { action: "expense_claim_approval", category: "meals", value: 180 },
    expectRule: "EXP-002",
    expectApprover: "line_manager",
  },
  {
    name: "travel-preapproval · international £4,200",
    req: { action: "travel_preapproval", category: "international", value: 4200 },
    expectRule: "TRV-011",
    expectApprover: "finance_controller",
  },
  {
    name: "vendor-kyc · high_risk",
    req: { action: "vendor_kyc_signoff", category: "high_risk" },
    expectRule: "VKY-003",
    expectApprover: "contracts_counsel",
  },
  {
    name: "contract-renewal · price_jump £35,000",
    req: { action: "contract_renewal_signoff", category: "price_jump", value: 35000 },
    expectRule: "CRN-010",
    expectApprover: "contract_finance_bp",
  },
  {
    name: "it-access-request · privileged_role",
    req: { action: "it_access_grant", category: "privileged_role" },
    expectRule: "ITAR-003",
    expectApprover: "it_access_it_admin",
  },
  {
    name: "employee-onboarding · external_contractor",
    req: { action: "employee_onboarding_access", category: "external_contractor" },
    expectRule: "ONB-003",
    expectApprover: "onboarding_it_admin",
  },
  {
    name: "perf-review · calibration_outlier",
    req: { action: "perf_calibration_signoff", category: "calibration_outlier" },
    expectRule: "PRR-002",
    expectApprover: "perf_review_hr_bp",
  },
  {
    name: "hiring · budget delta £8,000 (within band)",
    req: { action: "hire_budget_approval", category: "within_band", value: 8000 },
    expectRule: "HIRE-BUDGET-002",
    expectApprover: "finance_bp",
  },
];

for (const c of canonical) {
  test(`canonical resolution: ${c.name}`, () => {
    const r = resolve(matrix, c.req);
    assert.equal(r.matched, true, `expected match for ${c.name}`);
    if (r.matched) {
      assert.equal(r.rule_id, c.expectRule);
      assert.equal(r.approver_role, c.expectApprover);
    }
  });
}

// (f) checkAuthority — primary, escalation, denied
test("checkAuthority allows primary approver", () => {
  const r = checkAuthority(matrix, {
    role: "ssc_reviewer",
    action: "expense_claim_approval",
    category: "meals",
    value: 1000,
  });
  assert.equal(r.allowed, true);
  assert.equal(r.governing_rule_id, "EXP-003");
});

test("checkAuthority allows escalation-chain role", () => {
  const r = checkAuthority(matrix, {
    role: "finance_controller",
    action: "expense_claim_approval",
    category: "meals",
    value: 1000,
  });
  assert.equal(r.allowed, true);
  assert.equal(r.governing_rule_id, "EXP-003");
});

test("checkAuthority denies role outside primary + escalation", () => {
  const r = checkAuthority(matrix, {
    role: "candidate",
    action: "expense_claim_approval",
    category: "meals",
    value: 1000,
  });
  assert.equal(r.allowed, false);
  assert.equal(r.governing_rule_id, "EXP-003");
});

// Defensive: malformed matrix entry is skipped, not crashing
test("malformed rule is skipped with warning", () => {
  const broken: AuthorityRule[] = [
    // missing rule_id
    {
      action: "expense_claim_approval",
      category: "meals",
      value_band_gbp: { min: 0, max: 100 },
      business_unit: "*",
      geography: "*",
      requester_role: "*",
      approver_role: "auto",
      escalation_chain: [],
      basis: "broken",
    } as unknown as AuthorityRule,
    {
      rule_id: "GOOD-001",
      action: "expense_claim_approval",
      category: "meals",
      value_band_gbp: { min: 0, max: 100 },
      business_unit: "*",
      geography: "*",
      requester_role: "*",
      approver_role: "auto",
      escalation_chain: [],
      basis: "good",
    },
  ];
  const r = resolve(broken, { action: "expense_claim_approval", category: "meals", value: 50 });
  assert.equal(r.matched, true);
  if (r.matched) assert.equal(r.rule_id, "GOOD-001");
});
