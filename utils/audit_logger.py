"""Append-only evidence/audit trail as JSONL. Never logs secrets.

Every orchestrator call at a UI/demo boundary can be recorded here so the demo
can show a real audit trail and export it. Kept out of the Orchestrator core so
the graph stays pure and deterministic.
"""
import os
import json
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_PATH = os.path.join(_ROOT, "data", "evidence_log.jsonl")

# keys that must never be written, even if a caller passes them through
_FORBIDDEN = ("gemini_api_key", "api_key", "apikey", "authorization", "token")


def _sanitize(obj):
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()
                if k.lower() not in _FORBIDDEN}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


def append_event(event: dict, path: str = _DEFAULT_PATH) -> None:
    """Append one sanitized JSON event as a line. Never raises."""
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        payload = _sanitize(dict(event))
        payload.setdefault("timestamp", datetime.utcnow().isoformat())
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        # audit logging must never break the caller
        pass


def read_last_n(n: int = 100, path: str = _DEFAULT_PATH) -> list:
    """Return the last n events (most recent last). Never raises."""
    try:
        if not os.path.isfile(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            lines = [ln for ln in f.read().splitlines() if ln.strip()]
        out = []
        for ln in lines[-n:]:
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
        return out
    except Exception:
        return []


def event_from_result(result, sensor: dict = None, active_permits=None,
                      event_type: str = "orchestrator", extra: dict = None) -> dict:
    """Build a standardized evidence event from an OrchestratorResult.

    Captures risk/compliance/vision/knowledge evidence plus an optional sensor
    snapshot and active permits. Does not include any secret material.
    """
    ev = {
        "timestamp": datetime.utcnow().isoformat(),
        "type": event_type,
        "request_id": getattr(result, "request_id", None),
        "input_type": getattr(result, "input_type", None),
    }
    if sensor is not None:
        ev["sensor"] = _sanitize(dict(sensor))
    if active_permits is not None:
        ev["active_permits"] = list(active_permits)

    safety = getattr(result, "safety", None)
    if safety is not None:
        ev["safety"] = {
            "risk_score": safety.risk_score,
            "triggered_rules": list(safety.triggered_rules),
            "recommended_action": safety.recommended_action,
        }

    compliance = getattr(result, "compliance", None)
    if compliance is not None:
        ev["compliance"] = {
            "pass_status": compliance.pass_status,
            "highest_severity": compliance.highest_severity,
            "violations": [v.rule_id for v in compliance.violations],
        }

    vision = getattr(result, "vision", None)
    if vision is not None:
        types = [h.type for h in vision.hazards]
        ev["vision"] = {
            "source": vision.source,
            "hazard_count": len(types),
            "hazard_types": types,
        }

    knowledge = getattr(result, "knowledge", None)
    if knowledge is not None:
        ev["knowledge"] = {
            "confidence": knowledge.confidence,
            "sources": [s.get("filename") for s in knowledge.sources],
        }

    if getattr(result, "error", None):
        ev["error"] = result.error
    if extra:
        ev.update(_sanitize(dict(extra)))
    return ev


if __name__ == "__main__":
    append_event({"type": "selftest", "note": "hello", "api_key": "SECRET"})
    last = read_last_n(1)
    print("last event has api_key:", "api_key" in (last[-1] if last else {}))
    print(last[-1] if last else None)
