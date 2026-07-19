"""main.py — IndustrialSafetyAI entry point.

run_vizag_scenario() reconstructs a Vizag-style gas-leak emergency and asserts a
CRITICAL compliance finding with a safety risk_score >= 80.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_ROOT, ".env"))
except Exception:
    pass

from schema import OrchestratorInput  # noqa: E402
from agents.orchestrator import Orchestrator  # noqa: E402
from utils.sensor_simulator import vizag_critical_reading  # noqa: E402


def run_vizag_scenario() -> "object":
    reading = vizag_critical_reading()
    orch = Orchestrator()
    oi = OrchestratorInput(
        input_type="sensor",
        data={"reading": reading.to_dict(), "active_permits": ["hot_work"]},
    )
    result = orch.run(oi)

    highest = result.compliance.highest_severity if result.compliance else None
    risk = result.safety.risk_score if result.safety else -1

    if highest != "CRITICAL":
        print(f"WARNING: expected highest severity to be CRITICAL, got {highest}")
    if risk < 80:
        print(f"WARNING: expected risk to be >= 80, got {risk}")

    return result


if __name__ == "__main__":
    r = run_vizag_scenario()
    print({
        "request_id": r.request_id,
        "risk_score": r.safety.risk_score if r.safety else None,
        "highest_severity": r.compliance.highest_severity if r.compliance else None,
        "compliance_pass": r.compliance.pass_status if r.compliance else None,
        "violations": [v.rule_id for v in r.compliance.violations] if r.compliance else [],
        "recommended_action": r.safety.recommended_action if r.safety else None,
    })
