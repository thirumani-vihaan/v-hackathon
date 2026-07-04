"""Tests for the graduated continuous risk model — smoothness (no cliff), responsiveness
to every factor, and consistent interventions."""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from schema import SensorReading  # noqa: E402
from utils.risk_model import graduated_risk, rank_interventions  # noqa: E402


def _mk(**kw):
    base = dict(gas_ppm=48, temp_c=30, oxygen_pct=20.9, humidity_pct=50,
                permit_type="general", worker_count=2, zone="Zone-A-Tank-Farm",
                timestamp="2025-01-13T06:00:00")
    base.update(kw)
    return SensorReading(**base)


def test_no_cliff_at_gas_50():
    s50 = graduated_risk(_mk(gas_ppm=50))["score"]
    s51 = graduated_risk(_mk(gas_ppm=51))["score"]
    assert abs(s50 - s51) <= 3  # smooth, not a 0->100 jump


def test_monotonic_in_gas():
    scores = [graduated_risk(_mk(gas_ppm=g))["score"] for g in (10, 40, 70, 100, 130)]
    assert scores == sorted(scores)


def test_every_factor_moves_the_score_below_gas_threshold():
    base = graduated_risk(_mk(gas_ppm=48))["score"]
    hotter = graduated_risk(_mk(gas_ppm=48, temp_c=55))["score"]
    hotwork = graduated_risk(_mk(gas_ppm=48, permit_type="hot_work"), ["hot_work"])["score"]
    confined = graduated_risk(_mk(gas_ppm=48, zone="Zone-C-Confined"))["score"]
    lowo2 = graduated_risk(_mk(gas_ppm=48, oxygen_pct=18.5))["score"]
    assert hotter > base and hotwork > base and confined > base and lowo2 > base


def test_extremes_align():
    assert graduated_risk(_mk(gas_ppm=8, oxygen_pct=20.9))["score"] < 20
    vz = graduated_risk(_mk(gas_ppm=120, oxygen_pct=18.4, permit_type="hot_work",
                            zone="Zone-C-Confined"), ["hot_work"])
    assert vz["score"] >= 90 and vz["band"] == "CRITICAL"
    assert vz["contributions"] and vz["contributions"][0]["points"] > 0


def test_interventions_reduce_and_are_consistent():
    r = _mk(gas_ppm=90, oxygen_pct=18.6, permit_type="hot_work", zone="Zone-C-Confined")
    out = rank_interventions(r, ["hot_work"])
    assert out["risk_before"] == graduated_risk(r, ["hot_work"])["score"]
    assert out["recommended"] is not None
    assert out["recommended"]["risk_after"] < out["risk_before"]
    reductions = [c["risk_reduction"] for c in out["interventions"]]
    assert reductions == sorted(reductions, reverse=True)
