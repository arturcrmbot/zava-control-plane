// Shared accessor for the public replay deployment URL.
//
// The default points at the Azure Container Apps replay deploy. Override at
// build time with VITE_DEMO_URL (e.g. for a fork pointing at a different
// environment).
//
// Pass an optional `source` to be appended as `from=<source>` so we can tell
// in telemetry which CTA the visitor came from (essay closing, topbar,
// hero, observatory inline).
export function getDemoUrl(source: string = "essay"): string {
  const base = ((import.meta as any).env?.VITE_DEMO_URL as string | undefined)
    ?? "https://zava-zava-verify-fruocco.thankfulsand-2576b58e.swedencentral.azurecontainerapps.io/";
  const sep = base.includes("?") ? "&" : "?";
  return `${base}${sep}from=${encodeURIComponent(source)}`;
}
