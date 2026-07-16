"""api/shared/functions.py — compatibility adapter over the active vertical pack.

This module is a thin adapter, not a registry. It:

- re-exports the ``Function``/``PersonaTree`` contract types from
  :mod:`api.shared.function_contracts`
- exposes ``FUNCTIONS`` as the *active pack's* organisational-function
  mapping only — sourced from ``active_runtime().pack.organisation_functions``
- exposes ``_validate_persona_hierarchy()``, a validator that walks every
  ``Function.persona_hierarchy`` and asserts every role resolves to a
  SKILL.md under one of the active pack's ``personae_roots``. The
  ``legacy`` function carries the sentinel ``__legacy__`` role and is
  skipped.

Canonical function declarations live in ``verticals/agency/functions.py``
and ``verticals/telco/functions.py``. This module contains no business
declarations, no all-vertical registry, and does not parse the environment
itself.

Function → domain back-references are wired once, while building the
selected pack, via ``verticals._helpers.wire_domain_functions`` (invoked
from each pack's ``manifest.build_pack()``). There is no boot-time mutation
across a global domain dictionary here — every ``Domain`` the active pack
exposes already carries its ``function`` back-reference.

It does not register Azure Functions; that is the separate
``durable_functions`` field and Functions composition root.
"""
from __future__ import annotations

from pathlib import Path

from api.shared.function_contracts import Function, PersonaTree
from api.shared.vertical_loader import active_runtime

FUNCTIONS: dict[str, Function] = active_runtime().pack.organisation_functions


# --------------------------------------------------------------------------
# Boot-time-safe validators — callable on demand, no side effects at import.
# --------------------------------------------------------------------------

_LEGACY_SENTINEL = "__legacy__"


def _walk_persona_tree(
    node: PersonaTree,
    fn_name: str,
    roots: tuple[Path, ...],
) -> None:
    if node.role == _LEGACY_SENTINEL:
        return
    if not any((root / node.role / "SKILL.md").is_file() for root in roots):
        raise ValueError(
            f"FUNCTIONS['{fn_name}'].persona_hierarchy references unknown persona '{node.role}'"
        )
    for child in node.manages:
        _walk_persona_tree(child, fn_name, roots)


def _validate_persona_hierarchy() -> None:
    """Assert every PersonaTree role resolves to a real SKILL.md.

    The ``legacy`` function carries the ``__legacy__`` sentinel and is
    skipped (special-cased).
    """
    roots = active_runtime().pack.personae_roots
    for fn_name, fn in FUNCTIONS.items():
        _walk_persona_tree(fn.persona_hierarchy, fn_name, roots)
