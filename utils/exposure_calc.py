"""Deterministic industrial-hygiene calculator (no LLM, no network).

Analogue of AgriBloom's fertilizer/NPK calculator, but for confined-space and
process-safety engineering: OSHA PEL/STEL exposure ratios, %LEL for flammables,
required dilution ventilation (CFM / air-changes) and a conservative evacuation
radius. All numbers come from published exposure limits and gas-law math.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# OSHA/NIOSH exposure limits (ppm) and lower flammable limit (vol %).
# Values are standard published references for common industrial gases.
GASES: Dict[str, Dict[str, float]] = {
    "h2s": {"name": "Hydrogen Sulfide", "pel": 10, "stel": 15, "idlh": 100, "lel_pct": 4.0},
    "co": {"name": "Carbon Monoxide", "pel": 35, "stel": 200, "idlh": 1200, "lel_pct": 12.5},
    "ch4": {"name": "Methane", "pel": 1000, "stel": 0, "idlh": 0, "lel_pct": 5.0},
    "nh3": {"name": "Ammonia", "pel": 25, "stel": 35, "idlh": 300, "lel_pct": 15.0},
    "so2": {"name": "Sulfur Dioxide", "pel": 2, "stel": 5, "idlh": 100, "lel_pct": 0},
    "cl2": {"name": "Chlorine", "pel": 0.5, "stel": 1, "idlh": 10, "lel_pct": 0},
    "lpg": {"name": "LPG / Propane", "pel": 1000, "stel": 0, "idlh": 2100, "lel_pct": 2.1},
    "benzene": {"name": "Benzene", "pel": 1, "stel": 5, "idlh": 500, "lel_pct": 1.2},
}

CFM_PER_M3 = 35.3147  # 1 m^3 = 35.3147 ft^3


@dataclass
class ExposureAssessment:
    gas: str
    ppm: float
    pel: float
    stel: float
    pel_ratio: float
    stel_ratio: float
    lel_pct_of_limit: float
    status: str
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def assess_exposure(gas_key: str, ppm: float) -> ExposureAssessment:
    """Compare a measured ppm to PEL/STEL/IDLH and %LEL for the given gas."""
    g = GASES.get(gas_key.lower())
    if g is None:
        raise ValueError(f"unknown gas '{gas_key}'; known: {sorted(GASES)}")
    pel = g["pel"]
    stel = g["stel"] or pel
    idlh = g["idlh"]
    lel_ppm = g["lel_pct"] * 10000.0 if g["lel_pct"] else 0.0  # 1 vol% = 10000 ppm

    pel_ratio = round(ppm / pel, 3) if pel else 0.0
    stel_ratio = round(ppm / stel, 3) if stel else 0.0
    lel_of_limit = round(ppm / lel_ppm * 100.0, 2) if lel_ppm else 0.0

    notes: List[str] = []
    if idlh and ppm >= idlh:
        status = "IDLH"
        notes.append("Immediately Dangerous to Life/Health — evacuate, SCBA only.")
    elif lel_ppm and lel_of_limit >= 10:
        status = "FLAMMABLE"
        notes.append(">=10% LEL — remove ignition sources, no hot work.")
    elif pel and ppm > stel:
        status = "OVER_STEL"
        notes.append("Above short-term limit — limit exposure to <15 min.")
    elif pel and ppm > pel:
        status = "OVER_PEL"
        notes.append("Above 8-hr permissible limit — ventilate / respirators.")
    else:
        status = "OK"
        notes.append("Within permissible limits.")
    return ExposureAssessment(g["name"], float(ppm), pel, stel, pel_ratio,
                              stel_ratio, lel_of_limit, status, notes)


def lel_percent(gas_key: str, ppm: float) -> float:
    """Return the reading as a percentage of the gas's Lower Explosive Limit."""
    g = GASES.get(gas_key.lower())
    if not g or not g["lel_pct"]:
        return 0.0
    return round(ppm / (g["lel_pct"] * 10000.0) * 100.0, 2)


def ventilation_cfm(volume_m3: float, air_changes_per_hour: float) -> float:
    """Airflow (CFM) needed to achieve target air changes per hour."""
    if volume_m3 <= 0 or air_changes_per_hour <= 0:
        return 0.0
    m3_per_min = volume_m3 * air_changes_per_hour / 60.0
    return round(m3_per_min * CFM_PER_M3, 1)


def purge_time_min(volume_m3: float, cfm_available: float,
                   target_air_changes: float = 5.0) -> float:
    """Minutes to purge a space given available airflow (CFM)."""
    if cfm_available <= 0 or volume_m3 <= 0:
        return float("inf")
    m3_per_min = cfm_available / CFM_PER_M3
    return round(volume_m3 * target_air_changes / m3_per_min, 1)


def evacuation_radius_m(gas_key: str, ppm: float) -> int:
    """Conservative downwind evacuation radius (m) scaled by hazard severity."""
    a = assess_exposure(gas_key, ppm)
    base = {"IDLH": 300, "FLAMMABLE": 250, "OVER_STEL": 150,
            "OVER_PEL": 75, "OK": 0}[a.status]
    if a.pel_ratio > 1:
        base += min(200, int(a.pel_ratio * 25))
    return int(round(base / 25.0) * 25)  # round to nearest 25 m


def full_report(gas_key: str, ppm: float, volume_m3: float = 100.0,
                target_ach: float = 12.0) -> dict:
    """One-call summary bundling exposure + LEL + ventilation + evac radius."""
    a = assess_exposure(gas_key, ppm)
    return {
        "exposure": a.to_dict(),
        "lel_percent": lel_percent(gas_key, ppm),
        "recommended_ventilation_cfm": ventilation_cfm(volume_m3, target_ach),
        "purge_time_min_at_recommended": purge_time_min(
            volume_m3, ventilation_cfm(volume_m3, target_ach), 5.0),
        "evacuation_radius_m": evacuation_radius_m(gas_key, ppm),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(full_report("h2s", 120, 80, 12), indent=2))
