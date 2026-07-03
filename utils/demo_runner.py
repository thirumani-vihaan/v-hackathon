"""demo_runner: a two-phase live scenario that feels real, with an audit trace.

Phase 1 (safe):        nominal readings, risk stays low (< 50).
Phase 2 (escalation):  gas rises second-by-second and the crew switches to a
                       hot_work permit, driving risk up to a critical peak (>= 70,
                       typically 100).

run_phases() returns a tuple (safe_results, escalated_results) of
OrchestratorResult objects and writes data/demo_trace.jsonl with one JSON object
per simulated second. Fast by default (no sleeps) so tests stay quick; pass
realtime=True for a paced live demo.
"""
import os
import sys
import json
import time
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from schema import OrchestratorInput, SensorReading  # noqa: E402
from agents.orchestrator import Orchestrator  # noqa: E402

_DEFAULT_TRACE = os.path.join(_ROOT, "data", "demo_trace.jsonl")
_ZONE = "Zone-A-Tank-Farm"


def _lerp(a: float, b: float, frac: float) -> float:
    return a + (b - a) * frac


def _safe_readings(seconds: int):
    out = []
    for i in range(seconds):
        frac = i / max(seconds - 1, 1)
        out.append(SensorReading(
            gas_ppm=round(_lerp(4, 16, frac), 1),
            temp_c=round(_lerp(30, 33, frac), 1),
            oxygen_pct=20.9,
            humidity_pct=50.0,
            permit_type="general",
            worker_count=2,
            zone=_ZONE,
            timestamp=datetime.utcnow().isoformat(),
            pressure_bar=1.013,
            rescue_team_present=True,
        ))
    return out


def _escalated_readings(seconds: int):
    """Gas climbs and O2 is displaced; a hot_work permit is opened mid-phase."""
    out = []
    for i in range(seconds):
        frac = i / max(seconds - 1, 1)
        out.append(SensorReading(
            gas_ppm=round(_lerp(35, 130, frac), 1),
            temp_c=round(_lerp(34, 45, frac), 1),
            oxygen_pct=round(_lerp(20.8, 18.0, frac), 2),
            humidity_pct=60.0,
            permit_type="hot_work" if frac >= 0.5 else "general",
            worker_count=3,
            zone=_ZONE,
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

    def _trace_record(self, phase, reading, permits, result):
        risk = result.safety.risk_score if result.safety else None
        sev = result.compliance.highest_severity if result.compliance else None
        n_viol = len(result.compliance.violations) if result.compliance else 0
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "phase": phase,
            "request_id": result.request_id,
            "zone": reading.zone,
            "gas_ppm": reading.gas_ppm,
            "oxygen_pct": reading.oxygen_pct,
            "active_permits": list(permits),
            "risk_score": risk,
            "highest_severity": sev,
            "violations_count": n_viol,
        }

    def run_phases(self, seconds: int = 10, realtime: bool = False,
                   write_trace: bool = True, trace_path: str = _DEFAULT_TRACE):
        """Run both phases; return (safe_results, escalated_results)."""
        seconds = max(2, int(seconds))
        safe_results, escalated_results = [], []
        fh = None
        if write_trace:
            try:
                os.makedirs(os.path.dirname(trace_path) or ".", exist_ok=True)
                fh = open(trace_path, "w", encoding="utf-8")
            except Exception:
                fh = None

        try:
            for reading in _safe_readings(seconds):
                permits = []
                res = self._run_reading(reading, permits)
                safe_results.append(res)
                if fh:
                    fh.write(json.dumps(
                        self._trace_record("safe", reading, permits, res)) + "\n")
                    fh.flush()
                if realtime:
                    time.sleep(1)

            for reading in _escalated_readings(seconds):
                permits = ["hot_work"] if reading.permit_type == "hot_work" else []
                res = self._run_reading(reading, permits)
                escalated_results.append(res)
                if fh:
                    fh.write(json.dumps(
                        self._trace_record("escalation", reading, permits, res)) + "\n")
                    fh.flush()
                if realtime:
                    time.sleep(1)
        finally:
            if fh:
                fh.close()

        return (safe_results, escalated_results)

    def run_and_export(self, seconds: int = 10, realtime: bool = False,
                       trace_path: str = _DEFAULT_TRACE) -> str:
        """Run the demo and return the path to the written trace file."""
        self.run_phases(seconds=seconds, realtime=realtime,
                        write_trace=True, trace_path=trace_path)
        return trace_path


if __name__ == "__main__":
    safe, escalated = DemoRunner().run_phases(seconds=10)
    print("safe risks:", [r.safety.risk_score for r in safe])
    print("escalated risks:", [r.safety.risk_score for r in escalated])
    print("trace at:", _DEFAULT_TRACE)
