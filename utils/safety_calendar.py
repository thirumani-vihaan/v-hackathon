"""Seasonal industrial-safety calendar (deterministic, offline).

Maps the Indian calendar's seasons
(summer / monsoon / post-monsoon / winter) to the process-safety hazards that
spike in each, plus a daily shift-risk note. No LLM, no network.
"""
from datetime import datetime
from typing import Dict, List, Optional

# Month (1-12) -> season label tuned to Indian industrial conditions.
_SEASON = {
    1: "winter", 2: "winter", 3: "summer", 4: "summer", 5: "summer",
    6: "monsoon", 7: "monsoon", 8: "monsoon", 9: "monsoon",
    10: "post_monsoon", 11: "post_monsoon", 12: "winter",
}

SEASONAL_ADVISORIES: Dict[str, List[str]] = {
    "summer": [
        "Heat stress: enforce work-rest cycles, hydration stations, WBGT monitoring.",
        "Flammable vapour: rising temperatures increase tank breathing losses — watch %LEL.",
        "Static & spontaneous ignition risk elevated in coke/sulphur handling.",
    ],
    "monsoon": [
        "Electrical safety: water ingress raises earth-fault/shock risk — check ELCB/RCD.",
        "Slips & falls: wet walkways and scaffolds — inspect anti-slip and harnesses.",
        "Confined spaces: rainwater ingress can displace oxygen — re-test before entry.",
        "Lightning: suspend crane/flare/tank-top work during storms.",
    ],
    "post_monsoon": [
        "Corrosion inspection: post-monsoon pipe/structure integrity checks.",
        "Gas accumulation: stagnant humid air in low points — verify ventilation.",
    ],
    "winter": [
        "Low visibility/fog: reduce vehicle-movement speed, add hazard lighting.",
        "Gas pooling: cold dense gas settles in pits/trenches — extra LEL sweeps.",
        "Cold-start brittleness: check pressure-vessel min design metal temperature.",
    ],
}


def season_for_month(month: int) -> str:
    return _SEASON.get(int(month), "summer")


def advisories_for(month: Optional[int] = None) -> Dict[str, object]:
    """Return the season label and its hazard advisories for a given month."""
    m = month or datetime.now().month
    season = season_for_month(m)
    return {"month": m, "season": season,
            "advisories": SEASONAL_ADVISORIES[season]}


def upcoming(months: int = 3, start_month: Optional[int] = None) -> List[Dict]:
    """Advisories for the next `months` months (wraps across year)."""
    start = start_month or datetime.now().month
    out = []
    for i in range(months):
        mm = ((start - 1 + i) % 12) + 1
        out.append(advisories_for(mm))
    return out


def shift_note(hour: Optional[int] = None) -> str:
    """Shift-specific risk reminder based on hour of day (0-23)."""
    h = datetime.now().hour if hour is None else int(hour)
    if 6 <= h < 14:
        return "Day shift: peak hot-work/permit activity — supervisor sign-off required."
    if 14 <= h < 22:
        return "Evening shift: fading light — verify area lighting before elevated work."
    return "Night shift: reduced staffing & alertness — buddy system for confined entry."


def is_shift_changeover(timestamp=None, window_min: int = 30) -> bool:
    """True if `timestamp` falls within `window_min` minutes of a shift boundary.

    Shifts change at 06:00, 14:00 and 22:00 (the day/evening/night handovers used by
    shift_note). Changeover windows are documented supervision blind spots: outgoing and
    incoming crews overlap, permits are handed off, and hazardous conditions can go
    unwatched — a pattern PS1 calls out explicitly.
    """
    if timestamp is None:
        dt = datetime.now()
    elif isinstance(timestamp, str):
        try:
            dt = datetime.fromisoformat(timestamp)
        except ValueError:
            return False
    else:
        dt = timestamp
    minutes = dt.hour * 60 + dt.minute
    for boundary in (6 * 60, 14 * 60, 22 * 60):
        diff = abs(minutes - boundary)
        diff = min(diff, 24 * 60 - diff)  # wrap around midnight
        if diff <= window_min:
            return True
    return False


if __name__ == "__main__":
    import json
    print(json.dumps(advisories_for(), indent=2))
    print(shift_note())
