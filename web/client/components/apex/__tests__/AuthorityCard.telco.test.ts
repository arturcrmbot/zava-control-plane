// @vitest-environment jsdom

import { createElement } from "react";
import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Workflow } from "@shared/types";
import AuthorityCard, { deriveMatrixRequest } from "../AuthorityCard";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

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

  it("does not resolve authority again for an equivalent payload object", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      json: async () => ({ matched: false }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const item = workflow("order-to-activate", {
      service_order: { requested_site: { utilization: 0.95 } },
    });

    const view = render(createElement(AuthorityCard, { workflow: item }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    view.rerender(
      createElement(AuthorityCard, {
        workflow: {
          ...item,
          payload: {
            service_order: { requested_site: { utilization: 0.95 } },
          },
        },
      }),
    );

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
