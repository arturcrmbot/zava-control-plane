// @vitest-environment jsdom
// web/client/components/feed/__tests__/FilterBar.test.tsx
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import FilterBar from "@client/components/feed/FilterBar";

afterEach(cleanup);

const noop = () => {};

describe("FilterBar", () => {
  it("renders the [Needs you] / [All activity] segmented control", () => {
    render(
      <FilterBar
        filter={{ mode: "needs-you", domains: [], severity: null, search: "" }}
        onChange={noop}
        selectMode={false}
        onSelectModeChange={noop}
        availableDomains={[]}
      />,
    );
    expect(screen.getByRole("button", { name: /Needs you/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /All activity/i })).toBeTruthy();
  });

  it("fires onChange with new mode when All activity is clicked", () => {
    const onChange = vi.fn();
    render(
      <FilterBar
        filter={{ mode: "needs-you", domains: [], severity: null, search: "" }}
        onChange={onChange}
        selectMode={false}
        onSelectModeChange={noop}
        availableDomains={[]}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /All activity/i }));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ mode: "all-activity" }),
    );
  });

  it("renders a domain chip per availableDomains entry and toggles it", () => {
    const onChange = vi.fn();
    render(
      <FilterBar
        filter={{ mode: "needs-you", domains: [], severity: null, search: "" }}
        onChange={onChange}
        selectMode={false}
        onSelectModeChange={noop}
        availableDomains={["expense-claim", "hiring"]}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /^expense-claim$/i }));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ domains: ["expense-claim"] }),
    );
  });

  it("supports a 'Select' mode toggle", () => {
    const onSel = vi.fn();
    render(
      <FilterBar
        filter={{ mode: "needs-you", domains: [], severity: null, search: "" }}
        onChange={noop}
        selectMode={false}
        onSelectModeChange={onSel}
        availableDomains={[]}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /^Select$/i }));
    expect(onSel).toHaveBeenCalledWith(true);
  });

  it("fires onChange with new search on each keystroke", () => {
    const onChange = vi.fn();
    render(
      <FilterBar
        filter={{ mode: "needs-you", domains: [], severity: null, search: "" }}
        onChange={onChange}
        selectMode={false}
        onSelectModeChange={noop}
        availableDomains={[]}
      />,
    );
    fireEvent.change(screen.getByPlaceholderText(/search/i), { target: { value: "WF-12" } });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ search: "WF-12" }),
    );
  });
});
