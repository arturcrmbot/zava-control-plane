"""Smoke-check mem0 against the existing Azure OpenAI keyless setup.

- LLM:      gpt-4o on azureaiserviceforcontentunderstanding (Sweden Central)
- Embedder: text-embedding-3-large on the same endpoint (3072 dims)
- Auth:     DefaultAzureCredential (`az login`); mem0 auto-falls-back when
            api_key is empty.
- Storage:  local on-disk qdrant under a tmp dir (no Azure storage cost).
"""
from __future__ import annotations

import os
import sys
import tempfile

AOAI_ENDPOINT = "https://azureaiserviceforcontentunderstanding.services.ai.azure.com"
AOAI_API_VERSION = "2024-10-21"
LLM_DEPLOYMENT = "gpt-4o"
EMBED_DEPLOYMENT = "text-embedding-3-large"
EMBED_DIMS = 3072


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="mem0-smoke-")
    os.environ["MEM0_DIR"] = tmp
    from mem0 import Memory

    config = {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "path": f"{tmp}/qdrant",
                "on_disk": True,
                "embedding_model_dims": EMBED_DIMS,
            },
        },
        "llm": {
            "provider": "azure_openai",
            "config": {
                "model": LLM_DEPLOYMENT,
                "azure_kwargs": {
                    "api_key": "",
                    "azure_deployment": LLM_DEPLOYMENT,
                    "azure_endpoint": AOAI_ENDPOINT,
                    "api_version": AOAI_API_VERSION,
                },
            },
        },
        "embedder": {
            "provider": "azure_openai",
            "config": {
                "model": EMBED_DEPLOYMENT,
                "embedding_dims": EMBED_DIMS,
                "azure_kwargs": {
                    "api_key": "",
                    "azure_deployment": EMBED_DEPLOYMENT,
                    "azure_endpoint": AOAI_ENDPOINT,
                    "api_version": AOAI_API_VERSION,
                },
            },
        },
        "history_db_path": f"{tmp}/history.db",
    }
    memory = Memory.from_config(config)
    print(f"instantiated Memory at {tmp}")

    add_result = memory.add(
        messages="vendors from agency Acme consistently miss reference checks",
        user_id="lesson-store",
        metadata={"domain": "hiring", "lesson_id": "L-SMOKE-1"},
        infer=False,
    )
    print(f"add() returned: {add_result!r}")

    search_result = memory.search(
        query="reference checks",
        user_id="lesson-store",
        limit=5,
    )
    hits = search_result.get("results", []) if isinstance(search_result, dict) else []
    print(f"search() returned {len(hits)} hit(s)")
    bodies = [h.get("memory") for h in hits]
    print(f"  bodies: {bodies}")

    if any("reference checks" in (b or "") for b in bodies):
        print("roundtrip ok")
        return 0
    print("roundtrip FAILED \u2014 search did not return the added memory", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
