export interface WorldSceneLocation {
  id: string;
  label: string;
  x: number;
  y: number;
}

export interface WorldSceneActorBindingPosition {
  location_field?: string;
  x_field?: string;
  y_field?: string;
  route_field?: string;
  progress_field?: string;
}

export interface WorldSceneActorBinding {
  collection: string;
  kind: string;
  id_field: string;
  state_field: string;
  position: WorldSceneActorBindingPosition;
}

export interface WorldSceneEventMapping {
  event_type: string;
  animation_type: string;
  actor_id?: string;
  target_id?: string;
  actor_id_field?: string;
}

export interface WorldSceneMetadata {
  version: string;
  title: string;
  locations: WorldSceneLocation[];
  actor_bindings: WorldSceneActorBinding[];
  event_mappings: WorldSceneEventMapping[];
}

export interface RuntimeDomain {
  workflow_type: string;
  display_name: string;
}

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
  domains?: RuntimeDomain[];
  ui: {
    lenses: string[];
    theme: Record<string, string>;
    world_scene?: WorldSceneMetadata | boolean;
  };
}
