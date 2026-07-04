"""Graduated continuous compound-risk model for the live UI.

The deterministic rule engine (agents/safety_agent.py) is auditable but discrete — it
jumps at fixed thresholds and ignores factors like temperature or crowding. That is
correct for the compliance/benchmark proof, but it makes the live dashboard feel
unresponsive. This module produces a SMOOTH 0-100 compound-risk index in which every
sensor and permit — and their interactions — contributes continuously, with a
per-factor breakdown so the number is fully explainable.

The rule engine and the single-sensor benchmark are unchanged; this is an additional,
richer view for real-time operation.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Optional

from schema import SensorReading

_HAZARD_PERMITS = ("hot_work", "maintenance", "confined_space", "electrical", "shift_changeover")


def _permits(reading: SensorReading, active: Optional[List[str]]) -> set:
    p = {q.lower() for q in (active or [])}
    if reading.permit_type:
        p.add(reading.permit_type.lower())
    return p


def graduated_risk(reading: SensorReading, active_permits: Optional[List[str]] = None) -> Dict:
    """Return {score, band, recommended_action, contributions:[{factor,points,detail}]}."""
    permits = _permits(reading, active_permits)
    confined = "confined" in (reading.zone or "").lower() or "confined_space" in permits
    ignition = "hot_work" in permits
    gas, oxy, temp, hum, workers = (reading.gas_ppm, reading.oxygen_pct, reading.temp_c,
                                    reading.humidity_pct, reading.worker_count)

    c: List[Dict] = []

    def add(factor, points, detail):
        if points > 0.5:
            c.append({"factor": factor, "points": round(points, 1), "detail": detail})

    add("Gas concentration", min(52.0, gas * 0.5), f"{gas:.0f} ppm combustible/toxic gas")
    if oxy < 20.9:
        add("Oxygen deficiency", min(45.0, (20.9 - oxy) * 9.0), f"oxygen at {oxy:.1f}% (safe ≥ 19.5%)")
    elif oxy > 23.5:
        add("Oxygen enrichment", min(30.0, (oxy - 23.5) * 10.0), f"oxygen-enriched at {oxy:.1f}% (fire risk)")
    if ignition:
        add("Hot work + gas", min(35.0, gas * 0.35), "ignition source amid accumulating gas")
    if confined:
        add("Confined space", min(22.0, gas * 0.14 + max(0.0, 20.9 - oxy) * 3.2),
            "confinement amplifies accumulation & entrapment")
    if "maintenance" in permits and gas > 25:
        add("Maintenance activity", min(12.0, (gas - 25) * 0.3), "intrusive work can release trapped gas")
    if "shift_changeover" in permits and gas > 25:
        add("Shift changeover", 8.0, "handover supervision blind spot")
    if temp > 38:
        add("Thermal stress", min(15.0, (temp - 38) * 1.2), f"{temp:.0f}°C heat / ignition risk")
    if "electrical" in permits and hum > 80:
        add("Electrical + humidity", min(12.0, (hum - 80) * 0.6), f"{hum:.0f}% humidity shock risk")
    if workers > 0:
        add("Worker exposure", min(8.0, workers * 0.8), f"{workers} worker(s) in the zone")

    total = sum(x["points"] for x in c)
    # physical hard floors — acute conditions cannot read low
    if gas >= 100 or oxy < 16.0:
        total = max(total, 88.0)
    if gas > 50 and oxy < 19.5 and confined:
        total = max(total, 80.0)
    score = int(round(min(100.0, total)))

    band = ("CRITICAL" if score >= 80 else "HIGH" if score >= 50
            else "ELEVATED" if score >= 20 else "NOMINAL")
    action = {
        "CRITICAL": "STOP WORK. Evacuate the zone, isolate the source, deploy the emergency team.",
        "HIGH": "Suspend non-essential work. Increase ventilation and continuous monitoring; restrict entry.",
        "ELEVATED": "Heightened caution. Verify PPE, increase monitoring frequency, brief the crew.",
        "NOMINAL": "Conditions nominal. Continue routine monitoring.",
    }[band]
    c.sort(key=lambda x: -x["points"])
    return {"score": score, "band": band, "recommended_action": action, "contributions": c}


def rank_interventions(reading: SensorReading, active_permits: Optional[List[str]] = None) -> Dict:
    """Rank risk-reducing actions against the graduated model (consistent with the score)."""
    permits = list(_permits(reading, active_permits))
    before = graduated_risk(reading, permits)["score"]
    cand: List[Dict] = []

    for p in permits:
        if p not in _HAZARD_PERMITS:
            continue
        remaining = [q for q in permits if q != p]
        r2 = replace(reading, permit_type="general") if (reading.permit_type or "").lower() == p else reading
        cand.append({"action": f"Revoke {p.replace('_', ' ')} permit",
                     "description": f"Cancel the active {p.replace('_', ' ')} permit in {reading.zone}.",
                     "risk_after": graduated_risk(r2, remaining)["score"]})

    vent = replace(reading, gas_ppm=round(reading.gas_ppm * 0.35, 1),
                   oxygen_pct=min(20.9, round(reading.oxygen_pct + 2.0, 2)))
    cand.append({"action": "Increase forced ventilation",
                 "description": f"Deploy forced-air ventilation to dilute gas and restore oxygen in {reading.zone}.",
                 "risk_after": graduated_risk(vent, permits)["score"]})
    purge = replace(reading, gas_ppm=round(min(reading.gas_ppm, 20.0), 1), oxygen_pct=20.9)
    cand.append({"action": "Purge & oxygenate atmosphere",
                 "description": f"Full atmospheric purge and re-test before re-entry in {reading.zone}.",
                 "risk_after": graduated_risk(purge, permits)["score"]})

    for x in cand:
        x["risk_before"] = before
        x["risk_reduction"] = max(0, before - x["risk_after"])
    cand.sort(key=lambda x: (-x["risk_reduction"], x["risk_after"]))
    seen, ranked = set(), []
    for x in cand:
        if x["action"] in seen:
            continue
        seen.add(x["action"]); ranked.append(x)
    recommended = ranked[0] if ranked and ranked[0]["risk_reduction"] > 0 else None
    residual = None
    best = recommended["risk_after"] if recommended else before
    if before >= 80 and best >= 50:
        residual = ("Evacuate the zone immediately and deploy the emergency response team — "
                    "no single control brings this below the critical threshold.")
    return {"risk_before": before, "recommended": recommended, "interventions": ranked,
            "residual_action": residual}


if __name__ == "__main__":
    from utils.sensor_simulator import vizag_critical_reading, normal_reading
    for r, permits in [(normal_reading(), []), (vizag_critical_reading(), ["hot_work"])]:
        g = graduated_risk(r, permits)
        print(f"gas={r.gas_ppm} o2={r.oxygen_pct} -> {g['score']} ({g['band']})")
        for x in g["contributions"]:
            print(f"   +{x['points']} {x['factor']}: {x['detail']}")
