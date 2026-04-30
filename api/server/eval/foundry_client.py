"""Foundry SDK config singleton.

Reads required env vars; lazy-builds DefaultAzureCredential and the
AzureOpenAIModelConfiguration the SDK evaluators expect. Importing this
module has no side effects beyond reading os.environ — no Azure calls,
no credential probes.
"""
from __future__ import annotations
import os
from functools import lru_cache
from typing import Any


_REQUIRED_ENV = (
    "AZURE_FOUNDRY_PROJECT_ENDPOINT",
    "AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT",
)


def is_configured() -> bool:
    """Return True iff every required env var is set to a non-empty value."""
    return all(os.environ.get(k) for k in _REQUIRED_ENV)


def _require_configured() -> None:
    if not is_configured():
        missing = [k for k in _REQUIRED_ENV if not os.environ.get(k)]
        raise RuntimeError(
            f"Foundry eval is not configured; missing env: {', '.join(missing)}"
        )


@lru_cache(maxsize=1)
def _credential():
    from azure.identity import DefaultAzureCredential
    return DefaultAzureCredential()


def get_project_config() -> dict[str, Any]:
    """Return the dict shape `evaluate(azure_ai_project=...)` expects."""
    _require_configured()
    return {
        "endpoint": os.environ["AZURE_FOUNDRY_PROJECT_ENDPOINT"],
    }


def get_model_config() -> dict[str, Any]:
    """Return the AzureOpenAIModelConfiguration dict for evaluators that
    take a `model_config=` kwarg (Groundedness, Relevance, Coherence, etc.).
    """
    _require_configured()
    return {
        "azure_endpoint": os.environ["AZURE_FOUNDRY_PROJECT_ENDPOINT"],
        "azure_deployment": os.environ["AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT"],
    }
