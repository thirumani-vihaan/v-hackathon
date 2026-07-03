"""Tests for the 'feels real' upgrade utilities (pure, offline-safe)."""
import os
import sys
import json
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from schema import Hazard, OrchestratorInput  # noqa: E402
from utils.audit_logger import (  # noqa: E402
    append_event, read_last_n, event_from_result,
)
from utils.evidence_export import export_zip  # noqa: E402
from utils.vision_overlay import draw_hazards  # noqa: E402
from utils.zone_status import zone_colors, time_to_critical  # noqa: E402
from utils.plant_layout import ensure_plant_layout  # noqa: E402
from utils import translations  # noqa: E402


# ---- audit logger ----
def test_audit_append_and_read_roundtrip():
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl")
    tmp.close()
    append_event({"type": "t1", "n": 1}, path=tmp.name)
    append_event({"type": "t2", "n": 2}, path=tmp.name)
    last = read_last_n(5, path=tmp.name)
    assert len(last) == 2
    assert last[-1]["n"] == 2
    assert "timestamp" in last[-1]
    os.unlink(tmp.name)


def test_audit_never_logs_secrets():
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl")
    tmp.close()
    append_event({"type": "x", "gemini_api_key": "SECRET", "api_key": "SECRET",
                  "nested": {"token": "SECRET", "ok": 1}}, path=tmp.name)
    raw = open(tmp.name, encoding="utf-8").read()
    assert "SECRET" not in raw
    ev = read_last_n(1, path=tmp.name)[-1]
    assert "gemini_api_key" not in ev and "api_key" not in ev
    assert ev["nested"] == {"ok": 1}
    os.unlink(tmp.name)


def test_event_from_result_captures_evidence():
    from agents.orchestrator import Orchestrator
    from utils.sensor_simulator import vizag_critical_reading
    orch = Orchestrator()
    r = orch.run(OrchestratorInput(
        input_type="sensor",
        data={"reading": vizag_critical_reading().to_dict(),
              "active_permits": ["hot_work"]}))
    ev = event_from_result(r, sensor=vizag_critical_reading().to_dict(),
                           active_permits=["hot_work"], event_type="sensor_scan")
    assert ev["type"] == "sensor_scan"
    assert ev["request_id"] == r.request_id
    assert ev["safety"]["risk_score"] >= 80
    assert ev["compliance"]["highest_severity"] == "CRITICAL"
    assert isinstance(ev["compliance"]["violations"], list)


# ---- evidence export ----
def test_evidence_export_creates_zip():
    import zipfile
    zp = os.path.join(tempfile.mkdtemp(), "pkg.zip")
    # seed a log so there is at least one artifact
    log = os.path.join(_ROOT, "data", "evidence_log.jsonl")
    append_event({"type": "test_seed"}, path=log)
    out = export_zip(zip_path=zp)
    assert out == zp
    assert os.path.isfile(zp)
    with zipfile.ZipFile(zp) as zf:
        assert "manifest.txt" in zf.namelist()


# ---- vision overlay ----
def test_vision_overlay_returns_image():
    sample = os.path.join(_ROOT, "data", "test_safety_image.jpg")
    hz = [Hazard(type="smoke_fire", confidence=0.8, bbox=[10, 10, 60, 70])]
    img = draw_hazards(sample, hz)
    assert img.size[0] > 0 and img.size[1] > 0


def test_vision_overlay_bad_path_placeholder():
    img = draw_hazards("no_such_file.jpg", [])
    assert img.size[0] > 0  # placeholder returned, no crash


# ---- zone status ----
def test_zone_colors_rules():
    c = zone_colors(90, 17.5, 95, ["hot_work", "electrical"])
    assert c["Zone-A-Tank-Farm"] == "red"     # gas>80
    assert c["Zone-B-Process"] == "red"       # gas>80 or (gas>50 & hot_work)
    assert c["Zone-C-Confined"] == "red"      # oxygen<18
    assert c["Zone-D-Substation"] == "red"    # electrical & humidity>90
    safe = zone_colors(5, 20.9, 40, [])
    assert set(safe.values()) == {"green"}


def test_time_to_critical_behaviour():
    assert time_to_critical([80]) == 0.0                 # already critical
    assert time_to_critical([20, 20, 20]) is None        # flat
    assert time_to_critical([10, 30]) is None or time_to_critical([10, 30]) >= 0
    eta = time_to_critical([10, 20, 30, 40, 50])
    assert eta is not None and eta >= 0.0


# ---- plant layout ----
def test_plant_layout_generated():
    p = ensure_plant_layout(force=True)
    assert os.path.isfile(p)


# ---- translations ----
def test_translations_static_fallback():
    msg, src = translations.translate_evac("Telugu", "Zone-B", "req-1",
                                            use_gemini=False)
    assert src == "static"
    assert "req-1" in msg
    en, ensrc = translations.translate_evac("English", "Zone-A", "req-2",
                                            use_gemini=False)
    assert ensrc == "static" and "req-2" in en


# ---- demo runner trace ----
def test_demo_runner_writes_trace():
    from utils.demo_runner import DemoRunner
    trace = os.path.join(tempfile.mkdtemp(), "demo_trace.jsonl")
    safe, escalated = DemoRunner().run_phases(seconds=4, trace_path=trace)
    assert len(safe) >= 2 and len(escalated) >= 2
    assert all(r.safety.risk_score < 50 for r in safe)
    assert escalated[-1].safety.risk_score >= 70
    lines = [json.loads(x) for x in open(trace, encoding="utf-8").read().splitlines()]
    assert len(lines) == 8
    assert lines[0]["phase"] == "safe"
    assert lines[-1]["phase"] == "escalation"
    assert "risk_score" in lines[-1] and "violations_count" in lines[-1]
