"""Tests for ``classifier_cache`` (pitch-i3)."""
from __future__ import annotations

import pytest

from api.server.services import classifier_cache


@pytest.fixture(autouse=True)
def _reset_cache():
    classifier_cache._reset_for_tests()
    yield
    classifier_cache._reset_for_tests()


def test_signature_stable_for_equivalent_payloads():
    a = {
        "kind": "exception_classifier",
        "unmatched_item": {
            "vendor_id": "ORG-V1",
            "amount": 250.00,
            "scenario": "amount-mismatch",
        },
    }
    b = {
        "kind": "exception_classifier",
        "unmatched_item": {
            "vendor_id": "ORG-V1",
            "amount": 275.00,  # same band (<1000)
            "scenario": "amount-mismatch",
        },
    }
    assert classifier_cache.signature_for(a) == classifier_cache.signature_for(b)


def test_signature_differs_when_amount_band_differs():
    a = {"unmatched_item": {"vendor_id": "V", "amount": 50, "scenario": "x"}}
    b = {"unmatched_item": {"vendor_id": "V", "amount": 5000, "scenario": "x"}}
    assert classifier_cache.signature_for(a) != classifier_cache.signature_for(b)


def test_signature_differs_when_vendor_differs():
    a = {"unmatched_item": {"vendor_id": "V1", "amount": 100, "scenario": "x"}}
    b = {"unmatched_item": {"vendor_id": "V2", "amount": 100, "scenario": "x"}}
    assert classifier_cache.signature_for(a) != classifier_cache.signature_for(b)


def test_signature_differs_when_scenario_differs():
    a = {"unmatched_item": {"vendor_id": "V", "amount": 100, "scenario": "fraud-suspect"}}
    b = {"unmatched_item": {"vendor_id": "V", "amount": 100, "scenario": "duplicate-payment"}}
    assert classifier_cache.signature_for(a) != classifier_cache.signature_for(b)


def test_signature_handles_missing_fields():
    sig = classifier_cache.signature_for({"unmatched_item": {}})
    assert isinstance(sig, str) and len(sig) == 16


def test_signature_handles_inner_item_directly():
    inner = {"vendor_id": "V", "amount": 100, "scenario": "x"}
    wrapped = {"unmatched_item": inner}
    assert classifier_cache.signature_for(inner) == classifier_cache.signature_for(wrapped)


def test_lookup_miss_then_remember_then_hit():
    sig = "abc123"
    assert classifier_cache.lookup(sig) is None
    classifier_cache.remember(sig, {"classification": "fraud-suspect", "confidence": 0.91})
    cached = classifier_cache.lookup(sig)
    assert cached == {"classification": "fraud-suspect", "confidence": 0.91}


def test_lookup_returns_defensive_copy():
    sig = "abc123"
    classifier_cache.remember(sig, {"classification": "duplicate-payment"})
    out = classifier_cache.lookup(sig)
    out["classification"] = "MUTATED"
    again = classifier_cache.lookup(sig)
    assert again["classification"] == "duplicate-payment"


def test_remember_stores_defensive_copy():
    sig = "abc123"
    payload = {"classification": "amount-mismatch"}
    classifier_cache.remember(sig, payload)
    payload["classification"] = "MUTATED"
    cached = classifier_cache.lookup(sig)
    assert cached["classification"] == "amount-mismatch"


def test_remember_ignores_non_dict():
    classifier_cache.remember("sig", "not-a-dict")  # type: ignore[arg-type]
    assert classifier_cache.lookup("sig") is None


def test_stats_tracks_hits_and_misses():
    classifier_cache.remember("hit-sig", {"classification": "x"})
    classifier_cache.lookup("miss-sig")
    classifier_cache.lookup("hit-sig")
    classifier_cache.lookup("hit-sig")
    s = classifier_cache.stats()
    assert s["size"] == 1
    assert s["hits"] == 2
    assert s["misses"] == 1
    assert s["hit_rate"] == pytest.approx(2 / 3)


def test_end_to_end_signature_roundtrip():
    payload = {
        "kind": "exception_classifier",
        "unmatched_item": {"vendor_id": "ORG-V1", "amount": 750, "scenario": "amount-mismatch"},
    }
    sig = classifier_cache.signature_for(payload)
    assert classifier_cache.lookup(sig) is None
    classifier_cache.remember(sig, {"classification": "amount-mismatch", "confidence": 0.88})
    again = classifier_cache.signature_for(payload)
    assert classifier_cache.lookup(again) == {
        "classification": "amount-mismatch",
        "confidence": 0.88,
    }
