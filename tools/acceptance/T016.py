"""T016 acceptance: DemoRunner.run_phases two-phase validation.

safe_results length>=2 and safe_results[0].safety.risk_score < 40
escalated_results length>=2 and escalated_results[-1].safety.risk_score >= 70
"""
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def main():
    try:
        from utils.demo_runner import DemoRunner
        res = DemoRunner().run_phases()
        safe = res["safe_results"]
        esc = res["escalated_results"]

        assert len(safe) >= 2, f"safe_results too short: {len(safe)}"
        assert len(esc) >= 2, f"escalated_results too short: {len(esc)}"

        assert safe[0].safety.risk_score < 40, \
            f"safe[0] risk expected <40, got {safe[0].safety.risk_score}"
        assert esc[-1].safety.risk_score >= 70, \
            f"escalated[-1] risk expected >=70, got {esc[-1].safety.risk_score}"

        print("safe risks:", [r.safety.risk_score for r in safe])
        print("escalated risks:", [r.safety.risk_score for r in esc])
    except Exception:
        traceback.print_exc()
        return 1
    print("T016 PASS: DemoRunner two-phase validation OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
