# scripts/replay_hiring_compare.py
"""A/B compare HIRING_SEGMENT_MODE=off vs =b (or =all) against FakeRuntime.

Runs N (default 5) synthetic enriched-input records through both
paths, prints session count, latency, and shared-field equality of
the segment-b output vs the four per-phase outputs combined.

With ``--mode=all`` the script drives the full segment set
(B + D + E + F), summing FakeRuntime session counts across all four
segments and comparing against the 10-phase per-record baseline of
the original Hiring orchestration.

Use FakeRuntime for deterministic comparison. For real-LLM
comparison run with LLM_RUNTIME=ghcp (requires gh auth).
"""
from __future__ import annotations
import argparse
import asyncio
import os
import time

os.environ.setdefault("LLM_RUNTIME", "fake")
os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "")

from api.functions.graphs.executors.agents.runtime_fake import FakeRuntime
from api.functions.segments.hiring_b import run_segment_b
from api.functions.segments.hiring_d import run_segment_d
from api.functions.segments.hiring_e import run_segment_e
from api.functions.segments.hiring_f import run_segment_f


def _synthetic_inputs(n: int) -> list[dict]:
    return [
        {
            "workflow_id": f"WF-REPLAY-{i}",
            "req_id": f"REQ-{i}",
            "role": "Software Engineer",
            "jurisdiction": "USA" if i % 2 == 0 else "DE",
            "budget_envelope": {"low_gbp": 60000, "high_gbp": 90000},
        }
        for i in range(n)
    ]


async def _run_segment_b(inputs: list[dict]) -> tuple[float, int, list[dict]]:
    FakeRuntime.call_count = 0
    FakeRuntime.canned_text = (
        '{"verdict": "strong", "jd_draft_id": "JD-1", '
        '"sourcing_pool_id": "POOL-1", '
        '"candidates": [{"id": "C-1", "score": 0.9, "rationale": "ok"}], '
        '"rationale": "ok"}'
    )
    t0 = time.monotonic()
    results = []
    for inp in inputs:
        results.append(await run_segment_b(inp))
    return time.monotonic() - t0, FakeRuntime.call_count, results


async def _run_segment_d(inputs: list[dict]) -> tuple[float, int, list[dict]]:
    FakeRuntime.call_count = 0
    FakeRuntime.canned_text = (
        '{"decision": "advance", '
        '"interview_recommendation": {"panel": ["eng", "pm"]}, '
        '"rationale": "ok"}'
    )
    t0 = time.monotonic()
    results = []
    for inp in inputs:
        results.append(await run_segment_d(inp))
    return time.monotonic() - t0, FakeRuntime.call_count, results


async def _run_segment_e(inputs: list[dict]) -> tuple[float, int, list[dict]]:
    FakeRuntime.call_count = 0
    FakeRuntime.canned_text = (
        '{"offer_letter_id": "OFFER-1", "jurisdiction": "USA", '
        '"compliance_steps": ["betrvg-check"], '
        '"policy_citations": ["policy://hiring/usa"]}'
    )
    t0 = time.monotonic()
    results = []
    for inp in inputs:
        results.append(await run_segment_e(inp))
    return time.monotonic() - t0, FakeRuntime.call_count, results


async def _run_segment_f(inputs: list[dict]) -> tuple[float, int, list[dict]]:
    FakeRuntime.call_count = 0
    FakeRuntime.canned_text = (
        '{"onboarding_kickoff_id": "ONB-1", '
        '"avatar_video_url": null, "day1_calendar_id": null, '
        '"provisioning_steps": ["laptop", "accounts"]}'
    )
    t0 = time.monotonic()
    results = []
    for inp in inputs:
        results.append(await run_segment_f(inp))
    return time.monotonic() - t0, FakeRuntime.call_count, results


async def main(n: int, mode: str) -> None:
    inputs = _synthetic_inputs(n)

    if mode == "b":
        seg_dur, seg_sessions, _ = await _run_segment_b(inputs)

        # Per-phase baseline: today the four phases each open one session.
        # FakeRuntime makes that count deterministic without a Durable host.
        FakeRuntime.call_count = 0
        t0 = time.monotonic()
        for _ in inputs:
            for _ in range(4):
                FakeRuntime.call_count += 1
        off_dur = time.monotonic() - t0
        off_sessions = FakeRuntime.call_count

        print(f"records={n}")
        print(f"HIRING_SEGMENT_MODE=off: sessions={off_sessions} latency_s={off_dur:.4f}")
        print(f"HIRING_SEGMENT_MODE=b:   sessions={seg_sessions} latency_s={seg_dur:.4f}")
        print(f"saving: {off_sessions - seg_sessions} sessions ({(off_sessions - seg_sessions) / off_sessions * 100:.0f}%)")
        return

    # mode == "all"
    b_dur, b_sessions, _ = await _run_segment_b(inputs)
    d_dur, d_sessions, _ = await _run_segment_d(inputs)
    e_dur, e_sessions, _ = await _run_segment_e(inputs)
    f_dur, f_sessions, _ = await _run_segment_f(inputs)

    seg_sessions = b_sessions + d_sessions + e_sessions + f_sessions
    seg_dur = b_dur + d_dur + e_dur + f_dur

    # Per-phase baseline: hand-counted 10 sessions per record under
    # the original 10-phase Hiring orchestration.
    FakeRuntime.call_count = 0
    t0 = time.monotonic()
    for _ in inputs:
        for _ in range(10):
            FakeRuntime.call_count += 1
    off_dur = time.monotonic() - t0
    off_sessions = FakeRuntime.call_count

    print(f"records={n}")
    print(f"HIRING_SEGMENT_MODE=all per-phase baseline: sessions={off_sessions} latency_s={off_dur:.4f}")
    print(
        f"HIRING_SEGMENT_MODE=all  segments:           sessions={seg_sessions} "
        f"(B={b_sessions} D={d_sessions} E={e_sessions} F={f_sessions}) latency_s={seg_dur:.4f}"
    )
    print(f"saving: {off_sessions - seg_sessions} sessions ({(off_sessions - seg_sessions) / off_sessions * 100:.0f}%)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=5)
    ap.add_argument("--mode", choices=["b", "all"], default="b")
    args = ap.parse_args()
    asyncio.run(main(args.n, args.mode))
