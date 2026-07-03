#!/usr/bin/env python3
"""
tools/accept.py — Deterministic acceptance tests for T001-T016
Run: python tools/accept.py T003
Exit 0 = pass, exit 1 = fail
"""
import sys, os, json, importlib, time, traceback

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def ok(msg):
    print(f"PASS: {msg}")

def fail(msg, detail=""):
    print(f"FAIL: {msg}")
    if detail:
        print(detail)
    sys.exit(1)

# ============================================================
# T001 — Folders + __init__.py exist
# ============================================================
def accept_T001():
    dirs = ["agents", "knowledge_base/raw", "compliance", "utils", "ui", "tests", "data", "logs", "tools"]
    missing = [d for d in dirs if not os.path.isdir(d)]
    if missing:
        fail(f"Missing directories: {missing}")

    inits = ["agents/__init__.py", "utils/__init__.py", "compliance/__init__.py"]
    missing_init = [f for f in inits if not os.path.isfile(f)]
    if missing_init:
        fail(f"Missing __init__.py: {missing_init}")

    ok("All directories and __init__.py files exist")


# ============================================================
# T002 — All critical packages importable
# ============================================================
def accept_T002():
    packages = [
        ("langgraph", "langgraph"),
        ("langchain", "langchain"),
        ("chromadb", "chromadb"),
        ("google.generativeai", "google.generativeai"),
        ("streamlit", "streamlit"),
        ("folium", "folium"),
        ("reportlab", "reportlab"),
        ("pypdf", "pypdf"),
        ("sentence_transformers", "sentence_transformers"),
    ]
    failed = []
    for name, module in packages:
        try:
            importlib.import_module(module)
        except ImportError as e:
            failed.append((name, str(e)))
    if failed:
        fail(f"Import failures: {failed}", "Run: pip install -r requirements.txt")
    ok(f"All {len(packages)} packages import successfully")


# ============================================================
# T003 — Sensor simulator produces valid SensorReading dicts
# ============================================================
def accept_T003():
    from schema import SensorReading
    from utils.sensor_simulator import generate_sensor_reading

    scenarios = ["normal", "gas_spike", "confined_space", "electrical"]
    for sc in scenarios:
        r = generate_sensor_reading(sc)
        assert isinstance(r, dict), f"Scenario '{sc}' must return dict, got {type(r)}"

        obj = SensorReading(**r)
        assert isinstance(obj, SensorReading), "Dict must map to SensorReading"

        # Validate scenario-specific constraints
        if sc == "gas_spike":
            assert r["gas_ppm"] > 80, f"gas_spike must have gas_ppm>80, got {r['gas_ppm']}"
        elif sc == "normal":
            assert 10 <= r["gas_ppm"] <= 35, f"normal gas_ppm out of range: {r['gas_ppm']}"
            assert 20.5 <= r["oxygen_pct"] <= 21.0, f"normal oxygen_pct out of range: {r['oxygen_pct']}"
        elif sc == "confined_space":
            assert r["oxygen_pct"] < 19.5, f"confined_space oxygen should be <19.5, got {r['oxygen_pct']}"
            assert r["permit_type"] == "confined_space", f"confined_space should have matching permit"
        elif sc == "electrical":
            assert r["humidity_pct"] > 85, f"electrical humidity should be >85, got {r['humidity_pct']}"

        # All must have required keys
        required = ["gas_ppm", "temp_c", "oxygen_pct", "humidity_pct", "permit_type",
                     "worker_count", "zone", "timestamp"]
        missing = [k for k in required if k not in r]
        assert not missing, f"Missing keys: {missing}"

    ok(f"All {len(scenarios)} scenarios produce valid SensorReading dicts")


# ============================================================
# T004 — Gemini vision wrapper returns structured dict
# ============================================================
def accept_T004():
    from utils.gemini_vision import analyze_safety_image

    # Test 1: non-existent file returns error dict with correct keys
    res = analyze_safety_image("nonexistent_file_xyz.jpg")
    assert isinstance(res, dict), f"Must return dict, got {type(res)}"
    assert "hazards" in res, f"Missing 'hazards' key"
    assert "summary" in res, f"Missing 'summary' key"
    assert "source" in res, f"Missing 'source' key"
    assert isinstance(res["hazards"], list), f"hazards must be list, got {type(res['hazards'])}"
    assert isinstance(res["summary"], str), f"summary must be str"
    assert res["source"] in ["gemini", "fallback"], f"source must be gemini or fallback"

    # Test 2: if error key present, it must be string or None
    if "error" in res:
        assert res["error"] is None or isinstance(res["error"], str), f"error must be str or None"

    ok("analyze_safety_image returns correct structure")


# ============================================================
# T005 — VisionAgent returns VisionResult dataclass
# ============================================================
def accept_T005():
    from agents.vision_agent import VisionAgent
    from schema import VisionInput, VisionResult

    agent = VisionAgent()
    result = agent.process(VisionInput(image_path="fake_nonexistent.jpg"))

    assert isinstance(result, VisionResult), f"Must return VisionResult, got {type(result)}"
    assert hasattr(result, "hazards"), "VisionResult must have hazards"
    assert hasattr(result, "summary"), "VisionResult must have summary"
    assert hasattr(result, "source"), "VisionResult must have source"
    assert hasattr(result, "timestamp"), "VisionResult must have timestamp"
    assert isinstance(result.hazards, list), "hazards must be list"
    assert isinstance(result.source, str), "source must be str"

    # If error field present, system handled failure gracefully
    assert hasattr(result, "error"), "VisionResult must have error field"

    ok("VisionAgent returns valid VisionResult dataclass")


# ============================================================
# T006 — ComplianceAgent deterministic evaluation
# ============================================================
def accept_T006():
    from agents.compliance_agent import ComplianceAgent
    from schema import ComplianceInput, ComplianceResult, SensorReading

    agent = ComplianceAgent()

    # Safe scenario: should PASS
    safe = SensorReading(
        gas_ppm=10, temp_c=25, oxygen_pct=20.9, humidity_pct=50,
        permit_type="inspection", worker_count=2, zone="A",
        timestamp="2026-07-03T00:00:00Z"
    )
    r1 = agent.check(ComplianceInput(sensor=safe, active_permits=[]))
    assert isinstance(r1, ComplianceResult), f"Must return ComplianceResult, got {type(r1)}"
    assert r1.pass_status == True, f"Safe scenario should PASS, got {r1.violations}"
    assert r1.highest_severity is None or r1.highest_severity == "LOW" or r1.highest_severity == "MEDIUM", \
        f"Safe scenario severity should be None/LOW/MEDIUM, got {r1.highest_severity}"

    # Dangerous scenario 1: gas spike + hot work → BLOCK CRITICAL
    bad1 = SensorReading(
        gas_ppm=90, temp_c=25, oxygen_pct=20.9, humidity_pct=50,
        permit_type="hot_work", worker_count=2, zone="B",
        timestamp="2026-07-03T00:00:00Z"
    )
    r2 = agent.check(ComplianceInput(sensor=bad1, active_permits=["hot_work"]))
    assert r2.pass_status == False, f"Gas+hotwork should FAIL"
    assert r2.highest_severity == "CRITICAL", f"Expected CRITICAL, got {r2.highest_severity}"
    assert len(r2.violations) > 0, f"Should have violations"

    # Dangerous scenario 2: severe gas leak alone
    bad2 = SensorReading(
        gas_ppm=85, temp_c=25, oxygen_pct=20.9, humidity_pct=50,
        permit_type="inspection", worker_count=1, zone="A",
        timestamp="2026-07-03T00:00:00Z"
    )
    r3 = agent.check(ComplianceInput(sensor=bad2, active_permits=[]))
    assert r3.pass_status == False, f"Gas >80 alone should FAIL"
    assert r3.highest_severity in ["HIGH", "CRITICAL"], f"Expected HIGH or CRITICAL, got {r3.highest_severity}"

    # Boundary scenario: gas exactly at 50 (not > 50, so no BLOCK from R001)
    boundary = SensorReading(
        gas_ppm=50, temp_c=25, oxygen_pct=20.9, humidity_pct=50,
        permit_type="hot_work", worker_count=1, zone="A",
        timestamp="2026-07-03T00:00:00Z"
    )
    r4 = agent.check(ComplianceInput(sensor=boundary, active_permits=["hot_work"]))
    # R001 requires gas_ppm > 50, so at exactly 50 this specific rule should NOT fire
    # But R002 (gas > 80) also won't fire. Whether other rules fire depends on implementation.
    # The key assertion: gas_ppm=50 with hot_work should NOT produce the "explosion risk" CRITICAL violation
    critical_violations = [v for v in r4.violations if v.severity == "CRITICAL" and "explosion" in v.message.lower()]
    assert len(critical_violations) == 0, f"Gas=50 boundary should NOT trigger explosion CRITICAL rule"

    # Empty input handling (should not crash)
    try:
        empty = SensorReading(
            gas_ppm=0, temp_c=0, oxygen_pct=20.9, humidity_pct=0,
            permit_type="none", worker_count=0, zone="A",
            timestamp="2026-07-03T00:00:00Z"
        )
        r5 = agent.check(ComplianceInput(sensor=empty, active_permits=[]))
        assert isinstance(r5, ComplianceResult), "Empty-ish input should still return ComplianceResult"
    except Exception as e:
        fail(f"ComplianceAgent crashed on minimal input: {e}")

    # Violation structure check
    for v in r2.violations:
        assert hasattr(v, "rule_id"), "Violation must have rule_id"
        assert hasattr(v, "severity"), "Violation must have severity"
        assert hasattr(v, "message"), "Violation must have message"
        assert hasattr(v, "oisd_reference"), "Violation must have oisd_reference"
        assert v.severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"], f"Invalid severity: {v.severity}"

    ok("ComplianceAgent passes all behavioral tests: safe, dangerous, boundary, empty, structure")


# ============================================================
# T007 — KnowledgeAgent RAG returns citations
# ============================================================
def accept_T007():
    from agents.knowledge_agent import KnowledgeAgent
    from schema import QueryInput, KnowledgeResult

    agent = KnowledgeAgent()

    # Test 1: basic query returns KnowledgeResult
    r1 = agent.query(QueryInput(query_text="confined space entry requirements"))
    assert isinstance(r1, KnowledgeResult), f"Must return KnowledgeResult, got {type(r1)}"
    assert isinstance(r1.answer, str), "answer must be string"
    assert len(r1.answer) > 10, f"Answer too short: {r1.answer}"

    # Test 2: sources must be a list (may be empty if DB is empty, but must be list)
    assert isinstance(r1.sources, list), f"sources must be list, got {type(r1.sources)}"
    assert isinstance(r1.confidence, (int, float)), "confidence must be numeric"

    # Test 3: if synthetic PDF was ingested, sources should be non-empty
    # (This is a soft check — if ChromaDB ingestion failed, this will catch it)
    if len(r1.sources) == 0:
        print("WARNING: No sources returned. Knowledge base may be empty.")

    # Test 4: answer should contain some safety-relevant words
    safety_keywords = ["confined", "space", "entry", "permit", "safety", "oxygen",
                       "rescue", "ventilation", "monitor", "require", "must"]
    has_keyword = any(kw in r1.answer.lower() for kw in safety_keywords)
    assert has_keyword, f"Answer doesn't contain any safety keywords: {r1.answer[:200]}"

    # Test 5: different queries should return different results (or at least not crash)
    r2 = agent.query(QueryInput(query_text="gas leak emergency response"))
    assert isinstance(r2, KnowledgeResult), "Second query must also return KnowledgeResult"

    ok("KnowledgeAgent returns citations and relevant answers")


# ============================================================
# T008 — SafetyAgent compound risk scoring
# ============================================================
def accept_T008():
    from agents.safety_agent import SafetyAgent
    from schema import SensorInput, SensorReading, SafetyAlert

    agent = SafetyAgent()

    # Test 1: Safe conditions → low risk
    safe = SensorReading(
        gas_ppm=10, temp_c=25, oxygen_pct=20.9, humidity_pct=50,
        permit_type="inspection", worker_count=1, zone="A",
        timestamp="2026-07-03T00:00:00Z"
    )
    r1 = agent.process(SensorInput(reading=safe, active_permits=[]))
    assert isinstance(r1, SafetyAlert), f"Must return SafetyAlert, got {type(r1)}"
    assert r1.risk_score < 40, f"Safe scenario should be <40, got {r1.risk_score}"
    assert r1.zone == "A", f"Zone must match input"

    # Test 2: Compound danger (gas spike + hot work + low O2) → high risk
    danger = SensorReading(
        gas_ppm=90, temp_c=45, oxygen_pct=18.0, humidity_pct=50,
        permit_type="none", worker_count=1, zone="B",
        timestamp="2026-07-03T00:00:00Z"
    )
    r2 = agent.process(SensorInput(reading=danger, active_permits=["hot_work"]))
    assert r2.risk_score >= 80, f"Compound danger should score >=80, got {r2.risk_score}"
    assert r2.risk_score <= 100, f"Risk must be capped at 100, got {r2.risk_score}"
    assert len(r2.triggered_rules) > 0, "Should have triggered rules"
    assert len(r2.recommended_action) > 10, f"recommended_action too short: {r2.recommended_action}"

    # Test 3: Gas spike alone (no hot work) → medium risk (NOT high compound)
    gas_only = SensorReading(
        gas_ppm=85, temp_c=25, oxygen_pct=20.9, humidity_pct=50,
        permit_type="inspection", worker_count=1, zone="A",
        timestamp="2026-07-03T00:00:00Z"
    )
    r3 = agent.process(SensorInput(reading=gas_only, active_permits=[]))
    # Gas alone should score less than gas+hot_work compound
    assert 40 <= r3.risk_score < r2.risk_score, \
        f"Gas alone ({r3.risk_score}) should be less than compound ({r2.risk_score})"

    # Test 4: Hot work permit alone with safe gas → low risk
    permit_only = SensorReading(
        gas_ppm=10, temp_c=25, oxygen_pct=20.9, humidity_pct=50,
        permit_type="none", worker_count=1, zone="A",
        timestamp="2026-07-03T00:00:00Z"
    )
    r4 = agent.process(SensorInput(reading=permit_only, active_permits=["hot_work"]))
    assert r4.risk_score < 40, f"Permit alone should be low risk, got {r4.risk_score}"

    # Test 5: Low oxygen alone (no gas, no permit) → medium risk
    low_o2 = SensorReading(
        gas_ppm=5, temp_c=25, oxygen_pct=18.5, humidity_pct=50,
        permit_type="none", worker_count=1, zone="A",
        timestamp="2026-07-03T00:00:00Z"
    )
    r5 = agent.process(SensorInput(reading=low_o2, active_permits=[]))
    assert 30 <= r5.risk_score <= 80, f"Low O2 should be medium risk, got {r5.risk_score}"

    ok("SafetyAgent passes compound risk scoring tests: safe, compound, gas-only, permit-only, low-O2")


# ============================================================
# T009 — Orchestrator routing + request_id preservation
# ============================================================
def accept_T009():
    from agents.orchestrator import Orchestrator
    from schema import OrchestratorInput, OrchestratorResult

    orch = Orchestrator()

    # Test 1: Query routing → populates knowledge
    test_id_1 = "test-req-query-001"
    r1 = orch.process(OrchestratorInput(
        input_type="query",
        data={"query_text": "confined space entry requirements"},
        request_id=test_id_1
    ))
    assert isinstance(r1, OrchestratorResult), f"Must return OrchestratorResult, got {type(r1)}"
    assert r1.request_id == test_id_1, f"Request ID not preserved. Expected {test_id_1}, got {r1.request_id}"
    assert r1.knowledge is not None, "Query route should populate knowledge field"
    assert r1.knowledge.answer is not None, "Knowledge answer should not be None"
    assert r1.input_type == "query", "input_type should be echoed"

    # Test 2: Sensor routing → populates safety + compliance
    test_id_2 = "test-req-sensor-002"
    sensor_data = {
        "reading": {
            "gas_ppm": 85, "temp_c": 30, "oxygen_pct": 19.0,
            "humidity_pct": 50, "permit_type": "hot_work",
            "worker_count": 2, "zone": "B",
            "timestamp": "2026-07-03T00:00:00Z",
            "pressure_bar": 1.01, "rescue_team_present": True
        },
        "active_permits": ["hot_work"]
    }
    r2 = orch.process(OrchestratorInput(
        input_type="sensor",
        data=sensor_data,
        request_id=test_id_2
    ))
    assert r2.request_id == test_id_2, f"Request ID not preserved"
    assert r2.safety is not None, "Sensor route should populate safety"
    assert r2.compliance is not None, "Sensor route should populate compliance"
    assert r2.safety.risk_score > 0, "Safety score should be >0 for gas spike + hot work"
    assert r2.compliance.pass_status == False, "Compliance should FAIL for gas spike + hot work"
    assert r2.compliance.highest_severity == "CRITICAL", f"Expected CRITICAL, got {r2.compliance.highest_severity}"

    # Test 3: Unknown input type handled gracefully
    r3 = orch.process(OrchestratorInput(
        input_type="unknown_type",
        data={},
        request_id="test-req-unknown"
    ))
    assert isinstance(r3, OrchestratorResult), "Unknown type must still return OrchestratorResult"

    # Test 4: Timestamp present and non-empty
    assert r1.timestamp and len(r1.timestamp) > 5, f"Timestamp missing or empty"

    ok("Orchestrator routes correctly: query→knowledge, sensor→safety+compliance, preserves request_id")


# ============================================================
# T010 — PDF report generator
# ============================================================
def accept_T010():
    from utils.report_generator import generate_pdf_report
    from schema import OrchestratorResult, SafetyAlert, ComplianceResult, ComplianceViolation
    import os

    # Test 1: Minimal result (all None fields)
    minimal = OrchestratorResult(request_id="test-123", input_type="query")
    generate_pdf_report(minimal, "test_minimal.pdf")
    assert os.path.exists("test_minimal.pdf"), "PDF not created"
    size = os.path.getsize("test_minimal.pdf")
    assert size > 500, f"PDF too small ({size} bytes), likely empty"
    os.remove("test_minimal.pdf")

    # Test 2: Full result with violations
    full = OrchestratorResult(
        request_id="test-456",
        input_type="sensor",
        safety=SafetyAlert(
            risk_score=95, triggered_rules=["R001", "R003"],
            recommended_action="Evacuate zone B immediately",
            zone="B"
        ),
        compliance=ComplianceResult(
            pass_status=False,
            violations=[
                ComplianceViolation(
                    rule_id="R001", name="Hot Work Gas Spike",
                    severity="CRITICAL", message="Explosion risk",
                    oisd_reference="OISD-STD-105 Sec 4.2"
                )
            ],
            highest_severity="CRITICAL"
        )
    )
    generate_pdf_report(full, "test_full.pdf")
    assert os.path.exists("test_full.pdf"), "Full PDF not created"
    assert os.path.getsize("test_full.pdf") > 1000, "Full PDF should be larger"
    os.remove("test_full.pdf")

    # Test 3: Does not crash on None safety/compliance
    try:
        partial = OrchestratorResult(request_id="test-789", input_type="full_scan")
        generate_pdf_report(partial, "test_partial.pdf")
        assert os.path.exists("test_partial.pdf")
        os.remove("test_partial.pdf")
    except Exception as e:
        fail(f"PDF generator crashed on partial result: {e}")

    ok("PDF report generator handles minimal, full, and partial results")


# ============================================================
# T011 — Streamlit UI starts and serves HTTP 200 on port 8502
# ============================================================
def accept_T011():
    import subprocess, sys, time

    # Kill any existing process on 8502
    try:
        subprocess.run(
            f'for /f "tokens=5" %a in (\'netstat -aon ^| findstr :8502 ^| findstr LISTENING\') do taskkill /PID %a /F',
            shell=True, capture_output=True, timeout=5
        )
    except Exception:
        pass
    time.sleep(1)

    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "ui/app.py",
         "--server.headless", "true", "--server.port", "8502",
         "--server.address", "127.0.0.1"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        cwd=PROJECT_ROOT
    )

    # Wait for Streamlit to boot (up to 15 seconds)
    connected = False
    for attempt in range(15):
        time.sleep(1)
        try:
            import urllib.request
            resp = urllib.request.urlopen("http://127.0.0.1:8502", timeout=3)
            if resp.status == 200:
                connected = True
                break
        except Exception:
            continue

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()

    if not connected:
        stderr_output = ""
        try:
            stderr_output = proc.stderr.read().decode()[:500]
        except Exception:
            pass
        fail("Streamlit did not serve HTTP 200 on port 8502", f"stderr: {stderr_output}")

    ok("Streamlit UI serves HTTP 200 on port 8502")


# ============================================================
# T012 — Schema contract tests exist and run
# ============================================================
def accept_T012():
    assert os.path.isfile("tests/test_schema_contracts.py"), "tests/test_schema_contracts.py does not exist"

    # Verify it has actual test functions (not empty)
    with open("tests/test_schema_contracts.py", "r") as f:
        content = f.read()
    assert "def test_" in content or "class Test" in content, \
        "test_schema_contracts.py has no test functions"

    # Count test functions
    import re
    test_count = len(re.findall(r"def test_", content))
    assert test_count >= 5, f"Expected at least 5 test functions, found {test_count}"

    ok(f"Schema contract tests exist with {test_count} test functions")


# ============================================================
# T013 — Integration test suite has 14+ tests
# ============================================================
def accept_T013():
    assert os.path.isfile("tests/test_all.py"), "tests/test_all.py does not exist"

    with open("tests/test_all.py", "r") as f:
        content = f.read()

    import re
    test_count = len(re.findall(r"def test_", content))
    assert test_count >= 14, f"Expected at least 14 tests, found {test_count}"

    # Verify it covers multiple agents
    assert "vision" in content.lower() or "Vision" in content, "Missing vision tests"
    assert "compliance" in content.lower() or "Compliance" in content, "Missing compliance tests"
    assert "safety" in content.lower() or "Safety" in content, "Missing safety tests"
    assert "knowledge" in content.lower() or "Knowledge" in content, "Missing knowledge tests"
    assert "orchestrator" in content.lower() or "Orchestrator" in content, "Missing orchestrator tests"

    ok(f"Integration test suite has {test_count} tests covering all agents")


# ============================================================
# T014 — ChromaDB build script ingests PDFs
# ============================================================
def accept_T014():
    assert os.path.isfile("knowledge_base/build_db.py"), "knowledge_base/build_db.py does not exist"

    # Run it (it should not crash even if DB already exists)
    import subprocess
    result = subprocess.run(
        [sys.executable, "knowledge_base/build_db.py"],
        capture_output=True, text=True, timeout=120, cwd=PROJECT_ROOT
    )
    assert result.returncode == 0, f"build_db.py failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"

    # Verify ChromaDB has data
    try:
        import chromadb
        try:
            from chromadb.config import Settings
            client = chromadb.PersistentClient(
                path="./data/chroma_db",
                settings=Settings(anonymized_telemetry=False)
            )
        except Exception:
            client = chromadb.PersistentClient(path="./data/chroma_db")
        collections = client.list_collections()
        has_data = False
        for col in collections:
            try:
                c = client.get_collection(col) if isinstance(col, str) else col
                count = c.count()
                if count > 0:
                    has_data = True
                    break
            except Exception:
                continue
        assert has_data, "ChromaDB collection is empty after build_db.py"
    except ImportError:
        print("WARNING: Could not verify ChromaDB data (chromadb import failed)")

    ok("build_db.py executed successfully and ChromaDB has data")


# ============================================================
# T015 — Vizag scenario: CRITICAL + risk>=80
# ============================================================
def accept_T015():
    assert os.path.isfile("main.py"), "main.py does not exist"

    with open("main.py", "r") as f:
        content = f.read()
    assert "run_vizag_scenario" in content, "main.py must define run_vizag_scenario()"

    import importlib.util
    spec = importlib.util.spec_from_file_location("main", "main.py")
    main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(main)

    result = main.run_vizag_scenario()

    assert result is not None, "run_vizag_scenario() returned None"
    assert hasattr(result, "compliance"), "Result must have compliance"
    assert hasattr(result, "safety"), "Result must have safety"

    assert result.compliance is not None, "Compliance result is None"
    assert result.compliance.highest_severity == "CRITICAL", \
        f"Expected CRITICAL, got {result.compliance.highest_severity}"
    assert len(result.compliance.violations) > 0, "Should have violations"

    assert result.safety is not None, "Safety result is None"
    assert result.safety.risk_score >= 80, \
        f"Expected risk>=80, got {result.safety.risk_score}"
    assert result.safety.risk_score <= 100, f"Risk capped at 100"

    ok(f"Vizag scenario: severity={result.compliance.highest_severity}, risk={result.safety.risk_score}")


# ============================================================
# T016 — DemoRunner two-phase validation
# ============================================================
def accept_T016():
    from utils.demo_runner import DemoRunner

    runner = DemoRunner()
    assert hasattr(runner, "run_phases"), "DemoRunner must have run_phases()"

    result = runner.run_phases()
    assert isinstance(result, tuple) and len(result) == 2, \
        f"run_phases() must return (safe, escalated), got {type(result)}"

    safe, escalated = result

    # Safe phase: at least 2 readings, all low risk
    assert isinstance(safe, list), f"safe must be list, got {type(safe)}"
    assert len(safe) >= 2, f"safe phase needs >=2 results, got {len(safe)}"
    for i, r in enumerate(safe):
        assert hasattr(r, "safety"), f"safe[{i}] must have .safety"
        assert r.safety.risk_score < 50, \
            f"safe[{i}] risk={r.safety.risk_score} should be <50"

    # Escalation phase: at least 2 readings, last one high risk
    assert isinstance(escalated, list), f"escalated must be list, got {type(escalated)}"
    assert len(escalated) >= 2, f"escalated phase needs >=2 results, got {len(escalated)}"

    # Risk should increase over escalation
    first_risk = escalated[0].safety.risk_score
    last_risk = escalated[-1].safety.risk_score
    assert last_risk >= first_risk, \
        f"Escalation risk should increase: first={first_risk}, last={last_risk}"
    assert last_risk >= 70, \
        f"Final escalation risk should be >=70, got {last_risk}"

    ok(f"DemoRunner validated: safe_max_risk={max(r.safety.risk_score for r in safe)}, "
       f"escalated_final_risk={last_risk}")


# ============================================================
# MAIN ROUTER
# ============================================================
ACCEPTORS = {
    "T001": accept_T001,
    "T002": accept_T002,
    "T003": accept_T003,
    "T004": accept_T004,
    "T005": accept_T005,
    "T006": accept_T006,
    "T007": accept_T007,
    "T008": accept_T008,
    "T009": accept_T009,
    "T010": accept_T010,
    "T011": accept_T011,
    "T012": accept_T012,
    "T013": accept_T013,
    "T014": accept_T014,
    "T015": accept_T015,
    "T016": accept_T016,
}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/accept.py T001")
        sys.exit(1)

    task_id = sys.argv[1].upper()

    if task_id not in ACCEPTORS:
        print(f"Unknown task: {task_id}")
        print(f"Valid tasks: {', '.join(sorted(ACCEPTORS.keys()))}")
        sys.exit(1)

    try:
        print(f"Running acceptance for {task_id}...")
        ACCEPTORS[task_id]()
        print(f"{task_id} PASS")
        sys.exit(0)
    except AssertionError as e:
        fail(f"{task_id} ASSERTION FAILED", str(e))
        sys.exit(1)
    except Exception as e:
        fail(f"{task_id} EXCEPTION", traceback.format_exc())
        sys.exit(1)
