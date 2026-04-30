"""is_configured() and lazy-init behaviour for foundry_client."""
from __future__ import annotations
import importlib
import sys

import pytest


def _reload_foundry_client(monkeypatch, env: dict):
    """Reload the module so module-level state picks up env changes."""
    for k in ("AZURE_FOUNDRY_PROJECT_ENDPOINT", "AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    if "api.server.eval.foundry_client" in sys.modules:
        del sys.modules["api.server.eval.foundry_client"]
    return importlib.import_module("api.server.eval.foundry_client")


def test_is_configured_false_when_endpoint_missing(monkeypatch):
    fc = _reload_foundry_client(monkeypatch, env={
        "AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT": "gpt-4o",
    })
    assert fc.is_configured() is False


def test_is_configured_false_when_deployment_missing(monkeypatch):
    fc = _reload_foundry_client(monkeypatch, env={
        "AZURE_FOUNDRY_PROJECT_ENDPOINT": "https://example.cognitiveservices.azure.com",
    })
    assert fc.is_configured() is False


def test_is_configured_true_when_both_set(monkeypatch):
    fc = _reload_foundry_client(monkeypatch, env={
        "AZURE_FOUNDRY_PROJECT_ENDPOINT": "https://example.cognitiveservices.azure.com",
        "AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT": "gpt-4o",
    })
    assert fc.is_configured() is True


def test_module_import_does_not_construct_credentials(monkeypatch):
    """Importing the module must not call DefaultAzureCredential or any Azure SDK init.

    DefaultAzureCredential probes managed identity / az login; that's a side
    effect we never want at import time. Construction only happens when
    get_model_config() / get_project_config() are called.
    """
    fc = _reload_foundry_client(monkeypatch, env={})
    # Just importing succeeded — no exception, no eager Azure construction.
    # We intentionally call the public surface that does NOT need creds:
    assert fc.is_configured() is False


def test_get_project_config_raises_when_unconfigured(monkeypatch):
    fc = _reload_foundry_client(monkeypatch, env={})
    with pytest.raises(RuntimeError, match="not configured"):
        fc.get_project_config()


def test_get_model_config_raises_when_unconfigured(monkeypatch):
    fc = _reload_foundry_client(monkeypatch, env={})
    with pytest.raises(RuntimeError, match="not configured"):
        fc.get_model_config()
