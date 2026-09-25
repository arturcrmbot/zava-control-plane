"""Deep review: the slow, token-spending second look for unclear judgements.

Bounded by an hourly budget (``JUDGEMENT_LLM_BUDGET_PER_HOUR``, default 6) and
by one session at a time. It runs through the provider-neutral LLM runtime, so
``LLM_RUNTIME=fake`` keeps tests offline. The reviewer can only approve or
hold the recommendation it is shown: it never changes the option or the value.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable

from api.server.services.judgement.evidence import DeepReviewRecord
from api.server.services.judgement.profiles import GateFacts

DEFAULT_BUDGET_PER_HOUR = 6
DEFAULT_MODEL = "gpt-4.1"
DEFAULT_TIMEOUT_S = 90.0
# A review that cannot have this long before the gate closes is not started.
MIN_REVIEW_S = 30.0
_WINDOW_S = 3600.0


class NoTimeToReview(Exception):
    """A deep review could not start in time to finish before the gate closes."""


class Budget:
    """At most ``limit`` deep reviews in any rolling hour."""

    def __init__(self, limit: int, *, window_s: float = _WINDOW_S,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.limit = max(0, int(limit))
        self._window_s = window_s
        self._clock = clock
        self._stamps: deque[float] = deque()

    def _expire(self) -> None:
        cutoff = self._clock() - self._window_s
        while self._stamps and self._stamps[0] <= cutoff:
            self._stamps.popleft()

    def remaining(self) -> int:
        self._expire()
        return max(0, self.limit - len(self._stamps))

    def try_consume(self) -> bool:
        if self.remaining() <= 0:
            return False
        self._stamps.append(self._clock())
        return True


@dataclass(frozen=True)
class ReviewRequest:
    persona_role: str
    persona_label: str
    instructions: str
    character: str
    facts: GateFacts
    concerns: list[str] = field(default_factory=list)
    unclear: list[str] = field(default_factory=list)
    # Who a hold goes to; None when this persona has the last word.
    next_role_label: str | None = None
    # True once the agent has already re-assessed the case after a send-back.
    final: bool = False


def _bullets(items: list[str] | tuple[str, ...]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- none"


def build_prompt(request: ReviewRequest) -> str:
    reasoning = request.facts.texts.get("agent_reasoning") or "(the agent gave no reasoning)"
    parts = [
        f"You are the {request.persona_label} at Zava Bank, deciding a gate in a synthetic bank "
        "simulation. Nothing here is a real customer or a real institution.",
        f"Your character: {request.character}",
        f"The case: {request.facts.case}",
        f"The agent recommends: {request.facts.recommendation}",
        f"The agent's reasoning: {reasoning}",
        "A fast first reading raised these concerns:\n" + _bullets(request.concerns),
        "Points the fast reading could not settle:\n" + _bullets(request.unclear),
    ]
    if request.facts.prior_concerns:
        parts.append("An earlier reviewer held this case because:\n" + _bullets(request.facts.prior_concerns))
    if request.next_role_label:
        consequence = f"If you hold it, the case goes to the {request.next_role_label}."
    elif request.final:
        consequence = (
            "Nobody above you can take this case and the agent has already re-assessed it once: if you "
            "hold it, the recommendation is declined and will not be carried out."
        )
    else:
        consequence = (
            "Nobody above you can take this case: if you hold it, it goes back to the agent with your "
            "reasons to be re-assessed once."
        )
    parts.append(
        "Governance has already confirmed the value is within your delegated authority, and the "
        "rules have already admitted this option. You cannot change the option or the amount. "
        f"Decide whether to approve it now or hold it. {consequence}"
    )
    parts.append(
        'Return one JSON object only, no markdown: {"decision": "approve" or "hold", '
        '"rationale": "two or three plain sentences explaining why"}'
    )
    return "\n\n".join(parts)


def parse_verdict(text: str) -> tuple[str, str]:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("the reviewer returned no JSON object")
    data = json.loads(text[start:end + 1])
    if not isinstance(data, dict):
        raise ValueError("the reviewer's JSON is not an object")
    decision = str(data.get("decision") or "").strip().lower()
    if decision not in ("approve", "hold"):
        raise ValueError(f"the reviewer's decision {data.get('decision')!r} is not approve or hold")
    rationale = data.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        raise ValueError("the reviewer gave no rationale")
    return decision, rationale.strip()


def _default_runtime() -> Any:
    from api.functions.graphs.executors.agents.runtime import _get_runtime

    return _get_runtime()


class DeepReviewer:
    def __init__(
        self,
        *,
        budget: Budget | None = None,
        runtime_factory: Callable[[], Any] | None = None,
        model: str | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        self.budget = budget if budget is not None else Budget(
            int(os.environ.get("JUDGEMENT_LLM_BUDGET_PER_HOUR", DEFAULT_BUDGET_PER_HOUR))
        )
        self._runtime_factory = runtime_factory or _default_runtime
        self.model = model or os.environ.get("JUDGEMENT_LLM_MODEL", DEFAULT_MODEL)
        self._timeout_s = timeout_s
        self._lock = asyncio.Lock()

    def available(self) -> bool:
        return self.budget.remaining() > 0

    async def review(self, request: ReviewRequest, *, deadline: float | None = None) -> DeepReviewRecord | None:
        """Ask the LLM. ``None`` means the budget was spent and nothing was asked.

        Reviews run one at a time. ``deadline`` (``time.monotonic()``) is when
        the gate's answer is due: a review waits in the queue only while it
        could still finish in time, raising :class:`NoTimeToReview` otherwise,
        and takes its budget slot only once it can start.
        """
        if not self.available():
            return None
        wait_s = None if deadline is None else deadline - time.monotonic() - MIN_REVIEW_S
        if wait_s is not None and wait_s <= 0:
            raise NoTimeToReview()
        try:
            await asyncio.wait_for(self._lock.acquire(), timeout=wait_s)
        except asyncio.TimeoutError:
            raise NoTimeToReview() from None
        try:
            if not self.budget.try_consume():
                return None
            session_s, limit_s = self._timeout_s, self._timeout_s + 5.0
            if deadline is not None:
                limit_s = max(0.0, min(limit_s, deadline - time.monotonic()))
                session_s = min(session_s, limit_s)
            started = time.perf_counter()
            try:
                runtime = self._runtime_factory()
                result = await asyncio.wait_for(
                    runtime.run_session(
                        prompt=build_prompt(request),
                        system_message=request.instructions or None,
                        tools=[],
                        model=self.model,
                        timeout_s=session_s,
                    ),
                    timeout=limit_s,
                )
                decision, rationale = parse_verdict(getattr(result, "text", "") or "")
            except Exception as ex:  # a failed review falls back to the rules
                return DeepReviewRecord(None, "", (time.perf_counter() - started) * 1000,
                                        error=f"{type(ex).__name__}: {ex}", model=self.model)
            return DeepReviewRecord(decision, rationale, (time.perf_counter() - started) * 1000, model=self.model)
        finally:
            self._lock.release()


_REVIEWER: DeepReviewer | None = None


def get_reviewer() -> DeepReviewer:
    global _REVIEWER
    if _REVIEWER is None:
        _REVIEWER = DeepReviewer()
    return _REVIEWER


def reset_reviewer() -> None:
    global _REVIEWER
    _REVIEWER = None
