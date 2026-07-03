"""T010 acceptance: report_generator produces a non-empty PDF from a result."""
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def main():
    try:
        from schema import OrchestratorInput
        from agents.orchestrator import Orchestrator
        from utils.report_generator import generate_report
        from utils.sensor_simulator import vizag_critical_reading

        orch = Orchestrator()
        result = orch.run(OrchestratorInput(
            input_type="sensor",
            data={"reading": vizag_critical_reading().to_dict(),
                  "active_permits": ["hot_work"]}))

        out = os.path.join(ROOT, "data", "acceptance_report.pdf")
        if os.path.exists(out):
            os.remove(out)
        path = generate_report(result, out)
        assert os.path.exists(path), "PDF not created"
        size = os.path.getsize(path)
        assert size > 1000, f"PDF suspiciously small: {size} bytes"
        with open(path, "rb") as f:
            assert f.read(4) == b"%PDF", "not a valid PDF header"
    except Exception:
        traceback.print_exc()
        return 1
    print("T010 PASS: report_generator PDF OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
