/**
 * Shared helper for building a Constellation view URL.
 *
 * - When running locally (localhost / 127.0.0.1 / *.local) it redirects to
 *   port 5275 at the root path with ?view=constellation, matching Observatory
 *   dev-server behaviour.
 * - When deployed it builds from `demoBase` (the configured replay URL),
 *   sets pathname to /blueprint/, preserves attribution query params (e.g.
 *   `from=…`) from demoBase, and sets ?view=constellation.
 *
 * @param currentHref  window.location.href (or a stable fallback for SSR).
 * @param demoBase     The replay URL with source attribution, e.g. from getDemoUrl().
 */
export function buildConstellationUrl(currentHref: string, demoBase: string): string {
  const current = new URL(currentHref);
  const host = current.hostname;
  const isLocal = host === "localhost" || host === "127.0.0.1" || host.endsWith(".local");
  if (isLocal) {
    const url = new URL(current.origin);
    url.port = "5275";
    url.pathname = "/";
    url.search = "";
    url.searchParams.set("view", "constellation");
    return url.toString();
  }
  const base = new URL(demoBase);
  const url = new URL(base.origin);
  url.pathname = "/blueprint/";
  base.searchParams.forEach((value, key) => {
    if (key !== "view") url.searchParams.set(key, value);
  });
  url.searchParams.set("view", "constellation");
  return url.toString();
}
