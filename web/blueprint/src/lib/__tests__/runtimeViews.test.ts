import { describe, expect, it } from "vitest";
import { isRuntimeViewAllowed } from "../runtimeViews";

describe("isRuntimeViewAllowed", () => {
  it("returns true when dev=true regardless of origin or demoUrl", () => {
    expect(isRuntimeViewAllowed("https://arturzielinski.github.io", undefined, true)).toBe(true);
  });

  it("returns true for localhost", () => {
    expect(isRuntimeViewAllowed("http://localhost:5275", undefined, false)).toBe(true);
  });

  it("returns true for 127.0.0.1", () => {
    expect(isRuntimeViewAllowed("http://127.0.0.1:5275", undefined, false)).toBe(true);
  });

  it("returns true for *.azurecontainerapps.io", () => {
    expect(
      isRuntimeViewAllowed(
        "https://zava-replay.eastus.azurecontainerapps.io",
        undefined,
        false,
      ),
    ).toBe(true);
  });

  it("returns true for custom domain + VITE_DEMO_URL='/' (ACA Docker bundle, same origin)", () => {
    expect(isRuntimeViewAllowed("https://demo.contoso.com", "/", false)).toBe(true);
  });

  it("returns true for custom domain + absolute same-origin VITE_DEMO_URL", () => {
    expect(
      isRuntimeViewAllowed(
        "https://demo.contoso.com",
        "https://demo.contoso.com/",
        false,
      ),
    ).toBe(true);
  });

  it("returns false for GitHub Pages origin with different ACA absolute VITE_DEMO_URL", () => {
    expect(
      isRuntimeViewAllowed(
        "https://arturzielinski.github.io",
        "https://zava-replay.eastus.azurecontainerapps.io",
        false,
      ),
    ).toBe(false);
  });

  it("returns false for arbitrary custom host with no configured demoUrl", () => {
    expect(isRuntimeViewAllowed("https://blog.example.com", undefined, false)).toBe(false);
  });

  it("returns false when VITE_DEMO_URL is an absolute cross-origin URL and no other rule applies", () => {
    // An absolute URL whose origin differs from the current page is not same-origin.
    expect(
      isRuntimeViewAllowed("https://demo.contoso.com", "https://other.example.com/api", false),
    ).toBe(false);
  });

  it("does not throw and returns false when VITE_DEMO_URL is a malformed URL", () => {
    // new URL("http://[::1]invalid", base) throws — the helper must not surface it.
    expect(
      isRuntimeViewAllowed("https://demo.contoso.com", "http://[::1]invalid", false),
    ).toBe(false);
  });
});
