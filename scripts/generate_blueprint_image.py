"""Generate the Gutenberg blueprint illustration via Google's Gemini image API.

Idempotent and parameterless:

    uv run python scripts/generate_blueprint_image.py

Reads ``GEMINI_API_KEY`` from the environment (or from REPO_ROOT/.env if
present). Never logs the key. Writes the PNG to
``web/blueprint/public/gutenberg.png`` (creating the directory if needed).

Re-run when the prompt changes. The output file is gitignored under
``web/blueprint/.gitignore`` -- commit it only if you want a stable
artefact in the repo.

Uses Nano Banana Pro (``gemini-3-pro-image-preview``) for legible in-image
typography and 16:9 / 2K output.
"""

from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPO_ROOT / "web" / "blueprint" / "public" / "gutenberg.png"

MODEL = "gemini-3-pro-image-preview"
ASPECT_RATIO = "16:9"
IMAGE_SIZE = "2K"


def _load_env_file() -> None:
    """Load REPO_ROOT/.env into os.environ if python-dotenv is available.

    No-op if the file or library is missing. Existing environment values
    take precedence so the script works whether you ``source .env`` first
    or not.
    """
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv  # type: ignore
    except ImportError:
        return
    load_dotenv(env_path, override=False)


# Prompt is kept here verbatim so the script is self-contained. The thinking
# behind it lives in docs/archive/blueprint.md.
#
# Best-practice notes (from Google's Nano Banana guide):
#   1. Describe a scene as a narrative paragraph, not a keyword list.
#   2. Be hyper-specific. Order elements by importance.
#   3. State text rendering instructions explicitly and verbatim. Use Pro for
#      legible typography.
#   4. Provide the camera/composition language up front.
PROMPT = """\
A single editorial illustration in landscape 16:9, composed as two
adjacent panels of equal width with a thin vertical seam between them.
Matte digital illustration with hand-textured shading, in the visual
lineage of Christoph Niemann (New Yorker covers), Brian Stauffer, and
modern Penguin Press essay illustration. Restrained palette overall:
warm near-black surrounding tones, warm cream parchment highlights, and
a single warm amber accent used sparingly for light. No photorealism.
No vector-clean corporate-illustration look. Generous quiet detail, not
visual noise.

LEFT PANEL (cool, dim). A medieval scriptorium at midday, light from a
high lancet window. A single hooded monk hunched over a tilted writing
desk in the foreground, mid-illumination of a single open page; gold
leaf catching the cool light; fine brush in hand; half a capital letter
complete on the page. A second monk visible at a second desk in the
background, deep in his own different volume, no shared work between
them. To one side, a low wooden shelf with three or four hand-bound
finished volumes; each one obviously the work of a year. On the floor
in the foreground, a half-finished manuscript lies abandoned with its
parchment curling. The mood is skilled, painstaking, slow, isolated.
Cool palette throughout: muted greys, faded ochre, dim candlelight.
No readable text on this side; the bookshelf spines may carry decorative
illuminated marks but no legible English words.

RIGHT PANEL (warm, lit). A Gutenberg-era print shop. Warm amber
side-light from a high window. The dominant element of the right panel,
in the foreground, is the WOODEN TYPE CASE: a flat tray divided into
dozens of small compartments, each compartment holding a stack of
identical metal letter-sorts ready to be picked. A compositor's hand
is suspended just above the tray, having lifted a single piece of type.
On the workbench in front of the compositor, a composing stick already
holds one set line of type, with the individual cast letters visibly
arrayed into legible words. Beyond the bench, a forme -- a full page
of type locked up in its iron frame, set and ready, the discrete
letters now composed into continuous text. Behind the forme, the press
itself in the mid-distance, mid-pull, with one freshly printed sheet
just lifted clear of the platen. On a side bench to the right, a second
forme is being broken back out into individual letters and returned to
the case -- the same letterforms going home to be re-set on the next
page. The mood is alert, capable, quietly mechanical.

TYPOGRAPHY ON THE PAGE. The right panel must contain three short
legible English text moments, all rendered in clean serif printed type
as it would appear from a mid-15th-century press, ink slightly
imperfect on parchment. Render each one accurately and unambiguously,
with no spelling drift:

  1. On the bookshelf in the right-panel background, six slim recently
     printed pamphlets standing upright, each spine carrying one of the
     following words in clean serif capitals, in order from left to
     right: FINANCE, HIRING, ONBOARDING, PROCUREMENT, LEGAL, IT.
  2. On the freshly pulled sheet just lifted off the press, a single
     visible printed line in serif type reading exactly:
     "the unit of work is the type, not the page."
  3. No other readable English words on the page. No labels, captions,
     numbers, or watermarks anywhere else.

COMPOSITIONAL HIERARCHY of the right panel, in order of visual weight:
  (a) the type case and the compositor's hand above it,
  (b) the second forme being broken back out into letters on the side
      bench (this carries the "reusable" point),
  (c) the press itself, mid-pull, in the mid-distance.
The press must not dominate. The type case must.

GLOBAL FRAMING. Strong tonal contrast between the two panels: cool/dim
left, warm/lit right. The seam between them is a thin vertical rule, not
a hard wall. The composition reads as a single editorial spread, not as
two separate illustrations. No border, no caption, no title text overlay
from the model itself -- only the in-scene typography described above.
"""


def main() -> int:
    _load_env_file()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print(
            "GEMINI_API_KEY is not set. Add it to .env or export it in your shell.",
            file=sys.stderr,
        )
        return 1

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print(
            "The google-genai package is not installed. Run:\n"
            "    uv sync --group dev\n"
            "(google-genai is in the dev dependency group).",
            file=sys.stderr,
        )
        return 1

    client = genai.Client(api_key=api_key)

    print(f"Generating illustration via {MODEL} ({ASPECT_RATIO}, {IMAGE_SIZE}) ...")
    response = client.models.generate_content(
        model=MODEL,
        contents=[PROMPT],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(
                aspect_ratio=ASPECT_RATIO,
                image_size=IMAGE_SIZE,
            ),
        ),
    )

    image_bytes: bytes | None = None
    for candidate in response.candidates or []:
        for part in candidate.content.parts or []:
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                data = inline.data
                # SDK returns bytes for some versions and base64 string for others.
                image_bytes = data if isinstance(data, bytes) else base64.b64decode(data)
                break
        if image_bytes:
            break

    if not image_bytes:
        print("No image returned by the model. Response:", response, file=sys.stderr)
        return 2

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_bytes(image_bytes)
    print(f"Wrote {OUTPUT_PATH.relative_to(REPO_ROOT)} ({len(image_bytes):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
