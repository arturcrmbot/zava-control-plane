"""Shared Mem0 backend builder for domain memories."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def build_default_memory(data_dir: Path | None = None) -> Any:
    """Build a `mem0.Memory` wired to Azure OpenAI + file-backed Chroma."""
    from mem0 import Memory

    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    llm_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    embed_deployment = os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
    if not endpoint:
        raise RuntimeError("AZURE_OPENAI_ENDPOINT not set")
    if not embed_deployment:
        raise RuntimeError("AZURE_OPENAI_EMBED_DEPLOYMENT not set")

    default_chroma_dir = (
        data_dir / "mem0" / "chroma"
        if data_dir is not None
        else Path("data/runtime/agency/mem0/chroma")
    )
    chroma_dir = Path(os.getenv("MEM0_CHROMA_DIR", str(default_chroma_dir)))
    chroma_dir.mkdir(parents=True, exist_ok=True)

    azure_kwargs = {
        "azure_deployment": llm_deployment,
        "azure_endpoint": endpoint,
        "api_version": api_version,
        "api_key": "",
    }
    embed_azure_kwargs = {
        "azure_deployment": embed_deployment,
        "azure_endpoint": endpoint,
        "api_version": api_version,
        "api_key": "",
    }
    config = {
        "llm": {
            "provider": "azure_openai",
            "config": {
                "model": llm_deployment,
                "azure_kwargs": azure_kwargs,
            },
        },
        "embedder": {
            "provider": "azure_openai",
            "config": {
                "model": embed_deployment,
                "embedding_dims": 3072,
                "azure_kwargs": embed_azure_kwargs,
            },
        },
        "vector_store": {
            "provider": "chroma",
            "config": {
                "collection_name": "lesson_store",
                "path": str(chroma_dir),
            },
        },
    }
    return Memory.from_config(config)
