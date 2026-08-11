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

  // ── RED phase: new article contract ─────────────────────────────────────

  // 1. Metadata and navigation
  describe("metadata and navigation", () => {
    it("index.html title uses new agentic-organisation proposition", () => {
      const html = readFile("../../../../../index.html");
      expect(html).toContain("See what an agentic organisation");
      expect(html).not.toContain("Why your agentic strategy isn't moving the needle");
    });

    it("index.html description/OG/Twitter use new proposition", () => {
      const html = readFile("../../../../../index.html");
      expect(html).not.toContain("Why your agentic strategy isn't moving the needle");
    });

    it("TopBar contains new article caption", () => {
      const topBar = readFile("../../components/TopBar.tsx");
      expect(topBar).toContain("See what an agentic organisation actually looks like");
      expect(topBar).not.toContain("Why your agentic strategy isn't moving the needle");
    });
  });

  // 2. Current architecture truth
  describe("architecture truth", () => {
    it("Argument mentions both log-only and enforced governance modes", () => {
      const arg = section("Argument");
      expect(arg).toContain("log-only");
      expect(arg).toContain("enforced");
    });

    it("Argument does not claim adding/replacing a skill avoids deployment", () => {
      const arg = section("Argument");
      expect(arg).not.toContain("rather than a redeployment of the system");
      expect(arg).not.toContain("small change to a single file rather than a redeploy");
    });

    it("Argument does not say every agent uses the same adapter; uses pack-scoped/authorised capability language", () => {
      const arg = section("Argument");
      expect(arg).not.toContain("Every agent uses the same adapter for the same system");
      // Must contain pack-scoped or authorised capability language instead
      expect(arg).toMatch(/pack[\s-]scoped|authorised capability|authorised capabilities/i);
    });
  });

  // 3. Pack-owned authority
  describe("pack-owned authority", () => {
    it("Authority links or names verticals/agency/authority.py", () => {
      const auth = section("Authority");
      expect(auth).toContain("verticals/agency/authority.py");
    });

    it("Authority contains 'Each vertical owns' its authority", () => {
      const auth = section("Authority");
      expect(auth).toMatch(/each vertical owns/i);
    });

    it("Authority does not reference data/synthetic/authority/matrix.json", () => {
      const auth = section("Authority");
      expect(auth).not.toContain("data/synthetic/authority/matrix.json");
    });

    it("Authority does not say 'without a redeploy'", () => {
      const auth = section("Authority");
      expect(auth).not.toContain("without a redeploy");
    });
  });

  // 4. Proof/readiness truth
  describe("proof and readiness truth", () => {
    it("Composition calls Agency the worked example, not current proven reference", () => {
      const comp = section("Composition");
      expect(comp).toContain("worked example");
      expect(comp).not.toMatch(/current proven reference/);
    });

    it("MetaSkill contains Build ready, Demo ready, and Deployed with correct meaning", () => {
      const ms = section("MetaSkill");
      expect(ms).toContain("Build ready");
      expect(ms).toContain("Demo ready");
      expect(ms).toContain("Deployed");
    });

    it("MetaSkill does not import or render CompoundingDiagram", () => {
      const ms = section("MetaSkill");
      expect(ms).not.toContain("CompoundingDiagram");
    });

    it("MetaSkill contains not a reskin or equivalent", () => {
      const ms = section("MetaSkill");
      expect(ms).toMatch(/not a reskin|not merely a reskin/i);
    });

    it("no article section contains current proven reference except Telco canonical proof in Verticals", () => {
      const sections = [
        "Opening", "Analogy", "Argument", "Composition",
        "Personae", "Authority", "Memory", "MetaSkill",
        "Observatory", "Closing",
      ];
      for (const name of sections) {
        expect(section(name)).not.toMatch(/current proven reference/);
      }
      // Verticals.tsx must exist and may contain current proven reference for Telco
      const verticals = section("Verticals");
      expect(verticals).toContain("Telco");
    });
  });

  // 5. Seven executable vertical packs
  describe("seven executable vertical packs", () => {
    it("Verticals.tsx exists and contains all manifest display names", () => {
      const v = section("Verticals");
      expect(v).toContain("Agency");
      expect(v).toContain("Telco");
      expect(v).toContain("Fashion Retail");
      expect(v).toContain("Travel");
      expect(v).toContain("Synthetic Airline Operations");
      expect(v).toContain("Hospitality");
      expect(v).toContain("Electronics Retail");
    });

    it("Verticals.tsx says pack presence is not readiness", () => {
      const v = section("Verticals");
      expect(v).toMatch(/presence.{0,30}not readiness|not readiness/i);
    });

    it("Verticals.tsx says only Telco is the canonical proof reference", () => {
      const v = section("Verticals");
      expect(v).toMatch(/telco.{0,80}canonical proof|canonical proof.{0,80}telco/i);
    });
  });

  // 6. Concrete Agency story
  describe("concrete Agency story", () => {
    it("AgencyStory.tsx exists and contains Aurora, CFO, policy/freeze, AP invoices, escalation, CEO synthesis", () => {
      const as_ = section("AgencyStory");
      expect(as_).toContain("Aurora");
      expect(as_).toContain("CFO");
      expect(as_).toMatch(/policy|freeze/i);
      expect(as_).toMatch(/AP invoice|accounts payable invoice/i);
      expect(as_).toContain("escalation");
      expect(as_).toMatch(/CEO synthesis|CEO/i);
    });

    it("AgencyStory says data is synthetic but runtime boundaries/evidence are real", () => {
      const as_ = section("AgencyStory");
      expect(as_).toMatch(/data.{0,30}synthetic/i);
      expect(as_).toMatch(/runtime boundaries|boundaries.{0,30}real|evidence.{0,30}real/i);
    });

    it("App.tsx imports and renders AgencyStory and Verticals", () => {
      const app = readFile("../../App.tsx");
      expect(app).toContain("AgencyStory");
      expect(app).toContain("Verticals");
    });
  });

  // 7. Static fixture and replay honesty
  describe("static fixture and replay honesty", () => {
    it("Composition says its map is a curated static Agency snapshot, not live", () => {
      const comp = section("Composition");
      expect(comp).toMatch(/curated static|static.{0,30}snapshot/i);
      expect(comp).toContain("Agency");
    });

    it("Observatory says public view is recorded execution and not live", () => {
      const obs = section("Observatory");
      expect(obs).toMatch(/recorded execution|not live/i);
    });

    it("Observatory mentions recording date and selected vertical in full replay", () => {
      const obs = section("Observatory");
      expect(obs).toMatch(/recording date|selected vertical/i);
    });

    it("Opening does not contain 'synthetic today or real tomorrow'", () => {
      expect(section("Opening")).not.toContain("synthetic today or real tomorrow");
    });
  });

  // 8. Existing useful claims retained
  describe("existing useful claims retained", () => {
    it("Opening contains approved headline", () => {
      const opening = section("Opening");
      expect(opening).toContain("See what an agentic organisation");
    });

    it("Personae labels AP controller as an Agency example", () => {
      const personae = section("Personae");
      expect(personae).toMatch(/AP controller.{0,80}Agency example|Agency.{0,80}AP controller/i);
    });

    it("Memory remains conditional with 'Where memory is enabled'", () => {
      expect(section("Memory")).toContain("Where memory is enabled");
    });
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
