"""Warm FastAPI backend for IndustrialSafetyAI.

Loads the light compound-risk stack once at startup (SafetyAgent/ComplianceAgent are
pure-Python and fast); the heavy RAG stack (torch/sentence-transformers/chromadb) is
lazy-loaded only on the first /api/knowledge call, so the API starts in well under a
second and every sensor scan is served in ~20ms — a decisive speed win over reloading
the stack per interaction.

Run:  uvicorn backend.main:app --port 8000
"""
from __future__ import annotations

import os
import sys
from functools import lru_cache
from typing import Dict, List, Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

# Light imports only (no torch/chromadb here).
from schema import SensorReading, SensorInput, ComplianceInput, QueryInput  # noqa: E402
from agents.safety_agent import SafetyAgent  # noqa: E402
from agents.compliance_agent import ComplianceAgent  # noqa: E402
from utils.interventions import rank_interventions  # noqa: E402
from utils.confidence import assess_confidence  # noqa: E402
from utils.limit_check import limit_utilisation  # noqa: E402
from utils.baseline_detector import PROFILES as _SINGLE_PROFILES  # noqa: E402
from utils.zone_status import zone_colors  # noqa: E402
from utils import knowledge_graph as kg  # noqa: E402
from utils import incident_intelligence as ii  # noqa: E402
from utils.audit_logger import verify_chain, append_event  # noqa: E402

app = FastAPI(title="IndustrialSafetyAI API", version="1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_safety = SafetyAgent()
_compliance = ComplianceAgent()
_knowledge = None  # lazy


def _get_knowledge():
    global _knowledge
    if _knowledge is None:
        from agents.knowledge_agent import KnowledgeAgent  # heavy import, deferred
        _knowledge = KnowledgeAgent()
    return _knowledge


# ---------------------------------------------------------------- models
class ReadingModel(BaseModel):
    gas_ppm: float = 5.0
    temp_c: float = 30.0
    oxygen_pct: float = 20.9
    humidity_pct: float = 50.0
    permit_type: str = "general"
    worker_count: int = 2
    zone: str = "Zone-A-Tank-Farm"
    timestamp: Optional[str] = None
    pressure_bar: float = 1.013
    rescue_team_present: bool = True


class ScanRequest(BaseModel):
    reading: ReadingModel
    active_permits: List[str] = Field(default_factory=list)


class QueryRequest(BaseModel):
    query: str


def _to_reading(m: ReadingModel) -> SensorReading:
    from datetime import datetime
    d = m.model_dump()
    d["timestamp"] = d.get("timestamp") or datetime.utcnow().isoformat()
    return SensorReading(**d)


# ---------------------------------------------------------------- endpoints
@app.get("/api/health")
def health():
    return {"status": "ok", "knowledge_loaded": _knowledge is not None}


@app.post("/api/scan")
def scan(req: ScanRequest):
    try:
        reading = _to_reading(req.reading)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=str(e))
    permits = list(req.active_permits)
    alert = _safety.assess(SensorInput(reading=reading, active_permits=permits))
    comp = _compliance.evaluate(ComplianceInput(sensor=reading, active_permits=permits))
    conf = assess_confidence(reading)
    iv = rank_interventions(reading, permits)
    limits = limit_utilisation(reading)

    sp = _SINGLE_PROFILES["high_alarm"]
    single = []
    if reading.gas_ppm >= sp["gas_ppm"]:
        single.append("gas")
    if reading.oxygen_pct < sp["oxygen_pct"]:
        single.append("oxygen")
    if reading.temp_c >= sp["temp_c"]:
        single.append("temperature")

    result = {
        "risk_score": alert.risk_score,
        "triggered_rules": alert.triggered_rules,
        "recommended_action": alert.recommended_action,
        "zone": alert.zone,
        "compliance": {
            "pass_status": comp.pass_status,
            "highest_severity": comp.highest_severity,
            "violations": [{"rule_id": v.rule_id, "name": v.name,
                            "severity": v.severity, "message": v.message,
                            "reference": v.oisd_reference} for v in comp.violations],
        },
        "confidence": conf,
        "interventions": iv,
        "limits": limits,
        "single_sensor": {"fired": single, "count": len(single), "total": 3,
                          "compound_fires": alert.risk_score >= 50},
    }
    append_event({"type": "api_scan", "risk_score": alert.risk_score,
                  "severity": comp.highest_severity, "zone": reading.zone})
    return result


@app.get("/api/zones")
def zones(gas: float = 8.0, oxygen: float = 20.9, humidity: float = 50.0,
          permits: str = ""):
    plist = [p for p in permits.split(",") if p]
    colors = zone_colors(gas, oxygen, humidity, plist)
    color_gas = {"red": 90.0, "orange": 65.0, "green": 20.0}
    sel = max(colors, key=lambda z: {"red": 2, "orange": 1, "green": 0}[colors[z]])
    zone_states = {z: {"gas_ppm": color_gas[colors[z]], "oxygen_pct": oxygen,
                       "permits": plist if z == sel else []} for z in kg.ZONES}
    g = kg.build_plant_graph(zone_states)
    graph = {
        "nodes": [{"id": n, **{k: str(v) for k, v in d.items()}}
                  for n, d in g.nodes(data=True)],
        "edges": [{"source": u, "target": v, "relation": d.get("relation", "")}
                  for u, v, d in g.edges(data=True)],
    }
    return {"colors": colors, "conflicts": kg.permits_near_hazard(zone_states),
            "graph": graph}


@app.get("/api/incidents")
def incidents(gas: Optional[float] = None, oxygen: Optional[float] = None,
              zone: Optional[str] = None, permits: str = ""):
    corpus = ii.load_incidents()
    out = {"count": len(corpus),
           "priorities": ii.prevention_priorities(corpus, top_k=5),
           "patterns": ii.recurring_patterns(corpus)[:8]}
    if gas is not None and oxygen is not None and zone:
        out["similar"] = ii.similar_incidents(
            gas, oxygen, zone, [p for p in permits.split(",") if p], top_k=3)
    return out


@lru_cache(maxsize=1)
def _benchmark():
    from tools.benchmark import run
    return run(seed=42)


@app.get("/api/benchmark")
def benchmark():
    return _benchmark()


@app.get("/api/audit/verify")
def audit_verify():
    return verify_chain()


@app.post("/api/knowledge")
def knowledge(req: QueryRequest):
    try:
        res = _get_knowledge().query(QueryInput(query_text=req.query))
        return {"answer": res.answer, "confidence": res.confidence,
                "sources": res.sources,
                "answered_from_documents": bool(res.sources),
                "error": res.error}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
