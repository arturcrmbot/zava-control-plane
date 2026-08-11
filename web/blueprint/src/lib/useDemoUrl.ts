// Shared accessor for the public replay deployment URL.
//
// The demo URL is configured at build time via VITE_DEMO_URL. When that
// variable is absent (local dev) we resolve a same-origin base so the
// blueprint microsite can reach the FastAPI control plane running on the
// same machine without ever hardcoding an Azure hostname.
//
// Pass an optional `source` to be appended as `from=<source>` so we can tell
// in telemetry which CTA the visitor came from (essay closing, topbar,
// hero, observatory inline).

function localDemoBase(): string {
  if (typeof window === "undefined") return "/";
  const { protocol, hostname, port, origin } = window.location;
  // In local dev the blueprint Vite server runs on :5275 and FastAPI on :5273.
  if (port === "5275") return `${protocol}//${hostname}:5273/`;
  return `${origin}/`;
}

export function buildDemoUrl(
  base: string,
  source: string,
  origin: string = typeof window !== "undefined" ? window.location.origin : "http://localhost",
): string {
  const url = new URL(base, origin);
  url.searchParams.set("from", source);
  return url.toString();
}

export function getDemoUrl(source: string = "essay"): string {
  const configured = (
    (import.meta as unknown as { env?: { VITE_DEMO_URL?: string } }).env
      ?.VITE_DEMO_URL ?? ""
  ).trim();
  return buildDemoUrl(configured || localDemoBase(), source);
}
