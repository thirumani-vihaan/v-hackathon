"""Assessment-confidence engine — how much should an operator trust this risk verdict?

A single risk number hides whether the underlying evidence is strong. Borrowing the
"evidence quality" idea and adapting it honestly to what we can actually compute, this
decomposes trust into three auditable components:

  * coverage      — are all sensor channels reporting physically plausible values, or is
                    a channel out of range (a likely faulty/failed sensor)?
  * decisiveness  — how far are the key signals from their decision thresholds? Readings
                    sitting right on a threshold are ambiguous; readings far from it are
                    unambiguous. This is the signal-margin confidence.
  * freshness     — how recent is the reading? Stale data should lower trust.

overall = 0.40*coverage + 0.35*decisiveness + 0.25*freshness

This lets the UI say "risk 72, but LOW confidence — sensors sit on the threshold, verify"
versus "risk 72, HIGH confidence — act now", a distinction none of a bare score conveys.
Deterministic, offline, explainable.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from schema import SensorReading

W_COVERAGE = 0.40
W_DECISIVENESS = 0.35
W_FRESHNESS = 0.25

# Physically plausible operating ranges; outside => likely sensor fault.
_PLAUSIBLE = {
    "gas_ppm": (0.0, 1000.0),
    "temp_c": (-20.0, 80.0),
    "oxygen_pct": (5.0, 25.0),
    "humidity_pct": (0.0, 100.0),
    "pressure_bar": (0.5, 3.0),
}

# (threshold, scale) for the decisiveness margin per key signal.
_THRESHOLDS = {
    "gas_ppm": (50.0, 50.0),
    "oxygen_pct": (19.5, 3.0),
    "temp_c": (45.0, 15.0),
}

FRESH_MIN = 5.0     # full freshness within 5 minutes
STALE_MIN = 60.0    # zero freshness at/after 60 minutes


def _coverage(reading: SensorReading) -> float:
    ok = 0
    for field, (lo, hi) in _PLAUSIBLE.items():
        val = getattr(reading, field, None)
        if val is not None and lo <= float(val) <= hi:
            ok += 1
    return ok / len(_PLAUSIBLE)


def _decisiveness(reading: SensorReading) -> float:
    margins = []
    for field, (thr, scale) in _THRESHOLDS.items():
        val = float(getattr(reading, field))
        margins.append(min(1.0, abs(val - thr) / scale))
    return sum(margins) / len(margins)


def _freshness(reading: SensorReading, now: Optional[datetime]) -> float:
    now = now or datetime.utcnow()
    try:
        ts = datetime.fromisoformat(reading.timestamp)
    except (ValueError, TypeError):
        return 0.5  # unknown timestamp => neutral
    age_min = abs((now - ts).total_seconds()) / 60.0
    if age_min <= FRESH_MIN:
        return 1.0
    if age_min >= STALE_MIN:
        return 0.0
    return round(1.0 - (age_min - FRESH_MIN) / (STALE_MIN - FRESH_MIN), 3)


def assess_confidence(reading: SensorReading, now: Optional[datetime] = None) -> Dict:
    """Return the confidence breakdown for a reading's risk assessment."""
    coverage = round(_coverage(reading), 3)
    decisiveness = round(_decisiveness(reading), 3)
    freshness = round(_freshness(reading, now), 3)
    overall = round(W_COVERAGE * coverage + W_DECISIVENESS * decisiveness
                    + W_FRESHNESS * freshness, 3)
    label = "high" if overall >= 0.75 else "medium" if overall >= 0.5 else "low"

    notes = []
    if coverage < 1.0:
        notes.append("A sensor channel is out of plausible range — check for a fault.")
    if decisiveness < 0.34:
        notes.append("Signals sit near their thresholds — the verdict is borderline; verify.")
    if freshness < 0.5:
        notes.append("Reading is stale — refresh sensor data before acting.")
    if not notes:
        notes.append("Strong, fresh, unambiguous evidence.")

    return {
        "coverage": coverage,
        "decisiveness": decisiveness,
        "freshness": freshness,
        "confidence": overall,
        "label": label,
        "notes": notes,
    }


if __name__ == "__main__":
    from utils.sensor_simulator import vizag_critical_reading, normal_reading
    for r in (normal_reading(), vizag_critical_reading()):
        c = assess_confidence(r)
        print(f"gas={r.gas_ppm} o2={r.oxygen_pct} -> confidence {c['confidence']} "
              f"({c['label']}) cov={c['coverage']} dec={c['decisiveness']} "
              f"fresh={c['freshness']}")
