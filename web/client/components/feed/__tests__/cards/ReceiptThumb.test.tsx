// @vitest-environment jsdom
// web/client/components/feed/__tests__/cards/ReceiptThumb.test.tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import ReceiptThumb from "@client/components/feed/cards/ReceiptThumb";

afterEach(cleanup);

describe("ReceiptThumb", () => {
  it("renders a placeholder when no claimId is provided", () => {
    render(<ReceiptThumb />);
    expect(screen.getByText(/no claim/i)).toBeTruthy();
  });
  it("renders 'receipt missing' for missing-receipt flavour", () => {
    render(<ReceiptThumb claimId="C1" flavour="missing-receipt" />);
    expect(screen.getByText(/missing/i)).toBeTruthy();
  });
  it("renders an img for a present receipt", () => {
    render(<ReceiptThumb claimId="C1" />);
    const img = screen.getByAltText(/receipt c1/i);
    expect(img).toBeTruthy();
  });
  it("falls back to placeholder when the image errors", () => {
    render(<ReceiptThumb claimId="C1" />);
    const img = screen.getByAltText(/receipt c1/i) as HTMLImageElement;
    fireEvent.error(img);
    expect(screen.getByText(/missing/i)).toBeTruthy();
  });
});
