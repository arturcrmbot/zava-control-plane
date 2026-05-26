"""Azure OpenAI implementation of LLMRuntime.

Selected via ``LLM_RUNTIME=aoai`` (or the legacy alias ``azure``).

This is the cloud-deploy path used when the container runs in Azure
Container Apps with a managed identity that has ``Cognitive Services
OpenAI User`` on the AOAI account. It calls the AOAI chat completions
endpoint directly — it does NOT support GHCP-style MCP tool sessions,
skill directories, or attachments. Those kwargs are accepted (for
signature compatibility with :class:`GHCPRuntime`) but ignored.

Required env:
    AZURE_OPENAI_ENDPOINT       e.g. https://my-aoai.cognitiveservices.azure.com/
    AZURE_OPENAI_DEPLOYMENT     chat deployment name (e.g. ``gpt-4``)

Optional env:
    AZURE_OPENAI_API_VERSION    defaults to ``2024-10-21``
    AZURE_CLIENT_ID             when set, the UAMI client id is forwarded
                                to DefaultAzureCredential so the managed
                                identity is picked up unambiguously.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Callable

from api.functions.graphs.executors.agents.runtime import LLMRuntimeResult


_DEFAULT_API_VERSION = "2024-10-21"


def _build_client() -> Any:
    """Construct an ``openai.AzureOpenAI`` client using managed identity."""
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from openai import AzureOpenAI

    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    if not endpoint:
        raise RuntimeError(
            "AZURE_OPENAI_ENDPOINT is required for LLM_RUNTIME=aoai"
        )

    credential = DefaultAzureCredential(
        managed_identity_client_id=os.environ.get("AZURE_CLIENT_ID") or None,
    )
    token_provider = get_bearer_token_provider(
        credential, "https://cognitiveservices.azure.com/.default"
    )
    return AzureOpenAI(
        azure_endpoint=endpoint,
        azure_ad_token_provider=token_provider,
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", _DEFAULT_API_VERSION),
    )


class AOAIRuntime:
    """Minimal Azure OpenAI chat-completions runtime.

    Tools / MCP skills / attachments are not supported by this runtime;
    use :class:`GHCPRuntime` for agentic tool-using sessions. The
    workflow activities that only need a single text reply (most of the
    expense-claim / hiring spine) work fine here.
    """

    def __init__(self) -> None:
        self._client: Any | None = None
        self._deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT") or "gpt-4"

    def _client_lazy(self) -> Any:
        if self._client is None:
            self._client = _build_client()
        return self._client

    async def run_session(
        self,
        *,
        prompt: str,
        system_message: str | None = None,
        skill_directories: list[Path] | None = None,  # noqa: ARG002 - unsupported
        tools: list | None = None,  # noqa: ARG002 - unsupported
        permission_handler: Callable | None = None,  # noqa: ARG002 - unsupported
        attachments: list[dict] | None = None,  # noqa: ARG002 - unsupported
        model: str = "gpt-4.1",  # noqa: ARG002 - deployment name comes from env
        timeout_s: float = 240.0,
        event_subscriber: Callable[[Any], None] | None = None,  # noqa: ARG002
    ) -> LLMRuntimeResult:
        messages: list[dict[str, str]] = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})

        def _call() -> Any:
            client = self._client_lazy()
            return client.chat.completions.create(
                model=self._deployment,
                messages=messages,
                timeout=timeout_s,
            )

        # openai SDK is sync; run in thread so we don't block the worker loop.
        response = await asyncio.to_thread(_call)

        text = ""
        in_tok = out_tok = None
        try:
            text = response.choices[0].message.content or ""
        except (AttributeError, IndexError):
            text = ""
        usage = getattr(response, "usage", None)
        if usage is not None:
            in_tok = getattr(usage, "prompt_tokens", None)
            out_tok = getattr(usage, "completion_tokens", None)

        return LLMRuntimeResult(
            text=text,
            tool_calls=[],
            input_tokens=in_tok,
            output_tokens=out_tok,
            raw_event=None,
        )
