"""Tests for the FastAPI backend using the in-process TestClient (offline, fast)."""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from fastapi.testclient import TestClient  # noqa: E402
from backend.main import app  # noqa: E402

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_scan_vizag_critical():
    body = {"reading": {"gas_ppm": 120, "oxygen_pct": 18.4, "temp_c": 41,
                        "permit_type": "hot_work", "zone": "Zone-C-Confined",
                        "worker_count": 4}, "active_permits": ["hot_work"]}
    r = client.post("/api/scan", json=body)
    assert r.status_code == 200
    d = r.json()
    assert d["risk_score"] == 100
    assert d["compliance"]["highest_severity"] == "CRITICAL"
    assert d["interventions"]["recommended"] is not None
    assert d["confidence"]["label"] in ("high", "medium", "low")
    assert d["single_sensor"]["total"] == 3
    assert len(d["limits"]) == 4


def test_scan_rejects_bad_reading():
    body = {"reading": {"oxygen_pct": 150}, "active_permits": []}  # oxygen>100 invalid
    r = client.post("/api/scan", json=body)
    assert r.status_code == 422


def test_zones_returns_graph_and_conflicts():
    r = client.get("/api/zones", params={"gas": 90, "oxygen": 18, "permits": "hot_work"})
    assert r.status_code == 200
    d = r.json()
    assert "colors" in d and "graph" in d
    assert isinstance(d["conflicts"], list)
    assert len(d["graph"]["nodes"]) > 0


def test_incidents_and_benchmark_and_audit():
    assert client.get("/api/incidents").status_code == 200
    b = client.get("/api/benchmark").json()
    assert b["headline"]["false_negative_reduction_pct"] > 0
    assert client.get("/api/audit/verify").json()["valid"] in (True, False)


def test_exposure_and_gases():
    g = client.get("/api/gases").json()
    assert "h2s" in g
    rep = client.get("/api/exposure", params={"gas": "h2s", "ppm": 120}).json()
    assert rep["exposure"]["status"] == "IDLH"
    assert rep["evacuation_radius_m"] > 0


def test_languages_and_dispatch_and_briefing():
    langs = client.get("/api/languages").json()
    assert "Telugu" in langs
    body = {"reading": {"gas_ppm": 120, "oxygen_pct": 18.4, "zone": "Zone-C-Confined"},
            "active_permits": ["hot_work"], "language": "Telugu"}
    d = client.post("/api/dispatch", json=body).json()
    assert d["message"] and d["severity"] == "CRITICAL"
    assert set(["SMS", "Email"]).issubset(set(d["channels"]))
    br = client.post("/api/briefing", json=body).json()
    assert "briefing" in br and br["request_id"]


def test_facilities():
    f = client.get("/api/facilities", params={"zone": "Zone-C-Confined"}).json()
    assert len(f["nearest"]) > 0
    assert "contacts" in f


def test_stress_test_zero_false_escalations():
    r = client.post("/api/stress-test", params={"trials": 100})
    assert r.status_code == 200
    d = r.json()
    assert d["trials_run"] == 100
    assert d["false_escalations"] == 0
    assert d["false_escalation_rate"] == "0%"
