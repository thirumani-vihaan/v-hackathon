"""Contract tests for schema dataclasses (validation + shapes)."""
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from schema import (  # noqa: E402
    SensorReading, Hazard, SafetyAlert, ComplianceResult, ComplianceViolation,
    VisionResult, KnowledgeResult, OrchestratorResult, OrchestratorInput,
    VisionInput, SensorInput, QueryInput, ComplianceInput,
)


def _reading(**kw):
    base = dict(gas_ppm=5, temp_c=30, oxygen_pct=20.9, humidity_pct=50,
                permit_type="general", worker_count=1, zone="Z",
                timestamp="2026-07-03T00:00:00")
    base.update(kw)
    return SensorReading(**base)


def test_sensor_reading_defaults():
    r = _reading()
    assert r.pressure_bar == 1.013
    assert r.rescue_team_present is True


def test_sensor_reading_to_dict_roundtrip():
    r = _reading()
    d = r.to_dict()
    r2 = SensorReading(**d)
    assert r2.to_dict() == d


def test_oxygen_out_of_range_rejected():
    with pytest.raises(ValueError):
        _reading(oxygen_pct=150)


def test_negative_gas_rejected():
    with pytest.raises(ValueError):
        _reading(gas_ppm=-1)


def test_negative_worker_count_rejected():
    with pytest.raises(ValueError):
        _reading(worker_count=-5)


def test_hazard_confidence_bounds():
    with pytest.raises(ValueError):
        Hazard(type="no_helmet", confidence=1.5, bbox=[0, 0, 1, 1])


def test_hazard_bbox_length():
    with pytest.raises(ValueError):
        Hazard(type="no_helmet", confidence=0.5, bbox=[0, 0, 1])


def test_safety_alert_score_clamped_high():
    a = SafetyAlert(risk_score=250, triggered_rules=[], recommended_action="x",
                    zone="Z")
    assert a.risk_score == 100


def test_safety_alert_score_clamped_low():
    a = SafetyAlert(risk_score=-10, triggered_rules=[], recommended_action="x",
                    zone="Z")
    assert a.risk_score == 0


def test_input_dataclasses_have_request_id():
    assert VisionInput(image_path="x").request_id
    assert SensorInput(reading=_reading()).request_id
    assert QueryInput(query_text="x").request_id
    assert ComplianceInput(sensor=_reading()).request_id
    assert OrchestratorInput(input_type="sensor", data={}).request_id


def test_compliance_result_shape():
    v = ComplianceViolation(rule_id="R001", name="n", severity="HIGH",
                            message="m", oisd_reference="ref")
    cr = ComplianceResult(pass_status=False, violations=[v],
                          highest_severity="HIGH")
    assert cr.violations[0].rule_id == "R001"


def test_orchestrator_result_optional_fields_default_none():
    r = OrchestratorResult(request_id="x", input_type="sensor")
    assert r.vision is None and r.safety is None
    assert r.compliance is None and r.knowledge is None
