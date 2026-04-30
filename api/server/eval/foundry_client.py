"""Foundry SDK config singleton.

Two distinct concepts that must NOT share an env var:

1. `AZURE_OPENAI_ENDPOINT` + `AZURE_OPENAI_DEPLOYMENT` + `AZURE_OPENAI_API_VERSION`
   — the Azure OpenAI base endpoint that LLM-judge evaluators call. Used as
   `model_config={"azure_endpoint": ..., "azure_deployment": ..., "api_version": ...}`.

2. `AZURE_FOUNDRY_PROJECT_ENDPOINT` — the Foundry project URI used by
   `evaluate(azure_ai_project=...)` and by safety evaluators. The SDK's
   `is_onedp_project()` requires this be a bare string, not a dict.

Importing this module has no side effects beyond reading os.environ.
"""
from __future__ import annotations
import os
from functools import lru_cache


_REQUIRED_FOR_LLM_JUDGE = (
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_DEPLOYMENT",
)
_REQUIRED_FOR_PROJECT = (
    "AZURE_FOUNDRY_PROJECT_ENDPOINT",
)
_DEFAULT_API_VERSION = "2024-10-21"


def is_configured() -> bool:
    """Return True iff the LLM-judge and project env vars are all set.

    Both are required for the eval pipeline. We treat partial config as
    "not configured" so callers don't have to worry about which subset.
    """
    return (
        all(os.environ.get(k) for k in _REQUIRED_FOR_LLM_JUDGE)
        and all(os.environ.get(k) for k in _REQUIRED_FOR_PROJECT)
    )


def _require_configured() -> None:
    if not is_configured():
        missing = [k for k in (_REQUIRED_FOR_LLM_JUDGE + _REQUIRED_FOR_PROJECT)
                   if not os.environ.get(k)]
        raise RuntimeError(
            f"Foundry eval is not configured; missing env: {', '.join(missing)}"
        )


@lru_cache(maxsize=1)
def _credential():
    from azure.identity import DefaultAzureCredential
    return DefaultAzureCredential()


def get_project_config() -> str:
    """Return the project URI string for `evaluate(azure_ai_project=...)`."""
    _require_configured()
    return os.environ["AZURE_FOUNDRY_PROJECT_ENDPOINT"]


def get_model_config() -> dict:
    """Return the AzureOpenAIModelConfiguration dict for LLM-judge evaluators.

    Shape per Azure AI Evaluation SDK docs:
    `{azure_endpoint, azure_deployment, api_version}`.
    Auth uses DefaultAzureCredential — the SDK picks up the credential from
    the environment when no `api_key` is set.
    """
    _require_configured()
    return {
        "azure_endpoint": os.environ["AZURE_OPENAI_ENDPOINT"],
        "azure_deployment": os.environ["AZURE_OPENAI_DEPLOYMENT"],
        "api_version": os.environ.get("AZURE_OPENAI_API_VERSION", _DEFAULT_API_VERSION),
    }
