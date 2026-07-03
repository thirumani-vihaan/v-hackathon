"""T008 acceptance: SafetyAgent compound scoring is exact and clamped."""
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def _reading(**kw):
    from schema import SensorReading
    base = dict(gas_ppm=5, temp_c=30, oxygen_pct=20.9, humidity_pct=50,
                permit_type="general", worker_count=1, zone="Z",
                timestamp="2026-07-03T00:00:00")
    base.update(kw)
    return SensorReading(**base)


def main():
    try:
        from schema import SensorInput, SafetyAlert
        from agents.safety_agent import SafetyAgent
        agent = SafetyAgent()

        # gas 60 only => +30
        a = agent.assess(SensorInput(reading=_reading(gas_ppm=60)))
        assert isinstance(a, SafetyAlert)
        assert a.risk_score == 30, f"gas-only expected 30 got {a.risk_score}"

        # oxygen 18 only => +40
        b = agent.assess(SensorInput(reading=_reading(oxygen_pct=18.0)))
        assert b.risk_score == 40, f"oxygen-only expected 40 got {b.risk_score}"

        # gas 120 + oxygen 18 + hot_work => 30+40+50+30 = 150 -> cap 100
        c = agent.assess(SensorInput(
            reading=_reading(gas_ppm=120, oxygen_pct=18.0, permit_type="hot_work"),
            active_permits=["hot_work"]))
        assert c.risk_score == 100, f"compound expected 100 got {c.risk_score}"

        # normal => low
        d = agent.assess(SensorInput(reading=_reading()))
        assert d.risk_score < 40
    except Exception:
        traceback.print_exc()
        return 1
    print("T008 PASS: SafetyAgent compound scoring OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
