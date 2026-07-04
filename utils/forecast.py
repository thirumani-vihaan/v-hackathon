"""Predictive lead-time forecasting.

PS1 demands "prediction lead time before incident threshold" and interventions
"hours before they become critical". A threshold alarm is reactive by definition — it
fires when a value has ALREADY crossed. This module projects the recent trajectory of a
signal (gas, oxygen) forward and estimates the time until it crosses a physical threshold,
so the system can act while there is still time to evacuate.

Method: least-squares slope over a trailing window (robust to single-sample noise),
then linear extrapolation from the latest value to the target threshold. Deterministic,
offline, and explainable — a regulator can audit exactly why an alert fired.
"""
from __future__ import annotations

from typing import List, Optional


def _lsq_slope_per_step(values: List[float]) -> Optional[float]:
    """Least-squares slope (units per step) over the given values, or None."""
    n = len(values)
    if n < 2:
        return None
    xs = list(range(n))
    mx = sum(xs) / n
    my = sum(values) / n
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return None
    return sum((xs[i] - mx) * (values[i] - my) for i in range(n)) / denom


def minutes_to_threshold(history: List[float], threshold: float,
                         seconds_per_step: float = 60.0, window: int = 6,
                         rising: bool = True) -> Optional[float]:
    """Estimate minutes until `history` reaches `threshold` by linear extrapolation.

    Returns:
      0.0  if the latest value is already past the threshold (in the danger direction),
      >0   estimated minutes to cross,
      None if not enough data or the trend is not moving toward the threshold.

    `rising=True`  -> threshold is an upper limit (e.g. gas ppm approaching IDLH).
    `rising=False` -> threshold is a lower limit (e.g. oxygen dropping toward asphyxia).
    """
    if not history:
        return None
    last = history[-1]
    if (rising and last >= threshold) or (not rising and last <= threshold):
        return 0.0
    pts = history[-window:] if len(history) > window else history
    slope = _lsq_slope_per_step(pts)
    if slope is None:
        return None
    slope_per_min = slope * (60.0 / max(seconds_per_step, 1e-9))
    if rising:
        if slope_per_min <= 1e-9:      # flat or falling: not approaching an upper limit
            return None
        minutes = (threshold - last) / slope_per_min
    else:
        if slope_per_min >= -1e-9:     # flat or rising: not approaching a lower limit
            return None
        minutes = (threshold - last) / slope_per_min  # both negative -> positive minutes
    return round(max(0.0, minutes), 2)


def forecast_summary(gas_history: List[float], oxygen_history: List[float],
                     gas_idlh: float = 100.0, gas_danger: float = 60.0,
                     o2_asphyxia: float = 16.0, seconds_per_step: float = 60.0,
                     window: int = 6) -> dict:
    """Human/UI-ready forecast bundle for the current trajectory."""
    return {
        "minutes_to_gas_danger": minutes_to_threshold(
            gas_history, gas_danger, seconds_per_step, window, rising=True),
        "minutes_to_gas_idlh": minutes_to_threshold(
            gas_history, gas_idlh, seconds_per_step, window, rising=True),
        "minutes_to_oxygen_asphyxia": minutes_to_threshold(
            oxygen_history, o2_asphyxia, seconds_per_step, window, rising=False),
    }


if __name__ == "__main__":
    gas = [10, 18, 27, 34, 41, 49]
    print("gas->60 in", minutes_to_threshold(gas, 60), "min")
    print("gas->100 in", minutes_to_threshold(gas, 100), "min")
    print("flat:", minutes_to_threshold([20, 20, 20], 60))
    print(forecast_summary(gas, [20.9, 20.6, 20.2, 19.8, 19.3, 18.9]))
