"""T006 acceptance: ComplianceAgent deterministic rule engine (all 20 rules)."""
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
        from schema import ComplianceInput, ComplianceResult
        from agents.compliance_agent import ComplianceAgent
        from utils.sensor_simulator import normal_reading

        agent = ComplianceAgent()
        assert len(agent.rules) == 20, f"expected 20 rules, got {len(agent.rules)}"

        # Normal reading: passes.
        res = agent.evaluate(ComplianceInput(sensor=normal_reading()))
        assert isinstance(res, ComplianceResult)
        assert res.pass_status is True
        assert res.highest_severity is None

        # Determinism: same input -> same output twice.
        r = _reading(gas_ppm=120, oxygen_pct=18.0, permit_type="hot_work")
        a = agent.evaluate(ComplianceInput(sensor=r, active_permits=["hot_work"]))
        b = agent.evaluate(ComplianceInput(sensor=r, active_permits=["hot_work"]))
        assert [v.rule_id for v in a.violations] == [v.rule_id for v in b.violations]
        assert a.highest_severity == "CRITICAL"

        # R004 oxygen warning band 18-19.5.
        band = agent.evaluate(ComplianceInput(sensor=_reading(oxygen_pct=18.8)))
        assert "R004" in [v.rule_id for v in band.violations]

        # R006 confined space without rescue team.
        cs = _reading(permit_type="confined_space", rescue_team_present=False)
        r6 = agent.evaluate(ComplianceInput(sensor=cs,
                                            active_permits=["confined_space"]))
        assert "R006" in [v.rule_id for v in r6.violations]

        # R020 gas displacement.
        r20 = agent.evaluate(ComplianceInput(sensor=_reading(gas_ppm=60,
                                                             oxygen_pct=19.0)))
        assert "R020" in [v.rule_id for v in r20.violations]
    except Exception:
        traceback.print_exc()
        return 1
    print("T006 PASS: ComplianceAgent deterministic OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
