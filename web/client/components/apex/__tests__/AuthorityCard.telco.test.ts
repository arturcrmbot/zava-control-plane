import { describe, expect, it } from "vitest";

import type { Workflow } from "@shared/types";
import { deriveMatrixRequest } from "../AuthorityCard";

function workflow(
  type: Workflow["type"],
  payload: Record<string, unknown>,
): Workflow {
  return {
    id: `test-${type}`,
    type,
    status: "in_progress",
    currentPhase: "Intake",
    createdAt: 0,
    slaDueAt: 0,
    payload,
    jurisdiction: "UK",
    agency: "Zava",
    actionLedger: [],
    tokensSpent: 0,
    costUSD: 0,
  };
}

describe("Telco AuthorityCard mapping", () => {
  it("maps proactive care credits to the customer-care authority action", () => {
    const item = workflow(
      "proactive-customer-care",
      {
        decision: {
          command: {
            payload: {
              actions: [
                { credit_amount: 35 },
                { credit_amount: 40 },
              ],
            },
          },
        },
      },
    );

    expect(deriveMatrixRequest(item)).toEqual({
      action: "customer_care_credit_approval",
      category: "service_credit",
      value: 75,
    });
  });

  it("maps high-utilisation activation to the capacity exception action", () => {
    const item = workflow(
      "order-to-activate",
      {
        service_order: {
          requested_site: { utilization: 0.95 },
        },
      },
    );

    expect(deriveMatrixRequest(item)).toEqual({
      action: "order_capacity_exception",
      category: "site_capacity",
      value: 95,
    });
  });

  it("waits for a care decision before deriving authority", () => {
    const item = workflow("proactive-customer-care", {});

    expect(deriveMatrixRequest(item)).toBeNull();
  });
});
