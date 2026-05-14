"""PIL-templated receipt PNG generator with controlled mismatch flavours.

Renders a 480x720 receipt PNG per claim. Six mismatch flavours, weighted
80/4/4/4/4/4, are deterministically assigned and stamped back onto each
claim JSON as `receipt_mismatch_flavour` so the Week 2 receipt validator
has gold labels to compare against.

The "missing-receipt" flavour emits a zero-byte file rather than no file,
so the validator can distinguish "no receipt submitted" from "file
missing by accident" — a real-world EMS audit-trail concern.
"""
from __future__ import annotations
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DATA = Path(__file__).parent
CLAIMS = DATA / "claims"
RECEIPTS = DATA / "receipts"

FLAVOURS = ("correct", "wrong-amount", "wrong-date", "wrong-vendor",
            "missing-line-item", "missing-receipt")
# 80/4/4/4/4/4 of 300 — most claims have correct receipts so end-to-end
# accuracy can be measured.
FLAVOUR_WEIGHTS = (240, 12, 12, 12, 12, 12)

WIDTH, HEIGHT = 480, 720
BG = (255, 255, 255)
FG = (10, 10, 10)


def _font(size: int):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        try:
            return ImageFont.truetype("arial.ttf", size)
        except OSError:
            return ImageFont.load_default()


def _render(claim: dict, flavour: str):
    if flavour == "missing-receipt":
        return None
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)
    title = _font(28)
    body = _font(16)

    vendor = claim["vendor"] if flavour != "wrong-vendor" else f"NOT-{claim['vendor']}"
    submitted = datetime.fromisoformat(claim["submitted_at"])
    if flavour == "wrong-date":
        date_str = (submitted - timedelta(days=400)).date().isoformat()
    else:
        date_str = submitted.date().isoformat()
    amount = claim["amount"] * 1.5 if flavour == "wrong-amount" else claim["amount"]

    draw.text((20, 20), vendor, fill=FG, font=title)
    draw.text((20, 70), f"Date: {date_str}", fill=FG, font=body)
    draw.text((20, 100), f"Currency: {claim['currency']}", fill=FG, font=body)
    draw.text((20, 130), f"Total: {amount:.2f}", fill=FG, font=body)

    y = 180
    if flavour != "missing-line-item":
        draw.text((20, y), "Line items:", fill=FG, font=body)
        y += 30
        draw.text((40, y), f"- {claim['category']} x {claim.get('attendees', 1)}: {amount:.2f}",
                  fill=FG, font=body)
    return img


def run(seed: int = 20260427) -> None:
    rng = random.Random(seed)
    RECEIPTS.mkdir(parents=True, exist_ok=True)

    claim_files = sorted(CLAIMS.glob("CLM-*.json"))
    flavour_pool = []
    for flavour, weight in zip(FLAVOURS, FLAVOUR_WEIGHTS):
        flavour_pool.extend([flavour] * weight)
    rng.shuffle(flavour_pool)
    while len(flavour_pool) < len(claim_files):
        flavour_pool.append("correct")
    flavour_pool = flavour_pool[: len(claim_files)]

    for path, flavour in zip(claim_files, flavour_pool):
        claim = json.loads(path.read_text(encoding="utf-8"))
        claim["receipt_mismatch_flavour"] = flavour
        path.write_text(
            json.dumps(claim, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        out = RECEIPTS / claim["receipt_filename"]
        img = _render(claim, flavour)
        if img is None:
            out.write_bytes(b"")
        else:
            img.save(out, format="PNG", optimize=True)


if __name__ == "__main__":
    run()
    print(f"Wrote {len(list(RECEIPTS.glob('CLM-*.png')))} receipts")
