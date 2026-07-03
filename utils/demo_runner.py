"""demo_runner: two-phase scenario driver for demos and acceptance.

Phase 1 (safe): nominal readings -> low risk (< 40).
Phase 2 (escalated): ramping readings -> high risk (>= 70 at the peak).

run_phases() returns a dict with 'safe_results' and 'escalated_results', each a
list of OrchestratorResult objects.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from schema import OrchestratorInput  # noqa: E402
from agents.orchestrator import Orchestrator  # noqa: E402
from utils.sensor_simulator import (  # noqa: E402
    normal_reading, vizag_critical_reading, SensorReading,
)
from datetime import datetime  # noqa: E402


def _safe_readings(n: int = 3):
    out = []
    for i in range(n):
        out.append(SensorReading(
            gas_ppm=round(4 + i * 2, 1),
            temp_c=round(30 + i, 1),
            oxygen_pct=20.9,
            humidity_pct=50.0,
            permit_type="general",
            worker_count=2,
            zone="Zone-A-Tank-Farm",
            timestamp=datetime.utcnow().isoformat(),
            pressure_bar=1.013,
            rescue_team_present=True,
        ))
    return out


def _escalated_readings(n: int = 3):
    out = []
    for i in range(n):
        frac = (i + 1) / n
        out.append(SensorReading(
            gas_ppm=round(55 + frac * 70, 1),
            temp_c=round(38 + frac * 6, 1),
            oxygen_pct=round(19.6 - frac * 1.6, 2),
            humidity_pct=60.0,
            permit_type="hot_work",
            worker_count=3,
            zone="Zone-A-Tank-Farm",
            timestamp=datetime.utcnow().isoformat(),
            pressure_bar=1.02,
            rescue_team_present=True,
        ))
    return out


class DemoRunner:
    def __init__(self, orchestrator: Orchestrator = None):
        self.orchestrator = orchestrator or Orchestrator()

    def _run_reading(self, reading, permits):
        oi = OrchestratorInput(
            input_type="sensor",
            data={"reading": reading.to_dict(), "active_permits": permits},
        )
        return self.orchestrator.run(oi)

    def run_phases(self) -> dict:
        safe_results = [self._run_reading(r, []) for r in _safe_readings(3)]
        escalated_results = [self._run_reading(r, ["hot_work"])
                             for r in _escalated_readings(3)]
        return {
            "safe_results": safe_results,
            "escalated_results": escalated_results,
        }


if __name__ == "__main__":
    res = DemoRunner().run_phases()
    print("safe risks:", [r.safety.risk_score for r in res["safe_results"]])
    print("escalated risks:", [r.safety.risk_score for r in res["escalated_results"]])
