"""Pure functions for the live zone map and 'time to critical' estimate.

Kept out of the UI so they are unit-testable and reused by both the map and
the dashboard.
"""
from typing import List, Optional

GREEN = "green"
ORANGE = "orange"
RED = "red"

# Facility zones shown on the map.
ZONES = ("Zone-A-Tank-Farm", "Zone-B-Process", "Zone-C-Confined", "Zone-D-Substation")


def zone_colors(gas_ppm: float, oxygen_pct: float, humidity_pct: float,
                active_permits: List[str] = None) -> dict:
    """Map current sensor context to a color per facility zone.

    Rules (deterministic):
      Zone A Tank Farm : red gas>80, orange gas>50, else green
      Zone B Process   : red if (gas>50 and hot_work) or gas>80, orange gas>50, else green
      Zone C Confined  : red oxygen<18, orange oxygen<19.5, else green
      Zone D Substation: red if electrical and humidity>90,
                         orange if electrical and humidity>85, else green
    """
    permits = set(p.lower() for p in (active_permits or []))
    hot_work = "hot_work" in permits
    electrical = "electrical" in permits

    a = RED if gas_ppm > 80 else ORANGE if gas_ppm > 50 else GREEN
    b = (RED if (gas_ppm > 50 and hot_work) or gas_ppm > 80
         else ORANGE if gas_ppm > 50 else GREEN)
    c = RED if oxygen_pct < 18.0 else ORANGE if oxygen_pct < 19.5 else GREEN
    d = (RED if electrical and humidity_pct > 90
         else ORANGE if electrical and humidity_pct > 85 else GREEN)

    return {
        "Zone-A-Tank-Farm": a,
        "Zone-B-Process": b,
        "Zone-C-Confined": c,
        "Zone-D-Substation": d,
    }


def time_to_critical(history: List[float], threshold: float = 70.0,
                     seconds_per_step: float = 1.0,
                     window: int = 5) -> Optional[float]:
    """Estimate minutes until risk reaches `threshold` via linear extrapolation.

    Returns:
      0.0   if already at/above threshold,
      None  if risk is flat/decreasing (no ETA) or not enough data,
      >0    estimated minutes to reach threshold.
    """
    if not history:
        return None
    last = history[-1]
    if last >= threshold:
        return 0.0
    if len(history) < 2:
        return None

    pts = history[-window:] if len(history) > window else history
    n = len(pts)
    # slope per step via least-squares over the window
    xs = list(range(n))
    mx = sum(xs) / n
    my = sum(pts) / n
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return None
    slope_per_step = sum((xs[i] - mx) * (pts[i] - my) for i in range(n)) / denom
    if slope_per_step <= 1e-9:
        return None  # not rising
    slope_per_min = slope_per_step * (60.0 / max(seconds_per_step, 1e-9))
    if slope_per_min <= 1e-9:
        return None
    minutes = (threshold - last) / slope_per_min
    return round(max(0.0, minutes), 2)


if __name__ == "__main__":
    print(zone_colors(90, 18.5, 95, ["hot_work", "electrical"]))
    print("eta:", time_to_critical([10, 20, 30, 45, 60]))
    print("eta flat:", time_to_critical([20, 20, 20]))
