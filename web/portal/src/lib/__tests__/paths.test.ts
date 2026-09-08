import { afterEach, describe, expect, it, vi } from "vitest";
import { portalPath } from "../paths";

afterEach(() => vi.unstubAllEnvs());

describe("portal navigation paths", () => {
  it("keeps standalone development paths unchanged", () => {
    vi.stubEnv("BASE_URL", "/");
    expect(portalPath("/screen?token=example")).toBe("/screen?token=example");
  });

  it("keeps deployed navigation inside the portal mount", () => {
    vi.stubEnv("BASE_URL", "/portal/");
    expect(portalPath("/screen?token=a%2Fb")).toBe("/portal/screen?token=a%2Fb");
    expect(portalPath("portal?token=example")).toBe("/portal/portal?token=example");
  });
});
