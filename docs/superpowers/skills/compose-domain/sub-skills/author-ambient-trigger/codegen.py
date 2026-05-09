"""Codegen for author-ambient-trigger (TASK-024).

Emits a sentinel-bracketed Python block for one ``AmbientAgent(...)``
declaration that lands at
``api/server/services/ambient_agents/<function>.py`` (creating the
file when missing). The block is guarded by ``hasattr(_module,
"AmbientAgent")`` so the rendered file imports cleanly before
Phase 3 lands the primitive.

Idempotent append: if a sentinel for the same workflow_type already
exists in the file, :func:`apply_ambient` is a no-op.
"""
from __future__ import annotations

from pathlib import Path

__all__ = ["render_ambient", "apply_ambient", "render_module_skeleton"]


_FILE_HEADER = '''"""Ambient agents owned by FUNCTIONS["{function}"].

Auto-generated stubs from compose-domain v4 author-ambient-trigger.
The ``AmbientAgent`` primitive is defined by Phase 3
(api.server.services.ambient_agents.runtime). Until then the
constructors below are guarded behind ``hasattr(_module,
"AmbientAgent")`` so this module is import-clean.
"""
from __future__ import annotations

from api.server.services import ambient_agents as _module

ambient_registry: list = []
'''


def _trigger_repr(trig: dict) -> str:
    kind = trig["kind"]
    if kind == "bus":
        return (
            "{"
            + f'"kind": "bus", "event_type": {trig["event_type"]!r}, '
            + f'"filter": {trig.get("filter", "")!r}'
            + "}"
        )
    if kind == "cypher":
        return (
            "{"
            + f'"kind": "cypher", "pattern": {trig["pattern"]!r}, '
            + f'"sweep_seconds": {int(trig["sweep_seconds"])}'
            + "}"
        )
    if kind == "cadence":
        return (
            "{"
            + f'"kind": "cadence", "cron": {trig["cron"]!r}'
            + "}"
        )
    raise ValueError(f"unknown trigger kind: {kind!r}")


def render_module_skeleton(function: str) -> str:
    return _FILE_HEADER.format(function=function)


def render_ambient(brief: dict) -> tuple[Path, str]:
    """Return ``(file_path, append_block)``. The block carries a
    sentinel header + footer so subsequent runs can detect-and-skip.
    """
    ambient = brief["ambient"]
    function = ambient["function"]
    workflow_type = brief["domain"]["workflow_type"]
    name = ambient["name"]
    reasoning_skill = ambient.get("reasoning_skill")
    spawnable = list(ambient.get("spawnable_workflow_types") or [])
    triggers = list(ambient.get("triggers") or [])

    triggers_repr = "[\n        " + ",\n        ".join(
        _trigger_repr(t) for t in triggers
    ) + ",\n    ]"

    sentinel = f"# compose-domain:ambient:{workflow_type}"
    block = (
        f"\n\n{sentinel} BEGIN\n"
        f'if hasattr(_module, "AmbientAgent"):\n'
        f"    ambient_registry.append(_module.AmbientAgent(\n"
        f"        name={name!r},\n"
        f"        function={function!r},\n"
        f"        reasoning_skill={reasoning_skill!r},\n"
        f"        spawnable_workflow_types={spawnable!r},\n"
        f"        triggers={triggers_repr},\n"
        f"    ))\n"
        f"{sentinel} END\n"
    )
    file_path = Path("api/server/services/ambient_agents") / f"{function}.py"
    return file_path, block


def apply_ambient(brief: dict, repo_root: Path) -> Path:
    """Write the rendered block under ``repo_root``. Idempotent: skips
    when the sentinel for this workflow_type is already present.
    """
    rel_path, block = render_ambient(brief)
    full = repo_root / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    if not full.exists():
        full.write_text(render_module_skeleton(brief["ambient"]["function"]))

    workflow_type = brief["domain"]["workflow_type"]
    sentinel = f"# compose-domain:ambient:{workflow_type}"
    existing = full.read_text()
    if sentinel in existing:
        return full
    full.write_text(existing + block)
    return full
