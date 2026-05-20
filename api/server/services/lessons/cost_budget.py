"""In-process daily LLM cost budget for dream-pass.

Per-domain spend counter, reset implicitly per UTC day. The goal is a
hard stop that prevents runaway dream-pass cost from a bad proposer
loop or a flood of unconsumed working notes — NOT a perfect ledger.
Process restart resets the counter; this is acceptable because the
budget exists to stop hot loops within a single boot, not to enforce a
SaaS quota.

Token → USD uses approximate Azure OpenAI gpt-4o list prices:
  - input  $2.50 / 1M tokens
  - output $10.00 / 1M tokens
Review annually; update _GPT4O_INPUT_USD_PER_TOKEN if pricing changes.
"""
from __future__ import annotations

import threading
from collections import defaultdict
from datetime import date, datetime, timezone

_GPT4O_INPUT_USD_PER_TOKEN = 2.50 / 1_000_000
_GPT4O_OUTPUT_USD_PER_TOKEN = 10.00 / 1_000_000


def estimate_usd(*, input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens * _GPT4O_INPUT_USD_PER_TOKEN
        + output_tokens * _GPT4O_OUTPUT_USD_PER_TOKEN
    )


class CostBudget:
    """Thread-safe per-(domain, day) spend counter."""

    def __init__(self, *, daily_budget_usd: float) -> None:
        self._budget = float(daily_budget_usd)
        self._spend: dict[tuple[str, date], float] = defaultdict(float)
        self._lock = threading.Lock()

    @staticmethod
    def _today() -> date:
        return datetime.now(timezone.utc).date()

    def record(
        self,
        *,
        domain: str,
        input_tokens: int,
        output_tokens: int,
        on_date: date | None = None,
    ) -> None:
        d = on_date or self._today()
        delta = estimate_usd(input_tokens=input_tokens, output_tokens=output_tokens)
        with self._lock:
            self._spend[(domain, d)] += delta

    def spent_today(self, *, domain: str, on_date: date | None = None) -> float:
        d = on_date or self._today()
        with self._lock:
            return self._spend.get((domain, d), 0.0)

    def is_over_budget(self, domain: str, *, on_date: date | None = None) -> bool:
        return self.spent_today(domain=domain, on_date=on_date) >= self._budget
