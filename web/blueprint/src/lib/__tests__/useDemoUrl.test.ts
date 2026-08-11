import { describe, expect, it } from "vitest";
import { buildDemoUrl } from "../useDemoUrl";

describe("buildDemoUrl", () => {
  it("adds source attribution without losing existing query parameters", () => {
    expect(
      buildDemoUrl("https://example.test/?mode=replay", "observatory"),
    ).toBe("https://example.test/?mode=replay&from=observatory");
  });

  it("normalises a base without a trailing slash", () => {
    expect(buildDemoUrl("https://example.test", "closing")).toBe(
      "https://example.test/?from=closing",
    );
  });

  it("replaces an existing `from` parameter rather than duplicating it", () => {
    const url = buildDemoUrl("https://example.test/?from=old", "hero");
    expect(url).toBe("https://example.test/?from=hero");
  });

  it("encodes special characters in the source value", () => {
    const url = buildDemoUrl("https://example.test/", "a b&c=d");
    expect(url).toContain("from=a+b%26c%3Dd");
  });

  it("accepts a relative base with an explicit origin", () => {
    const url = buildDemoUrl("/", "hero", "https://replay.example.com");
    expect(url).toBe("https://replay.example.com/?from=hero");
  });
});
