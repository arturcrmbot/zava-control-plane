"""Tool manifest loader.

Per ``plan/feature-agent-governance-toolkit-1.md`` TASK-011. Single
source of truth for the schema of ``data/policies/tools.yaml``. The
kernel ([kernel.py](./kernel.py)) reads the manifest at boot via
:func:`load_tools_yaml` and stashes the result on the singleton.

Schema is documented in ``data/policies/README.md``.
"""
from __future__ import annotations

import threading
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

# Patterns used by SEC-004 of the plan: any tool whose id ends in one of
# these is, by convention, side-effecting. The compiler / CI validators
# may reuse these to catch lying manifests in Phase 8.
DESTRUCTIVE_SUFFIXES = (
    "write",
    "submit",
    "send",
    "cancel",
    "delete",
    "create",
    "post",
    "book",
)


class ToolManifestEntry(BaseModel):
    """One MCP tool's policy-relevant metadata.

    Frozen + extra=forbid so a typo in ``tools.yaml`` fails boot loudly
    rather than silently dropping a field.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    reversible: bool
    requires_capability: Optional[str] = None
    requires_authority: bool = False
    value_field: Optional[str] = None
    scope_function: str = Field(
        default="shared",
        description="Operating function: finance / hiring / creative / shared.",
    )
    description: str = ""

    @field_validator("id")
    @classmethod
    def _id_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("tool.id must be non-empty")
        return v.strip()


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


_LOAD_LOCK = threading.Lock()


def _default_path() -> Path:
    """Locate ``data/policies/tools.yaml`` relative to the repo root.

    The loader walks up from this file (``api/server/services/governance/``)
    to the first ancestor containing ``data/policies/tools.yaml``. Keeps
    the loader callable from any cwd (FastAPI / Functions / pytest).
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "data" / "policies" / "tools.yaml"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "data/policies/tools.yaml not found relative to "
        f"{here}; ensure the repo layout is intact."
    )


@lru_cache(maxsize=8)
def load_tools_yaml(path: Optional[str] = None) -> dict[str, ToolManifestEntry]:
    """Parse and validate ``tools.yaml``. Cached per absolute path.

    Returns a dict keyed by ``ToolManifestEntry.id`` so the kernel can
    do O(1) lookups. Raises ``ValueError`` (with the offending tool id)
    on schema mismatch — boot fails closed per REQ-003 / SEC-002.

    The ``path`` argument is mainly a test seam; production callers omit
    it and let :func:`_default_path` find the canonical file.
    """
    target = Path(path).resolve() if path else _default_path()
    with _LOAD_LOCK:
        try:
            raw = yaml.safe_load(target.read_text(encoding="utf-8"))
        except yaml.YAMLError as ex:  # pragma: no cover — surface boot failure
            raise ValueError(f"tools.yaml at {target} is not valid YAML: {ex}") from ex

    if not isinstance(raw, dict) or "tools" not in raw:
        raise ValueError(
            f"tools.yaml at {target} must be a mapping with a top-level 'tools' list"
        )

    tools_list = raw["tools"]
    if not isinstance(tools_list, list) or not tools_list:
        raise ValueError(
            f"tools.yaml at {target}: 'tools' must be a non-empty list"
        )

    out: dict[str, ToolManifestEntry] = {}
    for idx, item in enumerate(tools_list):
        if not isinstance(item, dict):
            raise ValueError(f"tools.yaml entry #{idx} is not a mapping: {item!r}")
        tool_id = item.get("id", f"<entry#{idx}>")
        try:
            entry = ToolManifestEntry.model_validate(item)
        except Exception as ex:
            raise ValueError(
                f"tools.yaml entry id={tool_id!r} failed validation: {ex}"
            ) from ex
        if entry.id in out:
            raise ValueError(f"tools.yaml: duplicate tool id {entry.id!r}")
        out[entry.id] = entry

    return out


def load_active_tools() -> dict[str, ToolManifestEntry]:
    from api.shared.vertical_loader import active_runtime

    runtime = active_runtime()
    merged: dict[str, ToolManifestEntry] = {}
    for path in runtime.pack.policy_sources:
        for tool_id, entry in load_tools_yaml(str(path)).items():
            if tool_id in merged:
                raise ValueError(
                    f"vertical {runtime.pack.name!r} policy sources contain "
                    f"duplicate tool id {tool_id!r}"
                )
            merged[tool_id] = entry
    return merged


def _reset_cache_for_tests() -> None:
    """Drop the LRU cache. Tests that rewrite tools.yaml on disk call this."""
    load_tools_yaml.cache_clear()
