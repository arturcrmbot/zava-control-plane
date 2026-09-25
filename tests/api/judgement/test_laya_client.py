"""Laya client: answer parsing, lead, failure handling and the circuit breaker."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from api.server.services.judgement.laya_client import (
    LayaClient,
    LayaUnavailable,
    get_client,
    reset_client,
)

CHOICE = {"type": "choice", "choice": "approve", "confidence": 0.6,
          "probabilities": {"approve": 0.8, "hold": 0.2}}
NOUL = {"type": "noul", "noul": 0.1}
SCORE = {"type": "score", "score": 1.4, "confidence": 0.2,
         "probabilities": {"0": 0.05, "1": 0.5, "2": 0.45}}


class _Clock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


def _client(handler, *, url="http://laya.test", clock=None) -> LayaClient:
    return LayaClient(url, transport=httpx.MockTransport(handler), clock=clock or _Clock())


def _ok(answers: dict) -> httpx.Response:
    return httpx.Response(200, json={"answers": answers, "latency_ms": 42.5,
                                     "usage": {"input_tokens": 10, "output_tokens": 0}})


def test_parses_choice_noul_and_score_answers() -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append({"url": str(request.url), "body": json.loads(request.content)})
        return _ok({"gate": CHOICE, "flag": NOUL, "upset": SCORE})

    result = asyncio.run(_client(handler).ask({"text": "x"}, {"gate": {}, "flag": {}, "upset": {}}))

    gate, flag, upset = result.answers["gate"], result.answers["flag"], result.answers["upset"]
    assert (gate.kind, gate.top, gate.lead) == ("choice", "approve", pytest.approx(0.6))
    assert flag.kind == "noul" and flag.top == "no"
    assert flag.probabilities == {"yes": pytest.approx(0.1), "no": pytest.approx(0.9)}
    assert flag.lead == pytest.approx(0.8)
    assert upset.kind == "score" and upset.top == "1" and upset.score == pytest.approx(1.4)
    assert upset.lead == pytest.approx(0.05)
    assert result.latency_ms == pytest.approx(42.5)
    assert seen[0]["url"] == "http://laya.test/v1/systemone"
    assert seen[0]["body"] == {"state": {"text": "x"}, "questions": {"gate": {}, "flag": {}, "upset": {}}}


def test_accepts_a_url_that_already_names_the_endpoint() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return _ok({"flag": NOUL})

    asyncio.run(_client(handler, url="http://laya.test/v1/systemone/").ask("s", {"flag": {}}))
    assert seen == ["http://laya.test/v1/systemone"]


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(422, json={"error": "bad question"}),
        httpx.Response(200, content=b"not json"),
        httpx.Response(200, json={"no_answers": True}),
        httpx.Response(200, json={"answers": {"flag": {"type": "noul"}}}),
    ],
)
def test_bad_responses_raise_unavailable(response: httpx.Response) -> None:
    client = _client(lambda request: response)
    with pytest.raises(LayaUnavailable):
        asyncio.run(client.ask("s", {"flag": {}}))


def test_a_missing_answer_raises_unavailable() -> None:
    client = _client(lambda request: _ok({"other": NOUL}))
    with pytest.raises(LayaUnavailable, match="flag"):
        asyncio.run(client.ask("s", {"flag": {}}))


def test_transport_errors_raise_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(LayaUnavailable):
        asyncio.run(_client(handler).ask("s", {"flag": {}}))


def test_three_failures_open_the_breaker_until_the_cool_down() -> None:
    clock = _Clock()
    calls = {"n": 0, "fail": True}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["fail"]:
            return httpx.Response(500)
        return _ok({"flag": NOUL})

    client = _client(handler, clock=clock)
    for _ in range(3):
        with pytest.raises(LayaUnavailable):
            asyncio.run(client.ask("s", {"flag": {}}))
    assert client.available() is False
    with pytest.raises(LayaUnavailable, match="circuit"):
        asyncio.run(client.ask("s", {"flag": {}}))
    assert calls["n"] == 3  # no request while the breaker is open

    clock.now += 31
    calls["fail"] = False
    assert client.available() is True
    asyncio.run(client.ask("s", {"flag": {}}))
    assert client.consecutive_failures == 0


def test_unset_url_disables_the_client(monkeypatch) -> None:
    monkeypatch.delenv("LAYA_URL", raising=False)
    reset_client()
    client = get_client()
    assert client.enabled is False and client.available() is False
    with pytest.raises(LayaUnavailable, match="LAYA_URL"):
        asyncio.run(client.ask("s", {"flag": {}}))


def test_get_client_reads_the_environment_once(monkeypatch) -> None:
    monkeypatch.setenv("LAYA_URL", "http://127.0.0.1:9")
    reset_client()
    try:
        first = get_client()
        assert first.enabled is True
        assert get_client() is first
    finally:
        reset_client()
