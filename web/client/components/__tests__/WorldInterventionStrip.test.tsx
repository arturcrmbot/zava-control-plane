// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { WorldInterventionStrip } from "@client/components/WorldInterventionStrip";

afterEach(cleanup);

describe("WorldInterventionStrip", () => {
  it("renders causal steps and selects the trace", () => {
    const onTrace = vi.fn();

    render(
      <WorldInterventionStrip
        testId="intervention"
        trace="network-anomaly-SITE-01"
        steps={[
          { label: "Anomaly detected", eventId: "E-1", detail: "SITE-01" },
          { label: "Command accepted", eventId: "E-2" },
        ]}
        onTrace={onTrace}
      />,
    );

    const strip = screen.getByTestId("intervention");
    expect(within(strip).getByText("Anomaly detected")).toBeTruthy();
    expect(within(strip).getByText("SITE-01")).toBeTruthy();
    expect(within(strip).getByText("Command accepted")).toBeTruthy();

    fireEvent.click(within(strip).getByRole("button"));
    expect(onTrace).toHaveBeenCalledWith("network-anomaly-SITE-01");
  });
});
