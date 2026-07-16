export interface RuntimeManifest {
  vertical: {
    name: string;
    display_name: string;
    manifest_version: string;
    fingerprint: string;
  };
  world: string | null;
  world_scale: string | null;
  capabilities: string[];
  ui: {
    lenses: string[];
    theme: Record<string, string>;
  };
}
