import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { buildConstellationUrl } from "../../lib/constellationUrl";
import { buildDemoUrl } from "../../lib/useDemoUrl";

const here = dirname(fileURLToPath(import.meta.url));

function section(name: string): string {
  return readFileSync(resolve(here, "..", `${name}.tsx`), "utf8");
}

function readFile(path: string): string {
  return readFileSync(resolve(here, path), "utf8");
}

describe("blueprint article story contract", () => {
  it("leads with the approved agentic-organisation promise", () => {
    expect(section("Opening")).toContain("See what an agentic organisation");
    expect(section("Opening")).toContain("use the blueprint to build yours");
  });

  it("does not position simulation as the product", () => {
    expect(section("Personae")).not.toContain(
      "The people in the simulated organisation",
    );
    expect(section("Personae")).not.toContain(
      "The substrate runs as a simulated organisation",
    );
    expect(section("MetaSkill")).not.toContain(
      "a live simulation running against real Azure infra",
    );
  });

  it("names Constellation as the visual command surface", () => {
    const observatory = section("Observatory");
    expect(observatory).toContain("Constellation");
    expect(observatory).toContain("visual command surface");
  });

  it("keeps memory claims bounded to enabled domains", () => {
    const memory = section("Memory");
    expect(memory).toContain("Where memory is enabled");
    expect(memory).not.toContain("Anthropic invented this");
  });

  it("closes with incremental connection to the existing estate", () => {
    const closing = section("Closing");
    expect(closing).toContain("existing agent");
    expect(closing).toContain("existing systems");
    expect(closing).toContain("make its edges real");
    expect(closing).not.toContain("nine workflows");
  });

  // Focused source-level tests for isolated-pilot / reference-implementation / synthetic boundary substance
  it("opening contains isolated-pilot and reference-implementation boundary substance", () => {
    const opening = section("Opening");
    expect(opening).toContain("one assistant handling one task");
    expect(opening).toContain("working reference implementation");
    expect(opening).toContain("A complete synthetic organisation");
  });

  // Composition retains CompositionMap and segment explanation
  it("composition preserves CompositionMap component and segment model", () => {
    const composition = section("Composition");
    expect(composition).toContain("CompositionMap");
    expect(composition).toContain("single segment");
    expect(composition).toContain("the model decides which skill");
  });

  // MetaSkill asserts current proven reference is Telco (intentionally hard-coded per approved story)
  it("metaskill establishes telco as proven reference with boundary connections", () => {
    const metaSkill = section("MetaSkill");
    expect(metaSkill).toContain("Telco vertical");
    expect(metaSkill).toContain("current proven reference");
    expect(metaSkill).toContain("Existing investments connect at the same boundaries");
  });

  // Observatory CTA text check (source assertion for visible copy)
  it("observatory CTA text says Open Constellation", () => {
    expect(section("Observatory")).toContain("Open Constellation");
  });

  // Behavioral URL helper tests — no source token assertions
  describe("buildConstellationUrl", () => {
    it("local blueprint dev (port 5275) returns origin:5275, pathname /, view=constellation", () => {
      const result = buildConstellationUrl(
        "http://localhost:5275/",
        "https://replay.example/?from=article-constellation",
      );
      const url = new URL(result);
      expect(url.hostname).toBe("localhost");
      expect(url.port).toBe("5275");
      expect(url.pathname).toBe("/");
      expect(url.searchParams.get("view")).toBe("constellation");
    });

    it("article-local (port 5273) redirects to port 5275, pathname /, view=constellation", () => {
      const result = buildConstellationUrl(
        "http://localhost:5273/blueprint/",
        "https://replay.example/?from=article-constellation",
      );
      const url = new URL(result);
      expect(url.hostname).toBe("localhost");
      expect(url.port).toBe("5275");
      expect(url.pathname).toBe("/");
      expect(url.searchParams.get("view")).toBe("constellation");
    });

    it("deployed: builds from demoBase, pathname /blueprint/, preserves from param, sets view=constellation", () => {
      const result = buildConstellationUrl(
        "https://docs.example/article",
        "https://replay.example/?from=article-constellation",
      );
      const url = new URL(result);
      expect(url.hostname).toBe("replay.example");
      expect(url.pathname).toBe("/blueprint/");
      expect(url.searchParams.get("from")).toBe("article-constellation");
      expect(url.searchParams.get("view")).toBe("constellation");
    });

    it("deployed: does not leak unrelated query params from currentHref into output", () => {
      const result = buildConstellationUrl(
        "https://docs.example/article?tab=intro&session=abc",
        "https://replay.example/?from=article-constellation",
      );
      const url = new URL(result);
      expect(url.searchParams.has("tab")).toBe(false);
      expect(url.searchParams.has("session")).toBe(false);
    });
  });

  // App.tsx footer contains August 2026
  it("app footer includes august 2026 publication date", () => {
    const appFile = readFile("../../App.tsx");
    expect(appFile).toContain("August 2026");
  });

  // Behavioral URL helper tests for Closing CTA — no source-token assertions
  describe("Closing 'Watch it run' CTA routes to Constellation", () => {
    it("local blueprint dev (port 5275) returns root with view=constellation", () => {
      const result = buildConstellationUrl(
        "http://localhost:5275/",
        buildDemoUrl("/", "closing", "https://replay.example.com"),
      );
      const url = new URL(result);
      expect(url.hostname).toBe("localhost");
      expect(url.port).toBe("5275");
      expect(url.pathname).toBe("/");
      expect(url.searchParams.get("view")).toBe("constellation");
    });

    it("article-local (port 5273) redirects to port 5275 with view=constellation", () => {
      const result = buildConstellationUrl(
        "http://localhost:5273/blueprint/",
        buildDemoUrl("/", "closing", "https://replay.example.com"),
      );
      const url = new URL(result);
      expect(url.hostname).toBe("localhost");
      expect(url.port).toBe("5275");
      expect(url.pathname).toBe("/");
      expect(url.searchParams.get("view")).toBe("constellation");
    });

    it("deployed: sets pathname /blueprint/, preserves from=closing, sets view=constellation", () => {
      const result = buildConstellationUrl(
        "https://docs.example/article",
        buildDemoUrl("https://replay.example.com/", "closing"),
      );
      const url = new URL(result);
      expect(url.hostname).toBe("replay.example.com");
      expect(url.pathname).toBe("/blueprint/");
      expect(url.searchParams.get("from")).toBe("closing");
      expect(url.searchParams.get("view")).toBe("constellation");
    });
  });
});
