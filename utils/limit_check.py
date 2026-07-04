"""Regulatory-limit utilisation — measured value vs the safe regulatory limit per
parameter, normalised so that >100% always means "in violation" regardless of whether
the limit is an upper bound (gas, temperature, humidity) or a lower bound (oxygen).

Gives the dashboard an instantly legible compliance visual: one bar per parameter, a
red line at 100%. Deterministic, offline; limits trace to the OISD/Factory Act thresholds
already encoded in the compliance rules.
"""
from __future__ import annotations

from typing import Dict, List

from schema import SensorReading

# (attribute, label, unit, limit, direction). direction "upper" => exceeding is bad;
# "lower" => falling below is bad (oxygen deficiency).
_LIMITS = [
    ("gas_ppm", "H\u2082S gas", "ppm", 50.0, "upper"),
    ("oxygen_pct", "Oxygen", "%", 19.5, "lower"),
    ("temp_c", "Temperature", "\u00b0C", 45.0, "upper"),
    ("humidity_pct", "Humidity", "%", 85.0, "upper"),
]


def limit_utilisation(reading: SensorReading) -> List[Dict]:
    """Return per-parameter utilisation vs the regulatory limit.

    Each item: {parameter, measured, limit, unit, direction, pct_of_limit, status}.
    pct_of_limit >= 100 means the safe limit is breached.
    """
    out: List[Dict] = []
    for attr, label, unit, limit, direction in _LIMITS:
        measured = float(getattr(reading, attr))
        if direction == "upper":
            pct = (measured / limit * 100.0) if limit else 0.0
        else:  # lower bound: below the limit is the violation
            pct = (limit / measured * 100.0) if measured else 999.0
        pct = round(pct, 1)
        out.append({
            "parameter": label,
            "measured": round(measured, 1),
            "limit": limit,
            "unit": unit,
            "direction": direction,
            "pct_of_limit": pct,
            "status": "EXCEEDED" if pct >= 100.0 else "OK",
        })
    return out


if __name__ == "__main__":
    from utils.sensor_simulator import vizag_critical_reading
    for row in limit_utilisation(vizag_critical_reading()):
        print(f"{row['parameter']:12} {row['measured']}{row['unit']} "
              f"limit {row['limit']}{row['unit']} -> {row['pct_of_limit']}% "
              f"[{row['status']}]")
