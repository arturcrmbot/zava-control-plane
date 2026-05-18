// @vitest-environment jsdom
// web/client/components/feed/__tests__/NewItemsPill.test.tsx
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import NewItemsPill from "@client/components/feed/NewItemsPill";

afterEach(cleanup);

describe("NewItemsPill", () => {
  it("renders nothing when count is 0", () => {
    const { container } = render(<NewItemsPill count={0} onPullIn={() => {}} />);
    expect(container.firstChild).toBeNull();
  });
  it("renders '↑ 3 new' when count is 3", () => {
    render(<NewItemsPill count={3} onPullIn={() => {}} />);
    expect(screen.getByRole("button", { name: /3 new/i })).toBeTruthy();
  });
  it("fires onPullIn on click", () => {
    const onPullIn = vi.fn();
    render(<NewItemsPill count={1} onPullIn={onPullIn} />);
    fireEvent.click(screen.getByRole("button"));
    expect(onPullIn).toHaveBeenCalled();
  });
});
