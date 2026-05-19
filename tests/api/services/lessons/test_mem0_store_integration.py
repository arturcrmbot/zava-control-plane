"""End-to-end integration test for Mem0LessonStore.

Runs against the real Azure OpenAI deployment the substrate uses
(azureaiserviceforcontentunderstanding, Sweden Central). Skipped by
default; opt-in with::

    uv run pytest -m foundry tests/api/services/lessons/test_mem0_store_integration.py

Requires:
- `az login` (DefaultAzureCredential)
- Access to the gpt-4o + text-embedding-3-large deployments on the
  configured endpoint
"""
from __future__ import annotations

import os
import tempfile

import pytest

from api.server.services.lessons.mem0_store import Mem0LessonStore
from api.server.services.lessons.types import LessonScope

pytestmark = pytest.mark.foundry

AOAI_ENDPOINT = "https://azureaiserviceforcontentunderstanding.services.ai.azure.com"
AOAI_API_VERSION = "2024-10-21"
EMBED_DEPLOYMENT = "text-embedding-3-large"
EMBED_DIMS = 3072
LLM_DEPLOYMENT = "gpt-4o"


@pytest.fixture(scope="module")
def real_memory():
    """Build a real mem0.Memory backed by Azure OpenAI + on-disk qdrant.

    Module-scoped: qdrant-local refuses to open two instances in the
    same process, so all tests in this file share one Memory.
    """
    tmp = tempfile.mkdtemp(prefix="mem0-lessonstore-")
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
    return Memory.from_config(config)


def test_add_then_search_returns_lesson_against_real_azure(make_lesson, real_memory) -> None:
    store = Mem0LessonStore(memory=real_memory)
    lesson = make_lesson(
        body="vendors from agency Acme consistently miss reference checks",
        domain="hiring",
    )

    store.add(lesson)

    hits = store.search(
        "reference checks",
        scope=LessonScope(domain="hiring"),
        top_k=5,
    )

    assert any(h.id == lesson.id for h in hits), (
        f"expected lesson {lesson.id} in results; got {[h.id for h in hits]}"
    )
    matched = next(h for h in hits if h.id == lesson.id)
    assert matched.body == lesson.body
    assert matched.scope.domain == "hiring"


def test_search_with_wrong_domain_returns_no_hits(make_lesson, real_memory) -> None:
    store = Mem0LessonStore(memory=real_memory)
    store.add(make_lesson(domain="hiring", body="hiring-only insight"))

    hits = store.search(
        "hiring-only insight",
        scope=LessonScope(domain="vendor_kyc"),
        top_k=5,
    )

    assert hits == []
