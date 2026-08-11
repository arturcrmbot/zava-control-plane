/**
 * Public story smoke tests.
 *
 * Requires two env vars:
 *   PUBLIC_STORY_URL  — deployed GitHub Pages article URL
 *   ACA_REPLAY_URL    — deployed Azure Container Apps replay URL
 *
 * These are not run locally unless those vars are set (the workflow only
 * runs them after a Pages deploy).
 */

import { expect, test, type Page } from "@playwright/test";

const pagesUrl = process.env.PUBLIC_STORY_URL;
const replayUrl = process.env.ACA_REPLAY_URL;

function required(value: string | undefined, name: string): string {
  if (!value) throw new Error(`${name} env var is required`);
  return value.replace(/\/$/, "");
}

function captureErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (message) => {
    // Ignore favicon 404s — these are browser-generated and not indicative of
    // application errors (consistent with existing e2e convention).
    if (message.type() === "error" && !message.text().includes("favicon")) {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => errors.push(String(error)));
  return errors;
}

test.describe("public story smoke", () => {
  test.describe.configure({ retries: 2, timeout: 120_000 });

  test("published article carries the approved promise and ACA Constellation link", async ({
    page,
  }) => {
    const story = required(pagesUrl, "PUBLIC_STORY_URL");
    const replay = required(replayUrl, "ACA_REPLAY_URL");
    const errors = captureErrors(page);

    await page.goto(story, { waitUntil: "domcontentloaded" });

    await expect(
      page.getByText(/See what an agentic organisation actually looks like/i),
    ).toBeVisible();

    const link = page.getByRole("link", { name: /Open Constellation/i });
    const href = await link.getAttribute("href");
    expect(href).toBeTruthy();
    // Verify origin matches ACA — use string parsing rather than a regex that
    // might inadvertently match an unescaped URL character.
    const linkUrl = new URL(href!);
    const replayOrigin = new URL(replay).origin;
    expect(linkUrl.origin).toBe(replayOrigin);
    expect(linkUrl.searchParams.get("view")).toBe("constellation");

    expect(errors).toEqual([]);
  });

  test("ACA is a truthful replay and Constellation explains itself", async ({
    page,
    request,
  }) => {
    const replay = required(replayUrl, "ACA_REPLAY_URL");

    // 1. Verify the replay meta API.
    const meta = await request.get(`${replay}/api/replay/meta`);
    expect(meta.ok()).toBeTruthy();
    const metaBody = await meta.json();
    expect(metaBody.mode).toBe("replay");
    expect(typeof metaBody.recorded_at).toBe("string");

    // 2. Visit the Constellation view and verify orientation copy.
    const errors = captureErrors(page);
    await page.goto(`${replay}/blueprint/?view=constellation`, {
      waitUntil: "domcontentloaded",
    });

    await expect(
      page.getByText(/watching a working agentic organisation/i),
    ).toBeVisible();

    await expect(page.getByText(/Recorded telemetry/i)).toBeVisible();

    await expect(
      page.getByRole("button", { name: /Follow one decision/i }),
    ).toBeVisible();

    expect(errors).toEqual([]);
  });
});
