"""Receipt PNG generator tests.

Output redirected to tmp_path so the tracked `data/synthetic/{claims,receipts}/`
directories are not mutated by the suite. Claims are regenerated into the same
sandbox so the receipt generator has 300 claim JSONs to read."""
from __future__ import annotations
import json
from collections import Counter

import pytest

from data.synthetic import generate, receipt_generator


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    claims = tmp_path / "claims"
    receipts = tmp_path / "receipts"
    claims.mkdir()
    receipts.mkdir()
    labels = tmp_path / "labels.csv"
    monkeypatch.setattr(generate, "CLAIMS", claims)
    monkeypatch.setattr(generate, "LABELS", labels)
    monkeypatch.setattr(receipt_generator, "CLAIMS", claims)
    monkeypatch.setattr(receipt_generator, "RECEIPTS", receipts)
    generate.run(seed=20260427, count=300)
    return {"claims": claims, "receipts": receipts}


def test_generates_receipt_for_every_claim(sandbox):
    receipt_generator.run(seed=20260427)
    assert len(list(sandbox["receipts"].glob("CLM-*.png"))) == 300


def test_pngs_are_valid_image_files(sandbox):
    receipt_generator.run(seed=20260427)
    from PIL import Image
    sample = next(p for p in sandbox["receipts"].glob("CLM-*.png") if p.stat().st_size > 0)
    with Image.open(sample) as img:
        assert img.format == "PNG"
        assert img.size[0] >= 200 and img.size[1] >= 300


def test_six_mismatch_flavours_present(sandbox):
    receipt_generator.run(seed=20260427)
    flavours = Counter(
        json.loads(f.read_text(encoding="utf-8"))["receipt_mismatch_flavour"]
        for f in sandbox["claims"].glob("CLM-*.json")
    )
    expected = {"correct", "wrong-amount", "wrong-date", "wrong-vendor", "missing-line-item", "missing-receipt"}
    assert expected <= set(flavours), flavours
    assert flavours["correct"] >= 200, flavours


def test_missing_receipt_flavour_emits_zero_byte_marker(sandbox):
    receipt_generator.run(seed=20260427)
    missing = [
        json.loads(f.read_text(encoding="utf-8"))
        for f in sandbox["claims"].glob("CLM-*.json")
        if json.loads(f.read_text(encoding="utf-8"))["receipt_mismatch_flavour"] == "missing-receipt"
    ]
    assert missing, "no missing-receipt claims generated"
    receipt_path = sandbox["receipts"] / missing[0]["receipt_filename"]
    assert receipt_path.exists()
    assert receipt_path.stat().st_size == 0
