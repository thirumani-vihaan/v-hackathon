"""T009 acceptance: Orchestrator LangGraph routing, request_id preservation,
and dataclass outputs for query + sensor routes."""
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def main():
    try:
        from schema import OrchestratorInput, OrchestratorResult
        from agents.orchestrator import Orchestrator
        from utils.sensor_simulator import vizag_critical_reading

        orch = Orchestrator()

        # Sensor routing.
        oi_s = OrchestratorInput(
            input_type="sensor",
            data={"reading": vizag_critical_reading().to_dict(),
                  "active_permits": ["hot_work"]})
        rs = orch.run(oi_s)
        assert isinstance(rs, OrchestratorResult)
        assert rs.request_id == oi_s.request_id, "request_id not preserved (sensor)"
        assert rs.safety is not None and rs.compliance is not None
        assert rs.knowledge is None and rs.vision is None, \
            "sensor route must not populate knowledge/vision"

        # Query routing.
        oi_q = OrchestratorInput(
            input_type="query",
            data={"query_text": "confined space entry requirements"})
        rq = orch.run(oi_q)
        assert isinstance(rq, OrchestratorResult)
        assert rq.request_id == oi_q.request_id, "request_id not preserved (query)"
        assert rq.knowledge is not None, "query route must populate knowledge"
        assert rq.safety is None and rq.compliance is None, \
            "query route must not populate safety/compliance"

        # Image routing.
        img = os.path.join(ROOT, "data", "test_safety_image.jpg")
        oi_i = OrchestratorInput(input_type="image", data={"image_path": img})
        ri = orch.run(oi_i)
        assert ri.vision is not None, "image route must populate vision"
        assert ri.request_id == oi_i.request_id
    except Exception:
        traceback.print_exc()
        return 1
    print("T009 PASS: Orchestrator routing + request_id preservation OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
