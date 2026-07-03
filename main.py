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


def run_vizag_scenario() -> dict:
    reading = vizag_critical_reading()
    orch = Orchestrator()
    oi = OrchestratorInput(
        input_type="sensor",
        data={"reading": reading.to_dict(), "active_permits": ["hot_work"]},
    )
    result = orch.run(oi)

    highest = result.compliance.highest_severity if result.compliance else None
    risk = result.safety.risk_score if result.safety else -1

    assert highest == "CRITICAL", f"expected CRITICAL, got {highest}"
    assert risk >= 80, f"expected risk >= 80, got {risk}"

    summary = {
        "request_id": result.request_id,
        "zone": reading.zone,
        "risk_score": risk,
        "highest_severity": highest,
        "compliance_pass": result.compliance.pass_status if result.compliance else None,
        "violations": [v.rule_id for v in result.compliance.violations]
        if result.compliance else [],
        "recommended_action": result.safety.recommended_action
        if result.safety else None,
    }
    return summary


if __name__ == "__main__":
    print(run_vizag_scenario())
