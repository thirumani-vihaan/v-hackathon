"""Tests for the assessment-confidence engine (coverage / decisiveness / freshness)."""
import os
import sys
from datetime import datetime, timedelta

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from schema import SensorReading  # noqa: E402
from utils.confidence import assess_confidence  # noqa: E402

_NOW = datetime(2025, 1, 13, 6, 0, 0)


def _mk(ts=_NOW, **kw):
    base = dict(gas_ppm=5, temp_c=30, oxygen_pct=20.9, humidity_pct=50,
                permit_type="general", worker_count=2, zone="Z",
                timestamp=ts.isoformat())
    base.update(kw)
    return SensorReading(**base)


def test_coverage_drops_on_out_of_range_sensor():
    good = assess_confidence(_mk(), now=_NOW)["coverage"]
    faulty = assess_confidence(_mk(oxygen_pct=2.0), now=_NOW)["coverage"]  # <5% implausible
    assert good == 1.0
    assert faulty < 1.0


def test_decisiveness_low_on_threshold_boundary():
    borderline = assess_confidence(
        _mk(gas_ppm=50.0, oxygen_pct=19.5, temp_c=45.0), now=_NOW)["decisiveness"]
    decisive = assess_confidence(
        _mk(gas_ppm=120.0, oxygen_pct=20.9, temp_c=30.0), now=_NOW)["decisiveness"]
    assert borderline < 0.1
    assert decisive > borderline


def test_freshness_decays_with_age():
    fresh = assess_confidence(_mk(ts=_NOW), now=_NOW)["freshness"]
    stale = assess_confidence(_mk(ts=_NOW - timedelta(minutes=90)), now=_NOW)["freshness"]
    assert fresh == 1.0
    assert stale == 0.0


def test_overall_confidence_and_label_bounds():
    c = assess_confidence(_mk(), now=_NOW)
    assert 0.0 <= c["confidence"] <= 1.0
    assert c["label"] in ("high", "medium", "low")
    assert c["label"] == "high"  # clean, fresh, unambiguous


def test_borderline_reading_flagged_low_or_medium():
    c = assess_confidence(
        _mk(gas_ppm=51.0, oxygen_pct=19.4, temp_c=45.5,
            ts=_NOW - timedelta(minutes=90)), now=_NOW)
    # near-threshold signals + stale data => not high confidence
    assert c["label"] in ("low", "medium")
    assert any("borderline" in n or "stale" in n for n in c["notes"])
