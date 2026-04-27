"""Receipt PNG generator tests."""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path

import pytest

from data.synthetic import generate, receipt_generator

DATA = Path(generate.__file__).parent
CLAIMS = DATA / "claims"
RECEIPTS = DATA / "receipts"


@pytest.fixture(autouse=True)
def _ensure_claims():
    if not CLAIMS.exists() or len(list(CLAIMS.glob("CLM-*.json"))) != 300:
        generate.run(seed=20260427, count=300)
    for p in RECEIPTS.glob("CLM-*.png"):
        p.unlink()


def test_generates_receipt_for_every_claim():
    receipt_generator.run(seed=20260427)
    pngs = sorted(RECEIPTS.glob("CLM-*.png"))
    assert len(pngs) == 300


def test_pngs_are_valid_image_files():
    receipt_generator.run(seed=20260427)
    from PIL import Image
    # Find a non-zero-byte sample (zero-byte files are missing-receipt markers).
    sample = next(p for p in RECEIPTS.glob("CLM-*.png") if p.stat().st_size > 0)
    with Image.open(sample) as img:
        assert img.format == "PNG"
        assert img.size[0] >= 200 and img.size[1] >= 300


def test_six_mismatch_flavours_present():
    receipt_generator.run(seed=20260427)
    flavours = Counter()
    for f in CLAIMS.glob("CLM-*.json"):
        c = json.loads(f.read_text(encoding="utf-8"))
        flavours[c["receipt_mismatch_flavour"]] += 1
    expected = {"correct", "wrong-amount", "wrong-date", "wrong-vendor", "missing-line-item", "missing-receipt"}
    assert expected <= set(flavours), flavours
    assert flavours["correct"] >= 200, flavours


def test_missing_receipt_flavour_emits_zero_byte_marker():
    receipt_generator.run(seed=20260427)
    missing = [json.loads(f.read_text()) for f in CLAIMS.glob("CLM-*.json")
               if json.loads(f.read_text())["receipt_mismatch_flavour"] == "missing-receipt"]
    assert missing, "no missing-receipt claims generated"
    sample = missing[0]
    receipt_path = RECEIPTS / sample["receipt_filename"]
    assert receipt_path.exists()
    assert receipt_path.stat().st_size == 0
