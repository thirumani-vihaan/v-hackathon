"""Tests for the compound-vs-single-sensor benchmark (P0): physics-labeled scenario
generator, single-sensor baseline, predictive forecasting, and the benchmark result
invariants that back our PS1 headline claim. All deterministic and offline.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from utils.scenario_generator import (  # noqa: E402
    build_dataset, generate_scenario, is_incident_condition, IDLH_PPM)
from utils.baseline_detector import detect_step, single_sensor_fires  # noqa: E402
from utils.forecast import minutes_to_threshold, forecast_summary  # noqa: E402
from tools.benchmark import run  # noqa: E402


# ---------------- scenario generator ----------------

def test_dataset_is_deterministic():
    a = build_dataset(seed=7)
    b = build_dataset(seed=7)
    assert [s["id"] for s in a] == [s["id"] for s in b]
    assert [s["incident_step"] for s in a] == [s["incident_step"] for s in b]


def test_incident_scenarios_have_an_incident_step():
    ds = build_dataset(seed=1)
    for s in ds:
        if s["label"] == "incident":
            assert s["incident_step"] is not None
            # ground truth actually holds at that step
            r = s["readings"][s["incident_step"]]
            assert is_incident_condition(r, s["active_permits"])
        else:
            assert s["incident_step"] is None


def test_safe_scenarios_never_cross_ground_truth():
    for kind in ("safe_stable", "safe_transient"):
        for seed in range(5):
            s = generate_scenario(kind, rng=__import__("random").Random(seed))
            assert s["label"] == "safe"
            assert all(not is_incident_condition(r, s["active_permits"])
                       for r in s["readings"])


# ---------------- single-sensor baseline ----------------

def test_single_high_alarm_is_blind_to_conjunctions():
    # The compound (Vizag) scenario stays below every individual high-alarm setpoint.
    import random
    for seed in range(8):
        s = generate_scenario("conjunction_incident", rng=random.Random(seed))
        assert detect_step(s["readings"], "high_alarm") is None


def test_single_low_alarm_is_more_sensitive():
    ds = build_dataset(seed=3)
    fired_low = sum(1 for s in ds if detect_step(s["readings"], "low_alarm") is not None)
    fired_high = sum(1 for s in ds if detect_step(s["readings"], "high_alarm") is not None)
    assert fired_low >= fired_high


def test_single_sensor_fires_on_idlh():
    from utils.sensor_simulator import vizag_critical_reading
    assert single_sensor_fires(vizag_critical_reading(), "high_alarm")


# ---------------- forecast ----------------

def test_forecast_predicts_rising_crossing():
    gas = [10, 18, 27, 34, 41, 49]
    m = minutes_to_threshold(gas, 60, seconds_per_step=60, rising=True)
    assert m is not None and m > 0


def test_forecast_none_when_flat():
    assert minutes_to_threshold([20, 20, 20, 20], 60, rising=True) is None


def test_forecast_zero_when_already_past():
    assert minutes_to_threshold([70, 80, 95, 105], 100, rising=True) == 0.0


def test_forecast_oxygen_falling():
    o2 = [20.9, 20.5, 20.0, 19.5, 19.0, 18.5]
    m = minutes_to_threshold(o2, 16.0, rising=False)
    assert m is not None and m > 0
    summ = forecast_summary([10, 20, 30, 40, 50, 58], o2)
    assert summ["minutes_to_gas_idlh"] is not None


# ---------------- benchmark invariants (the PS1 headline) ----------------

def test_compound_predictive_beats_single_sensor_on_false_negatives():
    for seed in (0, 5, 11, 42):
        s = run(seed=seed)
        d = s["detectors"]
        # our shipped detector never misses an incident outright
        assert d["compound_pred"]["false_negative_rate_raw"] == 0.0
        # and is operationally far better than single-sensor high-alarm
        assert (d["compound_pred"]["false_negative_rate_operational"]
                < d["single_high"]["false_negative_rate_operational"])
        # while keeping false alarms controlled (unlike the sensitive single-sensor)
        assert d["compound_pred"]["false_alarm_rate"] <= 0.2
        assert d["single_low"]["false_alarm_rate"] > d["compound_pred"]["false_alarm_rate"]


def test_benchmark_headline_present_and_positive():
    s = run(seed=42)
    h = s["headline"]
    assert h["false_negative_reduction_pct"] > 0
    assert h["compound_median_lead_minutes"] is not None


def test_per_scenario_kind_breakdown():
    s = run(seed=42)
    bk = s["by_scenario_kind"]
    # single-sensor high-alarm is totally blind to the conjunction case
    assert bk["conjunction_incident"]["single_high"] == 1.0
    # our shipped engine misses no incident kind operationally
    for kind, row in bk.items():
        if row["type"] == "incident":
            assert row["compound_pred"] == 0.0
        else:
            # sensitive single-sensor false-alarms on safe kinds; ours does not
            assert row["single_low"] > row["compound_pred"]


# ---------------- P1a: maintenance + shift-changeover signals ----------------

def _mk(**kw):
    from schema import SensorReading
    base = dict(gas_ppm=5, temp_c=30, oxygen_pct=20.9, humidity_pct=50,
                permit_type="general", worker_count=2, zone="Zone-A-Tank-Farm",
                timestamp="2025-01-13T05:50:00")
    base.update(kw)
    return SensorReading(**base)


def test_maintenance_escalation_only_in_confined_space():
    from schema import SensorInput
    from agents.safety_agent import SafetyAgent
    ag = SafetyAgent()
    # maintenance + gas>50 in a confined space escalates above the base gas-only score
    confined = ag.assess(SensorInput(
        reading=_mk(gas_ppm=60, zone="Zone-C-Confined"),
        active_permits=["maintenance"])).risk_score
    # same reading in an open zone gets ONLY the base gas>50 (+30), no escalation
    open_zone = ag.assess(SensorInput(
        reading=_mk(gas_ppm=60, zone="Zone-A-Tank-Farm"),
        active_permits=["maintenance"])).risk_score
    assert open_zone == 30
    assert confined == 55  # 30 (gas>50) + 25 (maintenance-in-confined)


def test_shift_changeover_escalation_requires_gas():
    from schema import SensorInput
    from agents.safety_agent import SafetyAgent
    ag = SafetyAgent()
    # no escalation when gas is low, even during a changeover
    low = ag.assess(SensorInput(reading=_mk(gas_ppm=10),
                                active_permits=["shift_changeover"])).risk_score
    assert low == 0
    # escalates when gas is elevated during the handover
    hi = ag.assess(SensorInput(reading=_mk(gas_ppm=60),
                               active_permits=["shift_changeover"])).risk_score
    assert hi == 45  # 30 (gas>50) + 15 (shift-changeover gap)


def test_shift_changeover_detection_window():
    from utils.safety_calendar import is_shift_changeover
    assert is_shift_changeover("2025-01-13T05:50:00") is True    # near 06:00
    assert is_shift_changeover("2025-01-13T22:10:00") is True    # near 22:00
    assert is_shift_changeover("2025-01-13T10:00:00") is False   # mid-shift
    assert is_shift_changeover("not-a-date") is False


def test_maintenance_scenario_detected_early():
    import random
    from tools.benchmark import single_detect, compound_pred_detect
    for seed in range(6):
        s = generate_scenario("maintenance_shift_incident", rng=random.Random(seed))
        assert s["label"] == "incident"
        k = s["incident_step"]
        cp = compound_pred_detect(s)
        assert cp is not None and cp < k          # our engine detects before onset
        sh = single_detect(s["readings"], "high_alarm")
        # single high-alarm, if it fires at all, does so no earlier than our engine
        assert sh is None or sh >= cp
