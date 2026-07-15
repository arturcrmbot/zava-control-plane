import { describe, expect, it } from "vitest";

import { CLOUD_FRAG, FRAG } from "../PlanetSurface";

describe("PlanetSurface shaders", () => {
  it("do not use the reserved GLSL sample identifier", () => {
    expect(FRAG).not.toMatch(/\bvec3\s+sample\b/);
    expect(CLOUD_FRAG).not.toMatch(/\bvec3\s+sample\b/);
  });
});
