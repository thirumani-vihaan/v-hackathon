"""Tests for the counterfactual intervention engine: it must reuse the compound
scoring, rank risk-reducing actions correctly, and escalate when no single control
clears a critical state. Deterministic and offline.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from schema import SensorReading  # noqa: E402
from utils.interventions import rank_interventions  # noqa: E402


def _mk(**kw):
    base = dict(gas_ppm=5, temp_c=30, oxygen_pct=20.9, humidity_pct=50,
                permit_type="general", worker_count=2, zone="Zone-B-Process",
                timestamp="2025-01-13T06:00:00")
    base.update(kw)
    return SensorReading(**base)


def test_permit_revocation_is_offered_and_reduces_risk():
    r = _mk(gas_ppm=60, permit_type="hot_work")
    out = rank_interventions(r, ["hot_work"])
    assert out["risk_before"] == 80  # gas>50 (+30) + gas>50&hot_work (+50)
    actions = {c["action"]: c for c in out["interventions"]}
    assert "Revoke hot work permit" in actions
    # revoking hot work removes the +50 compound term -> 30
    assert actions["Revoke hot work permit"]["risk_after"] == 30
    assert actions["Revoke hot work permit"]["risk_reduction"] == 50


def test_ventilation_offered_and_recommended_when_gas_driven():
    r = _mk(gas_ppm=60, permit_type="hot_work")
    out = rank_interventions(r, ["hot_work"])
    # ventilation dilutes gas below every threshold -> biggest reduction -> recommended
    assert out["recommended"] is not None
    assert "ventilation" in out["recommended"]["action"].lower() \
        or "purge" in out["recommended"]["action"].lower()
    assert out["recommended"]["risk_reduction"] >= 50


def test_interventions_ranked_by_reduction_desc():
    r = _mk(gas_ppm=90, oxygen_pct=18.4, permit_type="hot_work", zone="Zone-C-Confined")
    out = rank_interventions(r, ["hot_work", "maintenance"])
    reductions = [c["risk_reduction"] for c in out["interventions"]]
    assert reductions == sorted(reductions, reverse=True)


def test_no_recommendation_when_already_safe():
    r = _mk(gas_ppm=5, oxygen_pct=20.9)
    out = rank_interventions(r, [])
    assert out["risk_before"] == 0
    assert out["recommended"] is None


def test_vizag_critical_recommends_effective_control():
    from utils.sensor_simulator import vizag_critical_reading
    out = rank_interventions(vizag_critical_reading(), ["hot_work"])
    assert out["risk_before"] == 100
    # the recommended control must actually reduce risk
    assert out["recommended"] is not None
    assert out["recommended"]["risk_after"] < out["risk_before"]
