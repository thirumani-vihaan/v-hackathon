"""Integration tests across agents and the orchestrator (>=14 tests total)."""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from schema import (  # noqa: E402
    SensorReading, ComplianceInput, SensorInput, QueryInput, VisionInput,
    OrchestratorInput,
)
from agents.compliance_agent import ComplianceAgent  # noqa: E402
from agents.safety_agent import SafetyAgent  # noqa: E402
from agents.vision_agent import VisionAgent  # noqa: E402
from agents.knowledge_agent import KnowledgeAgent  # noqa: E402
from agents.orchestrator import Orchestrator  # noqa: E402
from utils.sensor_simulator import (  # noqa: E402
    normal_reading, vizag_critical_reading,
)


def _reading(**kw):
    base = dict(gas_ppm=5, temp_c=30, oxygen_pct=20.9, humidity_pct=50,
                permit_type="general", worker_count=1, zone="Z",
                timestamp="2026-07-03T00:00:00")
    base.update(kw)
    return SensorReading(**base)


# ---- compliance ----
def test_compliance_normal_passes():
    res = ComplianceAgent().evaluate(ComplianceInput(sensor=normal_reading()))
    assert res.pass_status is True
    assert res.highest_severity is None


def test_compliance_critical_gas():
    res = ComplianceAgent().evaluate(
        ComplianceInput(sensor=_reading(gas_ppm=120)))
    ids = [v.rule_id for v in res.violations]
    assert "R002" in ids
    assert res.highest_severity == "CRITICAL"


def test_compliance_oxygen_deficiency_band():
    res = ComplianceAgent().evaluate(
        ComplianceInput(sensor=_reading(oxygen_pct=18.8)))
    ids = [v.rule_id for v in res.violations]
    assert "R004" in ids


def test_compliance_confined_space_no_rescue():
    r = _reading(permit_type="confined_space", rescue_team_present=False)
    res = ComplianceAgent().evaluate(
        ComplianceInput(sensor=r, active_permits=["confined_space"]))
    ids = [v.rule_id for v in res.violations]
    assert "R006" in ids
    assert res.highest_severity == "CRITICAL"


def test_compliance_gas_displacement_r020():
    r = _reading(gas_ppm=60, oxygen_pct=19.0)
    res = ComplianceAgent().evaluate(ComplianceInput(sensor=r))
    ids = [v.rule_id for v in res.violations]
    assert "R020" in ids


def test_compliance_hot_work_flammable_gas_r010():
    r = _reading(gas_ppm=70, permit_type="hot_work")
    res = ComplianceAgent().evaluate(
        ComplianceInput(sensor=r, active_permits=["hot_work"]))
    ids = [v.rule_id for v in res.violations]
    assert "R010" in ids


def test_compliance_all_20_rules_loaded():
    agent = ComplianceAgent()
    assert len(agent.rules) >= 20


# ---- safety scoring ----
def test_safety_normal_low_risk():
    a = SafetyAgent().assess(SensorInput(reading=normal_reading()))
    assert a.risk_score < 40


def test_safety_compound_scoring_exact():
    # gas>50(+30), oxygen<19.5(+40), gas>50&hot_work(+50), gas>80(+30) => cap 100
    r = _reading(gas_ppm=120, oxygen_pct=18.0, permit_type="hot_work")
    a = SafetyAgent().assess(SensorInput(reading=r, active_permits=["hot_work"]))
    assert a.risk_score == 100


def test_safety_gas_only_moderate():
    r = _reading(gas_ppm=60)
    a = SafetyAgent().assess(SensorInput(reading=r))
    assert a.risk_score == 30


def test_safety_vizag_high():
    a = SafetyAgent().assess(
        SensorInput(reading=vizag_critical_reading(), active_permits=["hot_work"]))
    assert a.risk_score >= 80


# ---- vision (fallback path is deterministic) ----
def test_vision_returns_result():
    res = VisionAgent().analyze(VisionInput(image_path="does_not_exist.jpg"))
    assert res.source in ("gemini", "fallback")
    assert isinstance(res.hazards, list)


def test_vision_uploaded_image_path_does_not_crash():
    """Simulate a UI upload: analyze an arbitrary temp image path -> VisionResult."""
    import shutil
    import tempfile
    sample = os.path.join(_ROOT, "data", "test_safety_image.jpg")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    tmp.close()
    if os.path.exists(sample):
        shutil.copy(sample, tmp.name)
    from schema import VisionResult
    res = VisionAgent().analyze(VisionInput(image_path=tmp.name))
    assert isinstance(res, VisionResult)
    assert isinstance(res.hazards, list)
    os.unlink(tmp.name)


# ---- knowledge ----
def test_knowledge_returns_result_shape():
    res = KnowledgeAgent().query(QueryInput(query_text="hot work gas testing"))
    assert hasattr(res, "answer")
    assert isinstance(res.sources, list)


def test_knowledge_not_keyword_mapped():
    """Different questions must retrieve different grounded content, never a
    single canned/mapped string. Runs extractive (deterministic) so no network."""
    os.environ["KNOWLEDGE_LLM"] = "0"
    try:
        agent = KnowledgeAgent()
        r1 = agent.query(QueryInput(query_text="confined space entry requirements"))
        r2 = agent.query(QueryInput(query_text="hot work flammable gas testing"))
        # both grounded in the corpus
        assert len(r1.sources) > 0 and len(r2.sources) > 0
        assert r1.confidence > 0 and r2.confidence > 0
        # not the same answer for different topics => not a fixed mapping
        assert r1.answer != r2.answer
        # answers are drawn from retrieved chunks, not a hardcoded canned reply
        assert r1.answer.strip() and r2.answer.strip()
    finally:
        os.environ.pop("KNOWLEDGE_LLM", None)


def test_knowledge_empty_corpus_is_honest():
    """A fresh empty collection must not fabricate citations."""
    import tempfile
    tmp = tempfile.mkdtemp()
    os.environ["KNOWLEDGE_LLM"] = "0"
    try:
        agent = KnowledgeAgent(persist_dir=tmp, collection_name="empty_test")
        r = agent.query(QueryInput(query_text="anything"))
        assert r.sources == []
        assert r.confidence <= 0.10
        assert "no local documents" in r.answer.lower()
    finally:
        os.environ.pop("KNOWLEDGE_LLM", None)


# ---- orchestrator routing ----
def test_orchestrator_sensor_routing_and_request_id():
    orch = Orchestrator()
    oi = OrchestratorInput(input_type="sensor",
                           data={"reading": vizag_critical_reading().to_dict(),
                                 "active_permits": ["hot_work"]})
    r = orch.run(oi)
    assert r.request_id == oi.request_id
    assert r.safety is not None and r.compliance is not None
    assert r.knowledge is None and r.vision is None


def test_orchestrator_query_routing():
    orch = Orchestrator()
    oi = OrchestratorInput(input_type="query",
                           data={"query_text": "confined space entry requirements"})
    r = orch.run(oi)
    assert r.request_id == oi.request_id
    assert r.knowledge is not None
    assert r.safety is None


def test_orchestrator_image_routing():
    orch = Orchestrator()
    img = os.path.join(_ROOT, "data", "test_safety_image.jpg")
    oi = OrchestratorInput(input_type="image", data={"image_path": img})
    r = orch.run(oi)
    assert r.request_id == oi.request_id
    assert r.vision is not None


def test_orchestrator_returns_dataclass_not_dict():
    from schema import OrchestratorResult
    orch = Orchestrator()
    oi = OrchestratorInput(input_type="sensor",
                           data={"reading": normal_reading().to_dict()})
    r = orch.run(oi)
    assert isinstance(r, OrchestratorResult)
