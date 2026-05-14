# Persona photos

This directory holds head-shot images for the named individuals
surfaced by the cosmic-lens HUD's narrative-arcs panel
(see `web/blueprint/src/components/cosmicLens/HUD/NarrativeArcs.tsx`).

## Conventions

- File name matches the `photo_url` field in
  `api/server/data_fabric/narrative_arcs.py` (e.g. `aisha.png`).
- 256×256 PNG, square crop, transparent or dark background.
- One image per arc; the file is loaded directly by the browser at
  `/assets/personae/<name>.png`.

Until real photos land, the HUD renders CSS-only initials avatars,
so missing files are non-fatal.
