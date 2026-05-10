"""Shared brief validator for compose-domain v4 sub-skills.

Pure-function entry point :func:`validate_brief` that:

* Parses the schema YAML at ``docs/superpowers/skills/compose-domain/brief.schema.yaml``
  (or accepts an in-memory schema dict).
* Runs ``jsonschema.Draft202012Validator`` against the brief.
* Re-raises the first failure as a :class:`SchemaError` with a stable
  ``path`` field that sub-skill tests can assert on.

Sub-skill validators wrap this with semantic checks layered on top
(e.g. "phase X must be kind: hitl" — a constraint jsonschema cannot
express on its own).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

__all__ = ["SchemaError", "load_schema", "validate_brief"]


_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "brief.schema.yaml"
)


class SchemaError(ValueError):
    """A structural brief failure with a JSON-pointer-ish ``path`` field.

    ``path`` is dot-joined (e.g. ``"entities[0].kind"``) so test bodies can
    assert on it without matching the surrounding prose.
    """

    def __init__(self, *, path: str, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"{path}: {reason}")


def load_schema(path: Path | None = None) -> dict[str, Any]:
    """Load + parse the brief schema YAML."""
    target = path or _SCHEMA_PATH
    with target.open() as f:
        doc = yaml.safe_load(f)
    # Strip the documentation-only `example` block before handing to
    # jsonschema (it's not part of the schema vocabulary).
    doc.pop("example", None)
    return doc


def _format_path(parts: list[Any]) -> str:
    out: list[str] = []
    for p in parts:
        if isinstance(p, int):
            if out:
                out[-1] = f"{out[-1]}[{p}]"
            else:
                out.append(f"[{p}]")
        else:
            out.append(str(p))
    return ".".join(out) if out else "<root>"


def validate_brief(brief: dict, schema: dict | None = None) -> None:
    """Validate ``brief`` against the v4 schema. Raises :class:`SchemaError`.

    A ``schema=None`` argument loads the canonical YAML from disk.
    """
    s = schema if schema is not None else load_schema()
    validator = Draft202012Validator(s)
    errors = sorted(validator.iter_errors(brief), key=lambda e: list(e.absolute_path))
    if not errors:
        return
    err = errors[0]
    raise SchemaError(
        path=_format_path(list(err.absolute_path)),
        reason=err.message,
    )
