"""Deterministic fallback consolidator — works without Azure OpenAI.

The default ``consolidate_memories`` path in ``dream_consolidator.py``
calls Azure OpenAI to summarise/dedup. On a laptop with no cloud creds,
that call fails and nothing is reconciled.

This module provides ``fallback_consolidate(texts)``: a pure-Python
rule-based summariser that

  1. Strips bracket-prefix noise (``[role] VERDICT``) to compute a
     tokenised signature per entry.
  2. Groups entries by Jaccard-similar signatures (≥ 0.6 overlap).
  3. For each group of size ≥ 2, emits one distilled lesson:
     ``"Observed N× — <verdict-counts> for <gate>: <shared signals>"``.
  4. Groups of size 1 pass through unchanged.
  5. Output is always strictly smaller than (or equal to) input on
     repeated patterns — so reconciliation is observable.

Used by the cadence loop and the ``/api/memory/v2/dream`` route when
the Azure OpenAI consolidator is unavailable.
"""
from __future__ import annotations

import re
from collections import Counter

_BRACKET_RE = re.compile(r"^\[[^\]]+\]\s*")
_VERDICT_RE = re.compile(r"\b(approve|reject|escalate|hold|wait|approved|rejected)\b", re.I)
_GATE_RE = re.compile(r"\bfor\s+([a-z0-9_\-]+)", re.I)
_SIG_RE = re.compile(r"\b([a-z_]+)=([^,\s]+)", re.I)


def _normalize(text: str) -> str:
    return _BRACKET_RE.sub("", text or "").strip().lower()


def _tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", _normalize(text)) if len(t) > 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


_VERDICT_CANONICAL = {
    "approve": "approve", "approved": "approve",
    "reject": "reject", "rejected": "reject",
    "escalate": "escalate",
    "hold": "hold", "wait": "wait",
}


def fallback_consolidate(texts: list[str], *, threshold: float = 0.45) -> list[str]:
    """Return a smaller, deduplicated list of memory texts.

    Pure-Python — no LLM. Used when Azure OpenAI isn't configured or
    fails. Designed so that on patterned demo data the output is
    visibly shorter than the input.
    """
    if not texts:
        return []

    entries = [(t, _tokens(t)) for t in texts if t and t.strip()]
    if not entries:
        return []

    # Greedy clustering by token Jaccard similarity.
    clusters: list[list[tuple[str, set[str]]]] = []
    for text, toks in entries:
        placed = False
        for cluster in clusters:
            # Compare against cluster centroid (first entry's tokens).
            if _jaccard(toks, cluster[0][1]) >= threshold:
                cluster.append((text, toks))
                placed = True
                break
        if not placed:
            clusters.append([(text, toks)])

    out: list[str] = []
    for cluster in clusters:
        if len(cluster) == 1:
            out.append(cluster[0][0])
            continue
        # Group lesson: count verdicts + extract gate + intersect signals.
        verdicts: Counter[str] = Counter()
        gates: Counter[str] = Counter()
        signal_keys: Counter[str] = Counter()
        for text, _ in cluster:
            v = _VERDICT_RE.search(text)
            if v:
                key = _VERDICT_CANONICAL.get(v.group(1).lower(), v.group(1).lower())
                verdicts[key] += 1
            g = _GATE_RE.search(text)
            if g:
                gates[g.group(1).lower()] += 1
            for k, _v in _SIG_RE.findall(text):
                signal_keys[k.lower()] += 1
        verdict_str = ", ".join(
            f"{c}× {v}" for v, c in verdicts.most_common()
        ) or "various verdicts"
        gate_str = (
            gates.most_common(1)[0][0] if gates else "various gates"
        )
        sig_str = (
            "; signals: " + ", ".join(
                f"{k}" for k, _ in signal_keys.most_common(3)
            )
            if signal_keys else ""
        )
        out.append(
            f"LESSON ({len(cluster)} cases): {verdict_str} for {gate_str}"
            f"{sig_str}"
        )
    return out
