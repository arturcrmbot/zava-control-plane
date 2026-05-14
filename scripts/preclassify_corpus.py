"""Pre-classify the synthetic claim corpus for the Foundry batch evaluator.

Contract
--------
Each output JSONL row has:

    {
      "claim_id": "CLM-NNNN",
      "predicted_label": "green" | "amber" | "red" | "<error>",
      "predicted_reasoning": "...",
      "policy_clause": "§3.X ...",
      "context": "<concatenated policy_search results>",
      "gold_label": "green" | "amber" | "red"
    }

This is the shape `api/server/eval/batch_runner.py::_build_jsonl_rows` consumes
(it merges in the rest of the gold metadata from `data/synthetic/claims/`).

Why a separate CLI rather than reusing `POST /api/accuracy/run`
---------------------------------------------------------------
The accuracy route pre-classifies inline before each Foundry run (~25 min for
300 claims at typical rag-classifier latency, sequentially). For the AC #4
gate run we want to:
  - run pre-classify once with bounded concurrency, then
  - run the Foundry batch evaluator several times against the same JSONL while
    iterating the prompt / retrieval, without paying for re-classification.

Invocation pattern
------------------
We copy the GHCP SDK invocation from
`api/functions/graphs/executors/agents/_wrapper.py::run_agent_session`
verbatim — fresh `CopilotClient` + ephemeral session per claim, with
`tools=[policy_search_tool, claim_get_structured_tool]` and
`skill_directories=[<rag-classifier dir>]`. We do not go through
`agent_rag_classifier.execute` because that helper drops the `policy_search`
tool-call results before returning, and we need them as `context` for the
Groundedness evaluator.

Usage
-----
    uv run python scripts/preclassify_corpus.py --sample-size 300
    uv run python scripts/preclassify_corpus.py --sample-size 5  # smoke
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

# Ensure repo root is on sys.path so `api.*` imports work when this script is
# run directly (e.g. via `uv run python scripts/preclassify_corpus.py`).
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from copilot import CopilotClient
from copilot.client import SubprocessConfig
from copilot.session import PermissionHandler
from copilot.generated.session_events import SessionEventType

from api.server.eval.evaluator_set import extract_context
from api.server.mcp_tools.claim_get_structured import claim_get_structured_tool
from api.server.mcp_tools.policy_search import policy_search_tool

log = logging.getLogger("preclassify")

_CLAIMS_DIR = _REPO_ROOT / "data" / "synthetic" / "claims"
_LABELS_CSV = _REPO_ROOT / "data" / "synthetic" / "labels.csv"
_DEFAULT_OUT = _REPO_ROOT / "data" / ".eval" / "preclassified-300.jsonl"
_SKILL_DIR = _REPO_ROOT / "api" / "server" / "skills" / "rag-classifier"
_SKILL_LABEL = "rag-classifier"
_MAX_CONCURRENCY = 5
_PER_CLAIM_TIMEOUT_S = 180.0


# ---- helpers -------------------------------------------------------------

_gh_token_cache: str | None = None


def _gh_token() -> str:
    global _gh_token_cache
    if _gh_token_cache is None:
        _gh_token_cache = subprocess.check_output(
            ["gh", "auth", "token"], text=True,
        ).strip()
    return _gh_token_cache


def _load_skill_text() -> str:
    return (_SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")


def _load_gold_labels() -> dict[str, str]:
    """Map of claim_id -> gold_label from data/synthetic/labels.csv."""
    out: dict[str, str] = {}
    with _LABELS_CSV.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            out[row["claim_id"]] = row["gold_label"]
    return out


def _extract_json(text: str) -> dict:
    """Tolerant JSON extraction — same shape as _wrapper._extract_json."""
    obj_start = text.find("{")
    obj_end = text.rfind("}")
    if obj_start >= 0 and obj_end > obj_start:
        try:
            return json.loads(text[obj_start:obj_end + 1])
        except json.JSONDecodeError:
            pass
    return {"raw": text, "parse_error": True}


def _install_tool_call_collector(session, sink: list[dict]):
    """Subscribe to TOOL_EXECUTION_START/COMPLETE and append flat dicts to `sink`."""
    open_meta: dict[str, dict] = {}

    def on_event(event) -> None:
        try:
            if event.type == SessionEventType.TOOL_EXECUTION_START:
                data = event.data
                name = getattr(data, "tool_name", "unknown")
                call_id = getattr(data, "tool_call_id", None)
                args = getattr(data, "tool_args", None) or getattr(data, "arguments", None) or ""
                if not isinstance(args, str):
                    try:
                        args = json.dumps(args)
                    except Exception:
                        args = str(args)
                if call_id:
                    open_meta[call_id] = {"name": str(name), "args": args}
            elif event.type == SessionEventType.TOOL_EXECUTION_COMPLETE:
                data = event.data
                call_id = getattr(data, "tool_call_id", None)
                meta = open_meta.pop(call_id, None) if call_id else None
                if meta is not None:
                    result_text = getattr(data, "result", None) or getattr(data, "output", None) or ""
                    if not isinstance(result_text, str):
                        try:
                            result_text = json.dumps(result_text)
                        except Exception:
                            result_text = str(result_text)
                    sink.append({
                        "name": meta["name"],
                        "args": meta["args"],
                        "result": result_text,
                        "success": getattr(data, "success", True) is not False,
                    })
        except Exception:
            pass

    return session.on(on_event)


# ---- core classifier call ------------------------------------------------

async def _classify_one(claim_id: str, skill_text: str) -> tuple[dict, str]:
    """Run rag-classifier against one claim. Returns (parsed_json, context_string).

    Mirrors `_wrapper.run_agent_session` for the rag-classifier case; the
    only difference is we surface the policy_search tool-call results as
    `context` instead of emitting them via the webhook bridge.
    """
    prompt = (
        f"Classify expense claim `{claim_id}` per your role.\n\n"
        f"Use `claim_get_structured` to load the claim record, then use "
        f"`policy_search` to retrieve the relevant §3 rule chunks for the "
        f"claim's category and market. Return exactly the JSON object specified "
        f"in your skill instructions — no prose, no markdown."
    )

    tool_calls: list[dict] = []
    config = SubprocessConfig(github_token=_gh_token(), log_level="warning")
    client = CopilotClient(config)
    async with client:
        session = await client.create_session(
            on_permission_request=PermissionHandler.approve_all,
            model="gpt-4.1",
            tools=[policy_search_tool, claim_get_structured_tool],
            system_message={"mode": "append", "content": skill_text},
            skill_directories=[str(_SKILL_DIR)],
        )
        unsub = _install_tool_call_collector(session, tool_calls)
        try:
            response_event = await session.send_and_wait(prompt, timeout=_PER_CLAIM_TIMEOUT_S)
        finally:
            try:
                unsub()
            except Exception:
                pass
            try:
                await session.disconnect()
            except Exception:
                pass

    text = ""
    if response_event and getattr(response_event, "data", None):
        text = getattr(response_event.data, "content", "") or ""

    parsed = _extract_json(text)
    context = extract_context(_SKILL_LABEL, tool_calls)
    return parsed, context


# ---- driver --------------------------------------------------------------

async def _process(
    claim_id: str,
    gold_label: str,
    skill_text: str,
    sem: asyncio.Semaphore,
    progress: dict,
) -> dict:
    async with sem:
        started = time.monotonic()
        try:
            parsed, context = await asyncio.wait_for(
                _classify_one(claim_id, skill_text),
                timeout=_PER_CLAIM_TIMEOUT_S + 30,
            )
            row = {
                "claim_id": claim_id,
                "predicted_label": parsed.get("verdict", "<error>"),
                "predicted_reasoning": parsed.get("reasoning", ""),
                "policy_clause": parsed.get("policy_clause", ""),
                "context": context,
                "gold_label": gold_label,
            }
        except Exception as ex:
            log.warning("preclassify failed for %s: %s", claim_id, ex)
            row = {
                "claim_id": claim_id,
                "predicted_label": "<error>",
                "predicted_reasoning": f"<error: {type(ex).__name__}: {ex}>",
                "policy_clause": "",
                "context": "",
                "gold_label": gold_label,
            }
        elapsed = time.monotonic() - started
        progress["done"] += 1
        correct = row["predicted_label"] == gold_label
        if correct:
            progress["correct"] += 1
        log.info(
            "[%d/%d] %s pred=%s gold=%s %s (%.1fs)",
            progress["done"], progress["total"], claim_id,
            row["predicted_label"], gold_label,
            "OK" if correct else "MISS",
            elapsed,
        )
        return row


async def _amain(sample_size: int, out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    all_claim_ids = sorted(p.stem for p in _CLAIMS_DIR.glob("CLM-*.json"))
    if not all_claim_ids:
        log.error("no claims found in %s", _CLAIMS_DIR)
        return 2

    if sample_size > len(all_claim_ids):
        log.warning(
            "sample_size %d exceeds corpus size %d; using full corpus",
            sample_size, len(all_claim_ids),
        )
        sample_size = len(all_claim_ids)

    claim_ids = all_claim_ids[:sample_size]
    gold_by_id = _load_gold_labels()
    skill_text = _load_skill_text()
    sem = asyncio.Semaphore(_MAX_CONCURRENCY)
    progress = {"total": len(claim_ids), "done": 0, "correct": 0}

    log.info(
        "preclassify: %d claims, max_concurrency=%d, out=%s",
        len(claim_ids), _MAX_CONCURRENCY, out_path,
    )

    tasks = [
        _process(cid, gold_by_id.get(cid, ""), skill_text, sem, progress)
        for cid in claim_ids
    ]

    started = time.monotonic()
    rows = await asyncio.gather(*tasks)
    elapsed = time.monotonic() - started

    # Preserve canonical claim_id order in the output.
    rows.sort(key=lambda r: r["claim_id"])
    with out_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    n = len(rows)
    correct = progress["correct"]
    log.info(
        "wrote %d rows to %s in %.1fs — predicted_label==gold_label on %d/%d (%.1f%%)",
        n, out_path, elapsed, correct, n, (100.0 * correct / n) if n else 0.0,
    )
    return 0


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--sample-size", type=int, default=300,
        help="Number of claims to classify (default: 300, the full corpus).",
    )
    p.add_argument(
        "--out", type=Path, default=_DEFAULT_OUT,
        help=f"Output JSONL path (default: {_DEFAULT_OUT.relative_to(_REPO_ROOT)}).",
    )
    p.add_argument(
        "--log-level", default="INFO",
        help="Logging level (DEBUG, INFO, WARNING). Default: INFO.",
    )
    return p


def main() -> int:
    args = _build_argparser().parse_args()
    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return asyncio.run(_amain(args.sample_size, args.out))


if __name__ == "__main__":
    raise SystemExit(main())
