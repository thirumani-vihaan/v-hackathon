"""Counterfactual intervention engine — "what single action most reduces risk right now?"

Given the current sensor state, this simulates a set of concrete safety interventions
(revoke a permit, increase ventilation, purge/oxygenate, halt hot work) by re-scoring the
compound risk under each counterfactual, then ranks them by how much risk they remove.

This turns a risk *number* into an actionable *decision*: not "risk is 100", but "revoke
the hot-work permit -> risk 100 -> 20". Deterministic, offline, and explainable — it reuses
the exact SafetyAgent compound scoring, so every recommendation is auditable.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Optional

from schema import SensorReading, SensorInput
from agents.safety_agent import SafetyAgent

_HAZARD_PERMITS = ("hot_work", "maintenance", "confined_space", "electrical",
                   "shift_changeover")

_safety = SafetyAgent()


def _score(reading: SensorReading, permits: List[str]) -> int:
    return _safety.assess(SensorInput(reading=reading, active_permits=list(permits))).risk_score


def _permits_with(reading: SensorReading, active_permits: List[str]) -> List[str]:
    permits = list(active_permits or [])
    if reading.permit_type and reading.permit_type not in permits:
        permits.append(reading.permit_type)
    return permits


def rank_interventions(reading: SensorReading, active_permits: Optional[List[str]] = None
                       ) -> Dict:
    """Return the ranked list of risk-reducing interventions for the current state.

    Result: {risk_before, recommended, interventions: [{action, description,
             risk_before, risk_after, risk_reduction}], residual_action}
    """
    permits = _permits_with(reading, active_permits)
    risk_before = _score(reading, permits)

    candidates: List[Dict] = []

    # 1) Revoke each active hazardous permit.
    for p in permits:
        if p not in _HAZARD_PERMITS:
            continue
        remaining = [q for q in permits if q != p]
        r2 = reading
        if reading.permit_type == p:
            r2 = replace(reading, permit_type="general")
        after = _score(r2, remaining)
        candidates.append({
            "action": f"Revoke {p.replace('_', ' ')} permit",
            "description": (f"Cancel the active {p.replace('_', ' ')} permit in "
                            f"{reading.zone}."),
            "risk_after": after,
        })

    # 2) Increase forced ventilation (dilutes gas, restores oxygen).
    vent = replace(reading, gas_ppm=round(reading.gas_ppm * 0.35, 1),
                   oxygen_pct=min(20.9, round(reading.oxygen_pct + 2.0, 2)))
    candidates.append({
        "action": "Increase forced ventilation",
        "description": (f"Deploy forced-air ventilation to dilute gas and restore "
                        f"oxygen in {reading.zone}."),
        "risk_after": _score(vent, permits),
    })

    # 3) Purge / oxygenate to a safe atmosphere (aggressive ventilation).
    purge = replace(reading, gas_ppm=round(min(reading.gas_ppm, 20.0), 1),
                    oxygen_pct=20.9)
    candidates.append({
        "action": "Purge & oxygenate atmosphere",
        "description": f"Full atmospheric purge and re-test before re-entry in {reading.zone}.",
        "risk_after": _score(purge, permits),
    })

    for c in candidates:
        c["risk_before"] = risk_before
        c["risk_reduction"] = max(0, risk_before - c["risk_after"])

    # Rank by risk removed (desc), then by lowest residual risk.
    candidates.sort(key=lambda c: (-c["risk_reduction"], c["risk_after"]))

    # De-duplicate identical actions.
    seen = set()
    ranked = []
    for c in candidates:
        if c["action"] in seen:
            continue
        seen.add(c["action"])
        ranked.append(c)

    recommended = ranked[0] if ranked and ranked[0]["risk_reduction"] > 0 else None

    # If risk stays critical even after the best single action, escalate to evacuation.
    residual_action = None
    best_residual = recommended["risk_after"] if recommended else risk_before
    if risk_before >= 80 and best_residual >= 50:
        residual_action = ("Evacuate the zone immediately and deploy the emergency "
                           "response team — no single control brings this below the "
                           "critical threshold.")

    return {
        "risk_before": risk_before,
        "recommended": recommended,
        "interventions": ranked,
        "residual_action": residual_action,
    }


if __name__ == "__main__":
    from utils.sensor_simulator import vizag_critical_reading
    r = vizag_critical_reading()
    out = rank_interventions(r, ["hot_work"])
    print("risk_before:", out["risk_before"])
    for c in out["interventions"]:
        print(f"  {c['action']}: {c['risk_before']} -> {c['risk_after']} "
              f"(-{c['risk_reduction']})")
    if out["recommended"]:
        print("RECOMMENDED:", out["recommended"]["action"])
    if out["residual_action"]:
        print("RESIDUAL:", out["residual_action"])
