"""Single-sensor baseline detector — the status-quo foil for the benchmark.

This models how conventional plants actually run today (FICCI 2024: >60% of large
facilities rely on manual handoffs between independent digital safety tools): each
sensor alarms on ITS OWN instantaneous threshold, with no fusion of permits, spatial
context, or cross-signal trends.

Two honest profiles are provided so the comparison cannot be dismissed as a strawman:

  * "high_alarm"  — evacuation-grade setpoints tuned to AVOID nuisance trips in a
                    process area where moderate gas is routine (H2S high alarm at
                    IDLH 100 ppm, O2 low alarm 19.5%, temp high 55 C). Realistic for
                    coke-oven / tank-farm operations. Consequence: low false alarms,
                    but BLIND to sub-threshold lethal conjunctions.
  * "low_alarm"   — sensitive setpoints (H2S 15 ppm ~ STEL, O2 19.5%). Catches more,
                    but fires constantly on benign transients -> alarm fatigue, the
                    documented failure mode where operators habituate and ignore the
                    one alarm that mattered.

The benchmark reports BOTH profiles against the compound engine to show the real
trade-off single sensors force: miss incidents (high_alarm) OR drown operators in
false alarms (low_alarm). The compound engine escapes the trade-off using context.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from schema import SensorReading

PROFILES: Dict[str, Dict[str, float]] = {
    "high_alarm": {"gas_ppm": 100.0, "oxygen_pct": 19.5, "temp_c": 55.0},
    "low_alarm": {"gas_ppm": 15.0, "oxygen_pct": 19.5, "temp_c": 45.0},
}


def single_sensor_fires(reading: SensorReading, profile: str = "high_alarm") -> bool:
    """True if ANY individual sensor crosses its own setpoint (no context, no fusion)."""
    sp = PROFILES[profile]
    return (reading.gas_ppm >= sp["gas_ppm"]
            or reading.oxygen_pct < sp["oxygen_pct"]
            or reading.temp_c >= sp["temp_c"])


def detect_step(readings: List[SensorReading], profile: str = "high_alarm"
                ) -> Optional[int]:
    """First step index at which the single-sensor baseline alarms, else None."""
    for i, r in enumerate(readings):
        if single_sensor_fires(r, profile):
            return i
    return None


if __name__ == "__main__":
    from utils.scenario_generator import build_dataset, DEFAULT_MIX
    ds = build_dataset()
    for prof in ("high_alarm", "low_alarm"):
        fired = sum(1 for s in ds if detect_step(s["readings"], prof) is not None)
        print(f"{prof}: baseline fired on {fired}/{len(ds)} scenarios")
