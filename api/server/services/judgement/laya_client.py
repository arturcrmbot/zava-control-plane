"""Async client for Laya, the local System One model (``POST /v1/systemone``).

Laya answers typed questions about a short English state. Each answer becomes a
:class:`LayaAnswer` carrying every option's probability and the top option's
lead over the runner-up, which is what callers gate on.

The client never retries inside a decision. After three failures in a row it
stops calling for thirty seconds, so callers fall back at once instead of
waiting on timeouts.
"""
from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass
from typing import Any, Callable

import httpx

ENDPOINT = "/v1/systemone"
DEFAULT_TIMEOUT_S = 2.0
BREAKER_FAILURES = 3
BREAKER_COOLDOWN_S = 30.0


class LayaUnavailable(RuntimeError):
    """Laya could not answer; the caller must fall back."""


@dataclass(frozen=True, slots=True)
class LayaAnswer:
    kind: str
    probabilities: dict[str, float]
    top: str
    lead: float
    score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "kind": self.kind,
            "probabilities": {k: round(v, 4) for k, v in self.probabilities.items()},
            "top": self.top,
            "lead": round(self.lead, 4),
        }
        if self.score is not None:
            out["score"] = round(self.score, 4)
        return out


@dataclass(frozen=True, slots=True)
class LayaResult:
    answers: dict[str, LayaAnswer]
    latency_ms: float
    wall_ms: float


def _endpoint(url: str) -> str:
    base = url.strip().rstrip("/")
    return base if base.endswith(ENDPOINT) else base + ENDPOINT


def _probability(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("probability must be a number")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise ValueError(f"probability out of range: {value!r}")
    return number


def _lead(probabilities: dict[str, float]) -> float:
    ordered = sorted(probabilities.values(), reverse=True)
    return ordered[0] - (ordered[1] if len(ordered) > 1 else 0.0)


def parse_answer(raw: Any) -> LayaAnswer:
    if not isinstance(raw, dict):
        raise ValueError("answer must be an object")
    kind = raw.get("type")
    if kind == "noul" or (kind is None and "noul" in raw):
        p = _probability(raw["noul"])
        return LayaAnswer("noul", {"yes": p, "no": 1.0 - p}, "yes" if p >= 0.5 else "no", abs(2 * p - 1))
    probabilities = raw.get("probabilities")
    if not isinstance(probabilities, dict) or not probabilities:
        raise ValueError("answer has no probabilities")
    probs = {str(option): _probability(p) for option, p in probabilities.items()}
    top = max(probs, key=probs.__getitem__)
    score = None
    if kind == "score" and raw.get("score") is not None:
        score = float(raw["score"])
    return LayaAnswer(str(kind or "choice"), probs, top, _lead(probs), score)


class LayaClient:
    def __init__(
        self,
        url: str | None,
        *,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._url = _endpoint(url) if url and url.strip() else None
        self._timeout_s = timeout_s
        self._transport = transport
        self._clock = clock
        self._open_until = 0.0
        self.consecutive_failures = 0

    @property
    def url(self) -> str | None:
        return self._url

    @property
    def enabled(self) -> bool:
        return self._url is not None

    def available(self) -> bool:
        return self.enabled and self._clock() >= self._open_until

    def _fail(self) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= BREAKER_FAILURES:
            self._open_until = self._clock() + BREAKER_COOLDOWN_S

    async def ask(self, state: Any, questions: dict[str, dict[str, Any]]) -> LayaResult:
        if self._url is None:
            raise LayaUnavailable("LAYA_URL is not set")
        if self._clock() < self._open_until:
            raise LayaUnavailable("Laya circuit is open after repeated failures")
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s, transport=self._transport) as http:
                response = await http.post(self._url, json={"state": state, "questions": questions})
            response.raise_for_status()
            data = response.json()
            raw_answers = data["answers"]
            answers = {question_id: parse_answer(raw_answers[question_id]) for question_id in questions}
        except KeyError as ex:
            self._fail()
            raise LayaUnavailable(f"Laya gave no answer for {ex}") from ex
        except (httpx.HTTPError, ValueError, TypeError) as ex:
            self._fail()
            raise LayaUnavailable(f"Laya call failed: {ex}") from ex
        self.consecutive_failures = 0
        wall_ms = (time.perf_counter() - started) * 1000
        latency = data.get("latency_ms")
        server_ms = float(latency) if isinstance(latency, (int, float)) and not isinstance(latency, bool) else wall_ms
        return LayaResult(answers, round(server_ms, 1), round(wall_ms, 1))


_CLIENT: LayaClient | None = None


def get_client() -> LayaClient:
    global _CLIENT
    if _CLIENT is None:
        timeout = float(os.environ.get("LAYA_TIMEOUT_S", DEFAULT_TIMEOUT_S))
        _CLIENT = LayaClient(os.environ.get("LAYA_URL"), timeout_s=timeout)
    return _CLIENT


def reset_client() -> None:
    global _CLIENT
    _CLIENT = None
