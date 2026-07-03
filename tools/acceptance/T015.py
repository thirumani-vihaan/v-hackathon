"""T015 acceptance: main.run_vizag_scenario asserts CRITICAL + risk>=80."""
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def main():
    try:
        import main
        summary = main.run_vizag_scenario()
        assert summary["highest_severity"] == "CRITICAL", \
            f"expected CRITICAL, got {summary['highest_severity']}"
        assert summary["risk_score"] >= 80, \
            f"expected risk>=80, got {summary['risk_score']}"
        print("scenario summary:", summary)
    except Exception:
        traceback.print_exc()
        return 1
    print("T015 PASS: vizag scenario CRITICAL + risk>=80")
    return 0


if __name__ == "__main__":
    sys.exit(main())
