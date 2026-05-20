"""Dream pass consolidator — Anthropic-style memory cleanup.

Reads all memories from a DomainMemory store, sends them to an LLM
with instructions to:
  1. Merge duplicates (keep the most precise version)
  2. Resolve contradictions (keep the latest/most evidence-backed)
  3. Prune stale or overly specific entries
  4. Surface new cross-case insights

The output replaces the input store (auto-accepted). This mirrors
Anthropic's dream architecture where the dream produces a new memory
store that replaces the old one.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

log = logging.getLogger(__name__)


async def consolidate_memories(
    *,
    domain_memory: Any,
    llm_consolidate: Callable[[list[str]], Awaitable[list[str]]],
) -> dict[str, Any]:
    """Run one dream consolidation pass.

    Args:
        domain_memory: The DomainMemory store to consolidate.
        llm_consolidate: Async function that takes a list of memory
            strings and returns a consolidated list.

    Returns:
        Dict with input_count, output_count, domain, timestamp.
    """
    domain = domain_memory.domain
    all_memories = domain_memory.list_all(limit=500)

    if not all_memories:
        log.info("dream[%s]: no memories to consolidate", domain)
        return {
            "domain": domain,
            "input_count": 0,
            "output_count": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    valid_memories = [
        (m["id"], m["memory"])
        for m in all_memories
        if m.get("id") and m.get("memory")
    ]
    memory_ids = [memory_id for memory_id, _ in valid_memories]
    memory_texts = [text for _, text in valid_memories]

    if not memory_texts:
        log.info("dream[%s]: no valid memories to consolidate", domain)
        return {
            "domain": domain,
            "input_count": 0,
            "output_count": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    log.info("dream[%s]: consolidating %d memories", domain, len(memory_texts))

    try:
        consolidated = await llm_consolidate(memory_texts)
    except Exception as e:
        log.exception("dream[%s]: LLM consolidation failed", domain)
        return {
            "domain": domain,
            "input_count": len(memory_texts),
            "output_count": 0,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    consolidated_texts = [text.strip() for text in consolidated if text.strip()]
    if not consolidated_texts:
        log.warning("dream[%s]: LLM returned empty consolidation", domain)
        return {
            "domain": domain,
            "input_count": len(memory_texts),
            "output_count": 0,
            "error": "LLM returned empty consolidation",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    written = 0
    written_ids: list[str] = []
    try:
        for text in consolidated_texts:
            results = domain_memory.add_distilled(
                text,
                metadata={
                    "source": "dream-consolidation",
                    "consolidated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            written += 1
            written_ids.extend(r["id"] for r in results if r.get("id"))
    except Exception as exc:
        for memory_id in written_ids:
            try:
                domain_memory.delete(memory_id)
            except Exception:
                log.warning("dream[%s]: failed to rollback memory %s", domain, memory_id)
        log.exception("dream[%s]: failed to write consolidated memories", domain)
        return {
            "domain": domain,
            "input_count": len(memory_texts),
            "output_count": 0,
            "error": str(exc),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    delete_errors: list[str] = []
    for mid in memory_ids:
        try:
            domain_memory.delete(mid)
        except Exception as exc:
            log.warning("dream[%s]: failed to delete memory %s", domain, mid)
            delete_errors.append(f"{mid}: {exc}")

    if delete_errors:
        return {
            "domain": domain,
            "input_count": len(memory_texts),
            "output_count": written,
            "error": "; ".join(delete_errors),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    result = {
        "domain": domain,
        "input_count": len(memory_texts),
        "output_count": written,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    log.info(
        "dream[%s]: %d → %d memories",
        domain,
        result["input_count"],
        result["output_count"],
    )
    return result


def build_consolidation_prompt(memory_texts: list[str]) -> str:
    """Build the system prompt for the consolidation LLM call."""
    memories_block = "\n".join(f"- {m}" for m in memory_texts)

    return f"""You are a memory consolidation agent. You are reviewing the accumulated memories of an AI agent system that processes decisions in a corporate workflow.

Below are the current memories. Your job is to produce a CLEANED, CONSOLIDATED list:

1. **Merge duplicates** — if multiple memories say essentially the same thing, keep the most precise version
2. **Resolve contradictions** — if two memories conflict, keep the one with more evidence or the more recent insight
3. **Prune overly specific** — remove memories that are about one specific case and don't generalize (e.g. "Declined candidate C-123" — unless there's a lesson in WHY)
4. **Surface insights** — if you notice a pattern across multiple memories, add a new consolidated memory that captures the insight
5. **Keep it concise** — each memory should be one clear, actionable sentence

Current memories:
{memories_block}

Return a JSON array of strings — the consolidated memory list. No explanation, just the array.
Example: ["When CV is empty, decline unless other strong signals exist.", "Low voice scores below 2.0 correlate with poor interview performance."]"""
