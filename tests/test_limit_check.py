"""Tests for regulatory-limit utilisation (direction-aware measured-vs-limit)."""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from schema import SensorReading  # noqa: E402
from utils.limit_check import limit_utilisation  # noqa: E402


def _mk(**kw):
    base = dict(gas_ppm=5, temp_c=30, oxygen_pct=20.9, humidity_pct=50,
                permit_type="general", worker_count=2, zone="Z",
                timestamp="2025-01-13T06:00:00")
    base.update(kw)
    return SensorReading(**base)


def _by(rows, name):
    return next(r for r in rows if r["parameter"] == name)


def test_upper_bound_exceeded_when_gas_high():
    rows = limit_utilisation(_mk(gas_ppm=100))
    gas = _by(rows, "H\u2082S gas")
    assert gas["status"] == "EXCEEDED"
    assert gas["pct_of_limit"] == 200.0  # 100/50*100


def test_lower_bound_oxygen_violation_when_deficient():
    ox = _by(limit_utilisation(_mk(oxygen_pct=18.0)), "Oxygen")
    assert ox["direction"] == "lower"
    assert ox["status"] == "EXCEEDED"       # below 19.5 => violation
    assert ox["pct_of_limit"] > 100.0


def test_oxygen_ok_when_normal():
    ox = _by(limit_utilisation(_mk(oxygen_pct=20.9)), "Oxygen")
    assert ox["status"] == "OK"
    assert ox["pct_of_limit"] < 100.0


def test_all_parameters_present():
    rows = limit_utilisation(_mk())
    names = {r["parameter"] for r in rows}
    assert names == {"H\u2082S gas", "Oxygen", "Temperature", "Humidity"}
