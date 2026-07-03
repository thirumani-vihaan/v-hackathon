"""Emergency response directory + nearest-facility finder (deterministic).

Analogue of AgriBloom's helpline & KVK finder, adapted to an industrial estate:
a 24x7 helpline banner, an emergency contact directory, and a haversine-based
"nearest response facility" finder that ranks hospitals / fire / mutual-aid
centres by distance from a given plant zone. Offline, no LLM.
"""
import math
from typing import Dict, List, Optional, Tuple

# 24x7 national/industrial helplines (India).
HELPLINES: List[Dict[str, str]] = [
    {"name": "National Emergency", "number": "112", "hours": "24x7"},
    {"name": "Fire & Rescue", "number": "101", "hours": "24x7"},
    {"name": "Ambulance", "number": "108", "hours": "24x7"},
    {"name": "NDMA Disaster Helpline", "number": "1078", "hours": "24x7"},
    {"name": "PESO / Explosives Control", "number": "1906 (gas leak)", "hours": "24x7"},
]

# On-site / mutual-aid contact directory.
CONTACTS: List[Dict[str, str]] = [
    {"role": "CISF Control Room", "contact": "+91-891-2XX-100"},
    {"role": "Plant Fire Station", "contact": "+91-891-2XX-101"},
    {"role": "Occupational Health Centre", "contact": "+91-891-2XX-108"},
    {"role": "Safety Officer (on-call)", "contact": "+91-891-2XX-247"},
    {"role": "District Emergency Ops", "contact": "+91-891-2XX-112"},
]

# Zone reference coordinates (matches the UI plant layout, Visakhapatnam).
ZONE_COORDS: Dict[str, Tuple[float, float]] = {
    "Zone-A-Tank-Farm": (17.6868, 83.2185),
    "Zone-B-Process": (17.6890, 83.2210),
    "Zone-C-Confined": (17.6850, 83.2160),
    "Zone-D-Substation": (17.6900, 83.2150),
}

# Nearby emergency-response facilities (name, type, lat, lon).
FACILITIES: List[Dict[str, object]] = [
    {"name": "KGH Government Hospital", "type": "Hospital", "lat": 17.7100, "lon": 83.3020},
    {"name": "Seven Hills Hospital", "type": "Hospital (Trauma)", "lat": 17.7380, "lon": 83.3140},
    {"name": "Visakha Steel Plant Fire Stn", "type": "Fire / Mutual-Aid", "lat": 17.6300, "lon": 83.1900},
    {"name": "HPCL Refinery Mutual-Aid", "type": "Mutual-Aid (HAZMAT)", "lat": 17.6750, "lon": 83.2050},
    {"name": "Gajuwaka Fire Station", "type": "Fire & Rescue", "lat": 17.6820, "lon": 83.2010},
    {"name": "District Disaster Cell", "type": "Command", "lat": 17.7040, "lon": 83.2980},
]


def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Great-circle distance in km between two (lat, lon) points."""
    R = 6371.0
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return round(2 * R * math.asin(math.sqrt(h)), 2)


def nearest_facilities(zone: str, top_k: int = 3,
                       facility_type: Optional[str] = None) -> List[Dict]:
    """Return the closest response facilities to a zone, ranked by distance."""
    origin = ZONE_COORDS.get(zone)
    if origin is None:
        origin = next(iter(ZONE_COORDS.values()))
    items = FACILITIES
    if facility_type:
        items = [f for f in items if facility_type.lower() in str(f["type"]).lower()]
    ranked = []
    for f in items:
        d = haversine_km(origin, (f["lat"], f["lon"]))
        ranked.append({**f, "distance_km": d})
    ranked.sort(key=lambda x: x["distance_km"])
    return ranked[:top_k]


def helpline_banner() -> str:
    """One-line helpline banner string for prominent display."""
    parts = [f"{h['name']}: {h['number']}" for h in HELPLINES[:3]]
    return "24x7 EMERGENCY  |  " + "   ".join(parts)


if __name__ == "__main__":
    import json
    print(helpline_banner())
    print(json.dumps(nearest_facilities("Zone-C-Confined"), indent=2))
