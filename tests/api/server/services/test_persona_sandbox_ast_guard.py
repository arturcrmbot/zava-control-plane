"""AST whitelist hardening for the persona sandbox.

Tests defence-in-depth on top of ``_DECISION_BUILTINS``: the AST guard
in ``_validate_persona_source`` must reject sandbox-escape patterns
(reflection via dunders, imports, class definitions, global / nonlocal
declarations) at compile time, before ``compile()`` runs.

Each test lives in its own block so a pytest failure points at exactly
which escape vector regressed.
"""
from __future__ import annotations

import textwrap

import pytest

from api.server.services.persona_responder import (
    _validate_persona_source,
    _compile_decision_policy,
    _compile_summary_policy,
    _compile_voice_render,
)


# ---------------------------------------------------------------------------
# Negative tests: each escape vector must raise ValueError at validate time
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "vector,source",
    [
        # Classic Python sandbox-escape: walk the type hierarchy.
        ("__class__", "decision = ().__class__\nreason = 'x'"),
        # Reach `object` then arbitrary subclasses.
        ("__bases__", "x = (1).__class__.__bases__\ndecision = 'approve'\nreason = 'r'"),
        # Subclass walk → reach `<class 'subprocess.Popen'>` etc.
        ("__subclasses__", "x = ().__class__.__mro__[1].__subclasses__()\ndecision = 'approve'\nreason = 'r'"),
        # Direct MRO walk.
        ("__mro__", "decision = (1).__class__.__mro__\nreason = 'r'"),
        # Reach the calling frame's globals via traceback.
        (
            "__traceback__",
            textwrap.dedent("""
                try:
                    raise ValueError('x')
                except Exception as e:
                    g = e.__traceback__
                decision = 'approve'
                reason = 'r'
            """),
        ),
        # __globals__ on a function reaches module-level state.
        (
            "__globals__",
            textwrap.dedent("""
                f = lambda: None
                g = f.__globals__
                decision = 'approve'
                reason = 'r'
            """),
        ),
        # __code__ access → could be used to recompile / replay.
        ("__code__", "f = lambda: 1\nx = f.__code__\ndecision = 'approve'\nreason = 'r'"),
        # __builtins__ — even if replaced, the name shouldn't be reachable.
        ("__builtins__", "x = ().__class__.__builtins__\ndecision = 'approve'\nreason = 'r'"),
        # __dict__ access on instances.
        ("__dict__", "d = {}.__dict__\ndecision = 'approve'\nreason = 'r'"),
    ],
)
def test_dunder_attribute_access_rejected(vector, source):
    """Every dunder-attribute access in the AST must be rejected."""
    with pytest.raises(ValueError) as excinfo:
        _validate_persona_source(source, role="test_role", kind="decision_policy")
    msg = str(excinfo.value)
    assert "persona 'test_role' decision_policy" in msg
    assert "sandbox-escape vector" in msg
    assert vector in msg


def test_import_statement_rejected():
    src = "import os\ndecision = 'approve'\nreason = 'r'"
    with pytest.raises(ValueError, match=r"`import os` statement"):
        _validate_persona_source(src, role="r", kind="decision_policy")


def test_from_import_rejected():
    src = "from os import path\ndecision = 'approve'\nreason = 'r'"
    with pytest.raises(ValueError, match=r"`from os import \.\.\.` statement"):
        _validate_persona_source(src, role="r", kind="decision_policy")


def test_class_definition_rejected():
    src = textwrap.dedent("""
        class Hack:
            pass
        decision = 'approve'
        reason = 'r'
    """)
    with pytest.raises(ValueError, match=r"`class Hack` definition"):
        _validate_persona_source(src, role="r", kind="decision_policy")


def test_global_declaration_rejected():
    src = textwrap.dedent("""
        def f():
            global decision
            decision = 'approve'
        f()
        reason = 'r'
    """)
    with pytest.raises(ValueError, match=r"`global` declaration"):
        _validate_persona_source(src, role="r", kind="decision_policy")


def test_nonlocal_declaration_rejected():
    src = textwrap.dedent("""
        def outer():
            x = 1
            def inner():
                nonlocal x
                x = 2
            inner()
            return x
        decision = 'approve' if outer() == 2 else 'reject'
        reason = 'r'
    """)
    with pytest.raises(ValueError, match=r"`nonlocal` declaration"):
        _validate_persona_source(src, role="r", kind="decision_policy")


def test_syntax_error_surfaces_clearly():
    src = "decision =\n"  # incomplete
    with pytest.raises(ValueError, match=r"persona 'r' decision_policy fails to parse"):
        _validate_persona_source(src, role="r", kind="decision_policy")


# ---------------------------------------------------------------------------
# Positive tests: legitimate persona patterns must NOT be rejected
# ---------------------------------------------------------------------------


def test_normal_attribute_access_allowed():
    """Real personae call `payload.get(...)`, `auth.get(...)` — the
    common attribute pattern. Must not be blocked."""
    src = textwrap.dedent("""
        payload = (context or {}).get("invoice") or {}
        amount = payload.get("amount") or 0
        if amount > 100:
            decision = "escalate"
            reason = "amount over threshold"
        else:
            decision = "approve"
            reason = "ok"
    """)
    # No exception — validation passes.
    _validate_persona_source(src, role="r", kind="decision_policy")


def test_try_except_allowed():
    """Personae use try/except for value parsing — must not be blocked."""
    src = textwrap.dedent("""
        raw = (context or {}).get("amount")
        try:
            value = float(raw)
        except (TypeError, ValueError):
            value = None
        decision = "approve" if value else "reject"
        reason = "parsed" if value else "no value"
    """)
    _validate_persona_source(src, role="r", kind="decision_policy")


def test_lambda_and_inner_def_allowed():
    """Inner functions / lambdas are fine as long as no forbidden patterns."""
    src = textwrap.dedent("""
        squash = lambda v: round(float(v or 0), 2)
        amount = squash((context or {}).get("amount"))
        decision = "approve"
        reason = str(amount)
    """)
    _validate_persona_source(src, role="r", kind="decision_policy")


def test_subscript_with_string_key_allowed():
    """Dict subscript with a regular string key is fine; only dunder
    *attribute* access is blocked."""
    src = textwrap.dedent("""
        d = {"foo": 1}
        x = d["foo"]
        decision = "approve"
        reason = "x={}".format(x)
    """)
    _validate_persona_source(src, role="r", kind="decision_policy")


# ---------------------------------------------------------------------------
# End-to-end: the three compile entry points must invoke the guard
# ---------------------------------------------------------------------------


def test_decision_policy_compile_rejects_dunder():
    src = "decision = ().__class__\nreason = 'x'"
    with pytest.raises(ValueError, match=r"sandbox-escape vector"):
        _compile_decision_policy(role="r", source=src)


def test_summary_policy_compile_rejects_dunder():
    src = "summary = {}.__dict__"
    with pytest.raises(ValueError, match=r"sandbox-escape vector"):
        _compile_summary_policy(role="r", source=src)


def test_voice_render_compile_rejects_dunder():
    src = "body = ().__class__"
    with pytest.raises(ValueError, match=r"sandbox-escape vector"):
        _compile_voice_render(role="r", source=src)


# ---------------------------------------------------------------------------
# Regression: every shipped persona must still load
# ---------------------------------------------------------------------------


def test_all_shipped_personae_still_load():
    """The whole point of auditing the AST nodes used by real personae
    before adding the guard was to confirm zero use of the forbidden
    patterns. This regression test re-runs the gate against every
    shipped SKILL.md so a future persona can't accidentally introduce a
    forbidden pattern without CI failing."""
    import re
    import pathlib

    persona_root = pathlib.Path(__file__).resolve().parents[3] / "api" / "server" / "personae"
    failures: list[str] = []

    for skill_md in persona_root.rglob("SKILL.md"):
        text = skill_md.read_text(encoding="utf-8")
        for tag in ("decision_policy", "summary_policy", "voice_render"):
            m = re.search(rf"^{tag}:\s*\|\s*\n((?:    .+\n|\n)*)", text, re.MULTILINE)
            if not m:
                continue
            block = "\n".join(
                line[4:] if line.startswith("    ") else line
                for line in m.group(1).splitlines()
            )
            try:
                _validate_persona_source(block, role=skill_md.parent.name, kind=tag)
            except ValueError as ex:
                failures.append(f"{skill_md.parent.name}/{tag}: {ex}")

    assert not failures, (
        f"{len(failures)} shipped persona(e) violate the AST whitelist:\n"
        + "\n".join(failures)
    )
