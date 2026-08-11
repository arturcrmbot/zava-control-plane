/**
 * Determines whether ?view=... routing should be enabled for the current
 * runtime. Returns true when the process serving the bundle also hosts the
 * FastAPI control-plane (/api/...).
 *
 * Rules (first match wins):
 *  1. Always true in DEV (Vite dev-server).
 *  2. True for localhost / 127.0.0.1 / *.local (boot-demo.sh / vite preview).
 *  3. True for *.azurecontainerapps.io (public replay FQDN).
 *  4. True when VITE_DEMO_URL resolves to the SAME origin as the page — this
 *     covers the Docker/ACA bundle where VITE_DEMO_URL=/ and any custom domain
 *     that bakes an absolute same-origin URL.
 *  5. False for GitHub Pages, where VITE_DEMO_URL is an absolute ACA URL on a
 *     different origin.
 *  6. False when VITE_DEMO_URL is absent and no other condition applies.
 *     Invalid/unparseable configured URLs fall back to false for this rule only;
 *     rules 1-3 are still evaluated first.
 */
export function isRuntimeViewAllowed(
  currentOrigin: string,
  demoUrl: string | undefined,
  dev: boolean,
): boolean {
  if (dev) return true;

  let hostname: string;
  try {
    hostname = new URL(currentOrigin).hostname;
  } catch {
    // currentOrigin is not a valid absolute URL — cannot evaluate host rules.
    return false;
  }

  if (
    hostname === "localhost" ||
    hostname === "127.0.0.1" ||
    hostname.endsWith(".local")
  ) {
    return true;
  }

  if (hostname.endsWith(".azurecontainerapps.io")) return true;

  if (demoUrl !== undefined && demoUrl !== "") {
    try {
      const resolved = new URL(demoUrl, currentOrigin);
      if (resolved.origin === currentOrigin) return true;
    } catch {
      // Invalid configured URL — fall through to false.
    }
  }

  return false;
}
