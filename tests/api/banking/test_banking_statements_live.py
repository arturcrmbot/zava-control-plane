"""Live golden set: Laya reading what customers say when they call.

Skipped unless Laya answers ``$LAYA_URL/health``. The reading is advisory (the
record decides vulnerability and the rules decide what is permitted), so this
pins how good it is, including its known confident errors:

- a crypto investment with a release fee reads as an advance fee;
- a police impersonation reads as "not a scam";
- "money worries" is raised on two statements that don't mention any.

    LAYA_URL=http://127.0.0.1:8766 ZAVA_VERTICAL=banking \\
        .venv/bin/python -m pytest tests/api/banking/test_banking_statements_live.py -q
"""
from __future__ import annotations

import asyncio
import os
import time
import urllib.request

import pytest

from api.server.services.judgement.laya_client import LayaClient
from verticals.banking.worlds.statements import read_statement

LAYA_URL = os.environ.get("LAYA_URL", "http://127.0.0.1:8765").rstrip("/")


def _laya_up() -> bool:
    try:
        with urllib.request.urlopen(f"{LAYA_URL.removesuffix('/v1/systemone')}/health", timeout=1) as response:
            return response.status == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _laya_up(), reason=f"Laya is not running at {LAYA_URL}")

# (what the customer says, the kind of case, the circumstances really mentioned)
STATEMENTS = [
    ("Someone rang saying they were from Zava Bank's fraud team. They said my account was compromised and I had "
     "to move my savings to a safe account. I sent 18,400 pounds and now the number doesn't work.",
     "bank_impersonation", False),
    ("I met Daniel on a dating site eight months ago. He needed money for a hospital bill abroad and promised to pay "
     "me back. Since my husband died last year he was the only person I talked to. I have sent him 6,750 pounds.",
     "romance", True),
    ("A broker on social media showed me a crypto platform paying 3 percent a week. I moved 92,000 pounds from my "
     "business account and now they want a release fee before I can withdraw.", "investment", False),
    ("I paid 950 pounds for a car I found on a marketplace. The seller asked for a bank transfer instead of using "
     "the app and never delivered it.", "purchase", False),
    ("Our builder emailed to say their bank details had changed, so we paid the 23,500 pound stage payment to the "
     "new account. The real builder never got it.", "invoice", False),
    ("I'm behind on my rent and was desperate. A lender approved me online but I had to pay a 600 pound insurance "
     "fee first. After I paid, the company vanished.", "advance_fee", True),
    ("I paid a kitchen fitter 4,200 pounds. He did fit the kitchen but the work is poor and he won't come back to "
     "fix it.", "not_scam", False),
    ("I moved 3,000 pounds to my own savings account at another bank and I want it reversed.", "not_scam", False),
    ("A man said he was a police officer investigating my bank and told me not to tell anyone. My daughter says I "
     "get confused since my diagnosis. I sent 12,000 pounds.", "authority_impersonation", True),
    ("I bought two festival tickets from a man on a fan forum for 380 pounds. The tickets never arrived and he "
     "blocked me.", "purchase", False),
    ("I'm just out of hospital after a stroke and wanted to grow my pension. An adviser on the phone put 40,000 "
     "pounds into a bond that doesn't exist.", "investment", True),
    ("I got a text from the tax office saying I owed a penalty and would be arrested. I paid 2,300 pounds through "
     "the link.", "authority_impersonation", False),
]


def _read_all() -> list[tuple]:
    client = LayaClient(LAYA_URL, timeout_s=5.0)

    async def run() -> list[tuple]:
        rows = []
        for text, kind, has_cue in STATEMENTS:
            started = time.perf_counter()
            reading = await read_statement(text, client=client)
            rows.append((reading, kind, has_cue, (time.perf_counter() - started) * 1000))
        return rows

    return asyncio.run(run())


@pytest.fixture(scope="module")
def readings() -> list[tuple]:
    return _read_all()


def test_laya_reads_the_kind_of_case_well_enough_to_advise(readings) -> None:
    assert all(reading.read_by == "laya" for reading, *_ in readings)
    right = sum(reading.scam_type == kind for reading, kind, *_ in readings)
    assert right >= 8, f"{right}/12 scam types right (measured 9)"
    # The plain cases are never missed.
    for index in (0, 1, 9):
        assert readings[index][0].scam_type == readings[index][1]


def test_circumstances_are_caught_and_false_alarms_stay_mild(readings) -> None:
    caught = sum(bool(reading.cues) for reading, _kind, has_cue, _ms in readings if has_cue)
    assert caught >= 3, f"{caught}/4 statements with real circumstances caught (measured 3)"
    for reading, _kind, has_cue, _ms in readings:
        if not has_cue:
            assert set(reading.cues) <= {"money worries"}, reading


def test_a_call_is_read_in_well_under_a_second(readings) -> None:
    latencies = sorted(ms for *_, ms in readings)
    assert latencies[len(latencies) // 2] < 1_000, latencies
