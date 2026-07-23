"""CLI entry point: `uv run python -m verticals.travel.generator`.

Generates (or, with `--clean`, removes) the Travel vertical pack's
generated assets under a target root, defaulting to the repository root.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .render import clean, generate

# verticals/travel/generator/__main__.py -> repo root is three parents up.
_DEFAULT_TARGET_ROOT = Path(__file__).resolve().parents[3]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m verticals.travel.generator",
        description=(
            "Deterministically generate (or clean) the Travel vertical "
            "pack's generated assets."
        ),
    )
    parser.add_argument(
        "--target-root",
        type=Path,
        default=_DEFAULT_TARGET_ROOT,
        help=(
            "Root directory under which verticals/travel/ is generated "
            "(default: repository root; pass a tmp dir in tests)."
        ),
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove every asset listed in the current manifest instead of generating.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.clean:
        removed = clean(target_root=args.target_root)
        print(json.dumps({"removed": [str(path) for path in removed]}, indent=2))
        return 0

    manifest = generate(target_root=args.target_root)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
