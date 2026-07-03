"""T003 acceptance: sensor_simulator produces valid SensorReading objects."""
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def main():
    try:
        from schema import SensorReading
        from utils.sensor_simulator import (
            normal_reading, vizag_critical_reading, escalating_readings,
            random_reading,
        )
        n = normal_reading()
        assert isinstance(n, SensorReading)
        assert n.gas_ppm < 20 and n.oxygen_pct > 20

        v = vizag_critical_reading()
        assert isinstance(v, SensorReading)
        assert v.gas_ppm > 100 and v.oxygen_pct < 19.5
        assert "hot_work" == v.permit_type

        ramp = escalating_readings(4)
        assert len(ramp) == 4
        assert ramp[0].gas_ppm < ramp[-1].gas_ppm

        r = random_reading(seed=1)
        assert isinstance(r, SensorReading)
    except Exception:
        traceback.print_exc()
        return 1
    print("T003 PASS: sensor_simulator OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
