"""ULID monotonic-property test (TASK-008b).

Locks PAT-001's monotonic guarantee independent of the dedupe path in
``EntityGraph.record_decision`` (which lands in TASK-007). ``_ulid`` is a
private module-level helper; importing it directly is intentional.
"""
from __future__ import annotations

import re

from api.server.services.entity_graph import _ulid


# Crockford base32 alphabet — no I, L, O, U so 26 chars is unambiguous.
_CROCKFORD_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


def test_ulid_shape() -> None:
    value = _ulid()
    assert len(value) == 26
    assert _CROCKFORD_RE.match(value), f"not Crockford-base32: {value!r}"
    # Belt-and-braces: explicitly forbid the four excluded characters.
    for forbidden in "ILOU":
        assert forbidden not in value


def test_ulid_is_monotonic_over_1000_calls() -> None:
    values = [_ulid() for _ in range(1000)]
    # All distinct.
    assert len(set(values)) == 1000
    # Sort order matches mint order — the headline monotonic property.
    assert values == sorted(values)


def test_ulid_no_collisions_in_tight_loop() -> None:
    # In a tight Python loop many calls land in the same millisecond. The
    # in-ms counter must still keep them all distinct.
    values = [_ulid() for _ in range(5000)]
    assert len(set(values)) == 5000
    # Verify strict monotonicity — same ms calls are lexicographically increasing.
    assert values == sorted(values)


def test_ulid_alphabet_constants() -> None:
    # Belt-and-braces check on the alphabet — guards against accidental
    # edits that would re-introduce I/L/O/U.
    from api.server.services.entity_graph import _CROCKFORD_ALPHABET

    assert _CROCKFORD_ALPHABET == "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    assert len(_CROCKFORD_ALPHABET) == 32
    for forbidden in "ILOU":
        assert forbidden not in _CROCKFORD_ALPHABET
