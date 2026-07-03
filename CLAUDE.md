# CLAUDE.md — IndustrialSafetyAI Engineering Contract

This document is the authoritative engineering contract for the IndustrialSafetyAI
project. Every contributor (human or agent) MUST follow it.

## 1. ABSOLUTE RULES

1. `schema.py` is an **immutable global contract**. After it is written it must not
   be changed. ALL modules import their dataclasses from `schema.py`.
2. **Do NOT define new `@dataclass` types anywhere else.** If you need a new shape,
   it does not belong here — reuse the existing dataclasses.
3. Agent methods return **schema dataclasses**, never raw dicts.
4. The Orchestrator aggregates agent outputs into a single `OrchestratorResult`.
5. **No test-gaming.** Implement real, generalizing logic. Never hard-code answers to
   pass a specific acceptance check.
6. Never raise uncaught exceptions across an agent boundary. Catch, log, and populate
   the `error` field of the returned dataclass with a degraded-but-valid result.
7. Security: never `git push`, never modify git remotes, never authenticate to a git
   provider. Local filesystem only.

## 2. FILE BOUNDARY RULES

| Path | Responsibility |
|------|----------------|
| `schema.py` | All dataclasses (immutable). |
| `compliance/safety_rules.json` | 20 deterministic OISD rules (R001–R020). |
| `utils/sensor_simulator.py` | Generate `SensorReading` objects. |
| `utils/gemini_vision.py` | Gemini wrapper w/ safe fallback. |
| `utils/report_generator.py` | PDF report from `OrchestratorResult`. |
| `utils/demo_runner.py` | `DemoRunner.run_phases()` scenario driver. |
| `agents/vision_agent.py` | Image → `VisionResult`. |
| `agents/compliance_agent.py` | Sensor → `ComplianceResult` (deterministic). |
| `agents/knowledge_agent.py` | Query → `KnowledgeResult` (RAG + citations). |
| `agents/safety_agent.py` | Sensor+vision → `SafetyAlert` (compound scoring). |
| `agents/orchestrator.py` | LangGraph routing → `OrchestratorResult`. |
| `knowledge_base/build_db.py` | Ingest PDFs into ChromaDB. |
| `ui/app.py` | Streamlit UI (4 tabs + folium map, port 8502). |
| `main.py` | `run_vizag_scenario()` entry point. |

## 3. ARCHITECTURE

```
                         +-------------------------+
        input_type ----> |      Orchestrator       |  (LangGraph StateGraph)
   image|sensor|query    |  request_id preserved   |
        full_scan        +-----------+-------------+
                                     |
        +----------------+----------------+------------------+
        |                |                |                  |
        v                v                v                  v
 +-------------+  +--------------+  +---------------+  +----------------+
 | VisionAgent |  | SafetyAgent  |  | ComplianceAg. |  | KnowledgeAgent |
 |  image ->   |  | sensor+vis ->|  | sensor ->     |  | query ->       |
 | VisionResult|  | SafetyAlert  |  | ComplianceRes.|  | KnowledgeResult|
 +------+------+  +------+-------+  +-------+-------+  +--------+-------+
        |                |                 |                   |
        +----------------+--------+--------+-------------------+
                                  v
                        +------------------+
                        | OrchestratorResult|
                        +------------------+
```

## 4. DATA FLOW CONTRACTS (typed dataclasses)

- `VisionInput`      -> `VisionAgent.analyze()`      -> `VisionResult`
- `ComplianceInput`  -> `ComplianceAgent.evaluate()` -> `ComplianceResult`
- `QueryInput`       -> `KnowledgeAgent.query()`     -> `KnowledgeResult`
- `SensorInput`      -> `SafetyAgent.assess()`       -> `SafetyAlert`
- `OrchestratorInput`-> `Orchestrator.run()`         -> `OrchestratorResult`

Agents accept their typed `*Input` dataclass and return their `*Result` dataclass.

## 5. ORCHESTRATOR dict -> dataclass CONVERSION

The Orchestrator receives loosely-typed `data: Dict[str, Any]` in `OrchestratorInput`.
It MUST convert dicts into the strict input dataclasses before calling agents.

CORRECT:
```python
reading = SensorReading(**data["reading"])          # dict -> dataclass
ci = ComplianceInput(sensor=reading, active_permits=data.get("active_permits", []))
compliance_result = compliance_agent.evaluate(ci)   # returns ComplianceResult
```

WRONG:
```python
compliance_result = compliance_agent.evaluate(data) # passing raw dict -> forbidden
result = {"pass": True}                              # returning a dict -> forbidden
```

## 6. ERROR PHILOSOPHY

- Agents never let exceptions escape. Wrap the body in try/except.
- On failure, return a valid dataclass with `error=<str>` populated and safe defaults
  (e.g. empty `hazards`, `risk_score=0` or a conservative high score, `pass_status`
  reflecting inability to verify).
- The Orchestrator also guards each node; a single failing agent must not crash the run.

## 7. ChromaDB 0.5.x NOTES

- Prefer `PersistentClient` with telemetry disabled:
  ```python
  from chromadb.config import Settings
  client = chromadb.PersistentClient(path=persist_dir,
                                     settings=Settings(anonymized_telemetry=False))
  ```
  Fall back to `chromadb.PersistentClient(path=persist_dir)` if `Settings` import/shape
  differs.
- Always use `client.get_or_create_collection(name)` (never assume it exists).
- Embeddings: prefer
  `chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")`.
  Fall back to a raw `sentence_transformers.SentenceTransformer` if the util shape changed.
- Pass `embedding_function=` to `get_or_create_collection` so add/query are consistent.

## 8. LangGraph NOTES

- Nodes MUST return an **update dict only** (e.g. `return {"result": ...}`).
  **Never mutate the incoming state in place** — that is the classic state-mutation
  footgun and produces nondeterministic graphs.
- Define state as a `TypedDict`. Build with `StateGraph(State)`.
- `compile()` the graph **once**; `invoke(initial_state)` per request.
- Route with conditional edges keyed off `input_type`.

## 9. GEMINI USAGE

- Model preference order (current stable first, legacy as fallback):
  `gemini-2.5-flash` -> `gemini-2.0-flash` -> `gemini-flash-latest` ->
  `gemini-2.0-flash-exp` -> `gemini-1.5-flash`. Iterate until one responds; older
  names 404 on July-2026 API versions, so newer models are tried first.
- If `GEMINI_API_KEY` is empty/missing: produce a **safe fallback** `VisionResult`
  (`source="fallback"`, deterministic hazards) and never crash.
- Parse model JSON defensively; on any parse error, degrade to fallback.

## 10. COMPOUND RISK SCORING (EXACT)

```
score = 0
if gas_ppm > 50:                                   score += 30
if oxygen_pct < 19.5:                              score += 40
if gas_ppm > 50 and 'hot_work' in active_permits:  score += 50
if gas_ppm > 80:                                   score += 30
score = min(score, 100)
```
Cap at 100. This scoring lives in `agents/safety_agent.py`.

## 11. FORBIDDEN PATTERNS

- Defining `@dataclass` outside `schema.py`.
- Returning dicts from agent methods.
- Mutating LangGraph state in place inside a node.
- `anonymized_telemetry=True` / leaving ChromaDB telemetry on.
- Hard-coding acceptance answers ("test-gaming").
- Uncaught exceptions crossing an agent boundary.
- `git push`, adding remotes, or provider auth.
- Using `jq` for JSON manipulation (use the Python helpers in `tools/`).
