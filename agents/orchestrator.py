"""Orchestrator: routes an OrchestratorInput through the right agent(s) using a
LangGraph StateGraph and aggregates results into a single OrchestratorResult.

CLAUDE.md compliance:
- Nodes return update dicts ONLY; they never mutate incoming state in place.
- Graph is compiled once (at construction); invoked per request.
- Dicts in OrchestratorInput.data are converted to strict input dataclasses.
- request_id is preserved end-to-end.
- Every agent call is guarded; a single agent failure never crashes the run.
"""
import os
import sys
from typing import TypedDict, Optional, Any, Dict

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from schema import (  # noqa: E402
    OrchestratorInput, OrchestratorResult,
    VisionInput, SensorInput, QueryInput, ComplianceInput,
    SensorReading, VisionResult, SafetyAlert, ComplianceResult, KnowledgeResult,
)
from agents.vision_agent import VisionAgent  # noqa: E402
from agents.compliance_agent import ComplianceAgent  # noqa: E402
from agents.knowledge_agent import KnowledgeAgent  # noqa: E402
from agents.safety_agent import SafetyAgent  # noqa: E402


class GraphState(TypedDict, total=False):
    request_id: str
    input_type: str
    data: Dict[str, Any]
    vision: Optional[VisionResult]
    safety: Optional[SafetyAlert]
    compliance: Optional[ComplianceResult]
    knowledge: Optional[KnowledgeResult]
    error: Optional[str]


def _reading_from_data(data: Dict[str, Any]) -> SensorReading:
    raw = data.get("reading", data)
    if isinstance(raw, SensorReading):
        return raw
    return SensorReading(**raw)


class Orchestrator:
    def __init__(self, knowledge_agent: Optional[KnowledgeAgent] = None):
        self.vision_agent = VisionAgent()
        self.compliance_agent = ComplianceAgent()
        self.safety_agent = SafetyAgent()
        # Knowledge agent touches ChromaDB; allow injection / lazy failure.
        self.knowledge_agent = knowledge_agent or KnowledgeAgent()
        self._app = self._build_graph()

    # ---- nodes: each returns an UPDATE dict only ----
    def _vision_node(self, state: GraphState) -> Dict[str, Any]:
        try:
            data = state["data"]
            vi = VisionInput(image_path=data.get("image_path", ""),
                             request_id=state["request_id"])
            return {"vision": self.vision_agent.analyze(vi)}
        except Exception as e:  # noqa: BLE001
            return {"vision": VisionResult(hazards=[], summary="vision failed",
                                           source="fallback", error=str(e))}

    def _sensor_node(self, state: GraphState) -> Dict[str, Any]:
        update: Dict[str, Any] = {}
        try:
            data = state["data"]
            reading = _reading_from_data(data)
            permits = data.get("active_permits", [])
            si = SensorInput(reading=reading, active_permits=permits,
                             request_id=state["request_id"])
            ci = ComplianceInput(sensor=reading, active_permits=permits,
                                 request_id=state["request_id"])
            update["safety"] = self.safety_agent.assess(si)
            update["compliance"] = self.compliance_agent.evaluate(ci)
        except Exception as e:  # noqa: BLE001
            update["error"] = str(e)
            update["safety"] = SafetyAlert(risk_score=0, triggered_rules=[],
                                           recommended_action="error",
                                           zone="unknown", error=str(e))
            update["compliance"] = ComplianceResult(pass_status=False, violations=[],
                                                    highest_severity=None, error=str(e))
        return update

    def _query_node(self, state: GraphState) -> Dict[str, Any]:
        try:
            data = state["data"]
            qi = QueryInput(query_text=data.get("query_text", ""),
                            request_id=state["request_id"])
            return {"knowledge": self.knowledge_agent.query(qi)}
        except Exception as e:  # noqa: BLE001
            return {"knowledge": KnowledgeResult(answer="query failed", sources=[],
                                                 confidence=0.0, error=str(e))}

    def _full_scan_node(self, state: GraphState) -> Dict[str, Any]:
        update: Dict[str, Any] = {}
        update.update(self._sensor_node(state))
        if state["data"].get("image_path"):
            update.update(self._vision_node(state))
        if state["data"].get("query_text"):
            update.update(self._query_node(state))
        return update

    def _route(self, state: GraphState) -> str:
        it = state.get("input_type")
        if it == "image":
            return "route_vision"
        if it == "sensor":
            return "route_sensor"
        if it == "query":
            return "route_query"
        return "route_full_scan"

    def _build_graph(self):
        from langgraph.graph import StateGraph, END
        g = StateGraph(GraphState)
        # Node names must NOT collide with state keys (vision/safety/etc.).
        g.add_node("route_vision", self._vision_node)
        g.add_node("route_sensor", self._sensor_node)
        g.add_node("route_query", self._query_node)
        g.add_node("route_full_scan", self._full_scan_node)

        g.set_conditional_entry_point(self._route, {
            "route_vision": "route_vision",
            "route_sensor": "route_sensor",
            "route_query": "route_query",
            "route_full_scan": "route_full_scan",
        })
        for node in ("route_vision", "route_sensor", "route_query",
                     "route_full_scan"):
            g.add_edge(node, END)
        return g.compile()

    def run(self, orch_input: OrchestratorInput) -> OrchestratorResult:
        initial: GraphState = {
            "request_id": orch_input.request_id,
            "input_type": orch_input.input_type,
            "data": orch_input.data or {},
        }
        try:
            final = self._app.invoke(initial)
        except Exception as e:  # noqa: BLE001
            return OrchestratorResult(request_id=orch_input.request_id,
                                      input_type=orch_input.input_type, error=str(e))
        return OrchestratorResult(
            request_id=orch_input.request_id,
            input_type=orch_input.input_type,
            vision=final.get("vision"),
            safety=final.get("safety"),
            compliance=final.get("compliance"),
            knowledge=final.get("knowledge"),
            error=final.get("error"),
        )


if __name__ == "__main__":
    from utils.sensor_simulator import vizag_critical_reading
    orch = Orchestrator()
    oi = OrchestratorInput(input_type="sensor",
                           data={"reading": vizag_critical_reading().to_dict(),
                                 "active_permits": ["hot_work"]})
    r = orch.run(oi)
    print("request_id preserved:", r.request_id == oi.request_id)
    print("risk:", r.safety.risk_score, "compliance:", r.compliance.highest_severity)
