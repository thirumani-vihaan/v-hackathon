"""Sensor simulator: produce SensorReading objects for scenarios/tests."""
import random
from datetime import datetime

from schema import SensorReading

ZONES = ["Zone-A-Tank-Farm", "Zone-B-Process", "Zone-C-Confined", "Zone-D-Substation"]
PERMIT_TYPES = ["hot_work", "confined_space", "electrical", "excavation", "cold_work",
                "general", "working_at_height"]


def generate_sensor_reading(scenario: str = "normal") -> dict:
    """Return a scenario-shaped SensorReading as a dict.

    This is a simulator helper (not an agent method). The canonical shape is still
    the schema dataclass: we build a SensorReading and serialize via to_dict(),
    so the returned dict always maps cleanly back to SensorReading(**d).

    Supported scenarios: 'normal', 'gas_spike', 'confined_space', 'electrical'.
    """
    ts = datetime.utcnow().isoformat()
    if scenario == "gas_spike":
        reading = SensorReading(
            gas_ppm=round(random.uniform(85, 130), 1),
            temp_c=round(random.uniform(28, 38), 1),
            oxygen_pct=20.9,
            humidity_pct=55.0,
            permit_type="hot_work",
            worker_count=random.randint(1, 4),
            zone="Zone-B-Process",
            timestamp=ts,
        )
    elif scenario == "confined_space":
        reading = SensorReading(
            gas_ppm=round(random.uniform(5, 20), 1),
            temp_c=round(random.uniform(24, 32), 1),
            oxygen_pct=round(random.uniform(17.0, 19.3), 2),
            humidity_pct=60.0,
            permit_type="confined_space",
            worker_count=random.randint(1, 2),
            zone="Zone-C-Confined",
            timestamp=ts,
            rescue_team_present=True,
        )
    elif scenario == "electrical":
        reading = SensorReading(
            gas_ppm=round(random.uniform(5, 20), 1),
            temp_c=round(random.uniform(24, 32), 1),
            oxygen_pct=20.9,
            humidity_pct=round(random.uniform(86, 97), 1),
            permit_type="electrical",
            worker_count=random.randint(1, 3),
            zone="Zone-D-Substation",
            timestamp=ts,
        )
    else:  # "normal" (default)
        reading = SensorReading(
            gas_ppm=round(random.uniform(10, 35), 1),
            temp_c=round(random.uniform(24, 34), 1),
            oxygen_pct=round(random.uniform(20.5, 21.0), 2),
            humidity_pct=round(random.uniform(40, 60), 1),
            permit_type="inspection",
            worker_count=random.randint(1, 3),
            zone="Zone-A-Tank-Farm",
            timestamp=ts,
        )
    return reading.to_dict()


def normal_reading(zone: str = "Zone-A-Tank-Farm") -> SensorReading:
    """A safe, nominal reading (no rules should fire)."""
    return SensorReading(
        gas_ppm=5.0,
        temp_c=32.0,
        oxygen_pct=20.9,
        humidity_pct=55.0,
        permit_type="general",
        worker_count=2,
        zone=zone,
        timestamp=datetime.utcnow().isoformat(),
        pressure_bar=1.013,
        rescue_team_present=True,
    )


def vizag_critical_reading() -> SensorReading:
    """Recreates a Vizag-style gas-leak emergency: high gas + oxygen displacement
    during hot work. Should produce CRITICAL compliance and risk_score >= 80."""
    return SensorReading(
        gas_ppm=120.0,
        temp_c=41.0,
        oxygen_pct=18.4,
        humidity_pct=70.0,
        permit_type="hot_work",
        worker_count=4,
        zone="Zone-A-Tank-Farm",
        timestamp=datetime.utcnow().isoformat(),
        pressure_bar=1.02,
        rescue_team_present=True,
    )


def escalating_readings(n: int = 4) -> list:
    """A ramp from safe to critical, useful for demo phase validation."""
    out = []
    for i in range(n):
        frac = i / max(1, n - 1)
        out.append(SensorReading(
            gas_ppm=round(5 + frac * 120, 1),
            temp_c=round(32 + frac * 12, 1),
            oxygen_pct=round(20.9 - frac * 3.0, 2),
            humidity_pct=55.0,
            permit_type="hot_work" if frac > 0.5 else "general",
            worker_count=2 + i,
            zone="Zone-A-Tank-Farm",
            timestamp=datetime.utcnow().isoformat(),
            pressure_bar=1.013,
            rescue_team_present=True,
        ))
    return out


def random_reading(seed: int = None) -> SensorReading:
    if seed is not None:
        random.seed(seed)
    return SensorReading(
        gas_ppm=round(random.uniform(0, 130), 1),
        temp_c=round(random.uniform(20, 58), 1),
        oxygen_pct=round(random.uniform(17.0, 24.0), 2),
        humidity_pct=round(random.uniform(30, 95), 1),
        permit_type=random.choice(PERMIT_TYPES),
        worker_count=random.randint(0, 12),
        zone=random.choice(ZONES),
        timestamp=datetime.utcnow().isoformat(),
        pressure_bar=round(random.uniform(0.85, 2.2), 3),
        rescue_team_present=random.choice([True, False]),
    )


if __name__ == "__main__":
    print(normal_reading().to_dict())
    print(vizag_critical_reading().to_dict())
