# 🛡️ IndustrialSafetyAI — Agentic Process-Safety Command Center

**Multi-Agent AI for Industrial & Confined-Space Safety** · Vision + Deterministic Compliance + Grounded RAG + Live Dispatch

> Point a camera or a gas sensor at a hazard → get a risk score, the exact regulations violated, a grounded expert answer, an evacuation radius, and a spoken multilingual alert — **fully offline if needed.**

---

## 🎯 Built for Problem Statement 1 — the headline evidence

PS1's decisive metric is *"reduction in false-negative rate — the metric that actually saves lives."* We measure it, honestly, against single-sensor baselines on a **physics-labeled** scenario dataset (`tools/benchmark.py`, stable across 20 random seeds):

| Detector | Missed incidents (operational) | False alarms | Median early warning |
|---|---|---|---|
| Single-sensor, evacuation-grade alarms | **~80%** (blind to conjunctions) | ~0% | — |
| Single-sensor, sensitive alarms | ~0% | **100%** (alarm fatigue) | 31 min |
| **Compound + prediction (ours)** | **0%** | **~0–3%** | **~18 min** |

Single sensors force an impossible trade-off — go blind to sub-threshold conjunctions **or** drown operators in false alarms. Our engine fuses **gas + permit + confinement + maintenance + shift-changeover + trend** to escape it: it catches every incident, early, without crying wolf. That is the exact blind spot that killed eight workers at Visakhapatnam Steel in January 2025.

**PS1 capabilities delivered:**
- **Compound Risk Detection** — deterministic compound scoring + predictive lead-time forecasting (`utils/forecast.py`); maintenance-in-confined and shift-changeover escalations.
- **Digital Permit Intelligence + Knowledge Graph** (`utils/knowledge_graph.py`) — flags hot-work/maintenance permits in zones *adjacent* to elevated gas (a graph query no single sensor can answer).
- **Incident Pattern Intelligence** (`utils/incident_intelligence.py`) — mines a near-miss corpus for recurring, severity-weighted prevention priorities and retrieves incidents similar to the live state.
- **Emergency Response Orchestrator** — multilingual spoken evacuation, evidence preservation (ZIP + JSONL), auto regulatory incident PDF.
- **Compliance Audit** — 20 deterministic rules, every one cross-referenced to **OISD + Factory Act 1948 + DGMS**.
- **Geospatial** — plant-layout risk overlay with a weighted hazard **heatmap** + permit-proximity graph.

Run it yourself: `python -m tools.benchmark`

---

## 🚀 Key capabilities

IndustrialSafetyAI is a production-grade, offline-capable process-safety intelligence platform: a deterministic compound-risk engine, a real offline computer-vision fallback, an industrial-hygiene calculator, and a full audit/evidence trail suitable for a regulated plant.

- **5-agent LangGraph pipeline** — Orchestrator · Vision · Safety · Compliance · Knowledge + an **OutputAgent** formatting stage.
- **Vision** — Gemini 2.5 with % bounding boxes online; **real OpenCV HSV pixel analysis + a CPU-trained model** (`hazard_model.npz`, trains in seconds, no dataset download) offline.
- **Deterministic guardrail** — 20 safety rules with **compound risk scoring (0–100)**, no LLM, fully auditable, each cross-referenced to **OISD + Factory Act 1948 + DGMS**.
- **Predictive compound detection** — maintenance / shift-changeover escalations + trajectory forecasting, benchmarked against single-sensor baselines.
- **Counterfactual intervention engine** — ranks the actions (revoke permit, ventilate, purge) that most reduce risk right now, with before/after scores.
- **Assessment confidence** — every verdict is scored on sensor coverage, signal decisiveness, and data freshness, so operators know how much to trust it.
- **Tamper-evident audit trail** — SHA-256 hash-chained evidence log with one-click integrity verification (OISD/PESO-grade).
- **Industrial-hygiene calculator** — PEL/STEL exposure, %LEL, ventilation CFM, purge time, evacuation radius.
- **Grounded ChromaDB RAG** — retrieves *then* synthesizes with citations; honest low-confidence fallback (never keyword-mapped).
- **Knowledge graph + Incident Pattern Intelligence** — permit-proximity conflict detection and recurring near-miss prevention priorities.
- **10 Indian languages** (English, Hindi, Telugu, Tamil, Marathi, Kannada, Punjabi, Gujarati, Bengali, Odia) with **browser Web-Speech TTS** (offline, zero extra deps).
- **Seasonal safety calendar**, **nearest response-facility finder** (haversine ranking) + 24×7 helpline banner.
- **Emergency Dispatch** — multilingual spoken evacuation message, live sensor stream, risk-trend chart, time-to-critical estimate.
- **Reporting & audit** — PDF incident package + downloadable evidence ZIP + append-only JSONL evidence log (secrets sanitized).
- **True offline path** — local CV + cached embeddings + deterministic compliance.
- **Tested** — **126 pytest + 16 authoritative acceptance tasks** (142 total, all green).
- **UI** — Streamlit, 7 interactive tabs, real uploads, live map, benchmark.

---

## 🏗️ Architecture — 5-stage LangGraph pipeline

```
              ┌──────────────┐
   input ───▶ │ Orchestrator │  (routes typed inputs; nodes return update dicts only)
              └──────┬───────┘
        ┌────────────┼────────────┬───────────────┐
        ▼            ▼            ▼               ▼
   ┌─────────┐  ┌─────────┐  ┌────────────┐  ┌────────────┐
   │ Vision  │  │ Safety  │  │ Compliance │  │ Knowledge  │
   │ Gemini/ │  │ compound│  │ 20 OISD    │  │ ChromaDB   │
   │ OpenCV  │  │ risk    │  │ rules      │  │ grounded   │
   └────┬────┘  └────┬────┘  └─────┬──────┘  └─────┬──────┘
        └────────────┴─────────────┴───────────────┘
                          ▼
                  ┌──────────────┐
                  │ OutputAgent  │  format + multilingual voice briefing
                  └──────────────┘
                          ▼
                 OrchestratorResult  ──▶  audit/evidence log
```

**Contract-first design:** every agent returns a schema dataclass; the orchestrator
converts raw dict payloads into typed inputs and aggregates into a single
`OrchestratorResult`. `schema.py` is an **immutable contract** — no agent invents its
own data shape.

---

## 📂 Project structure

```
v/
├── schema.py                     # Immutable dataclass contract (single source of truth)
├── agents/
│   ├── orchestrator.py           # LangGraph router + aggregator (5th OutputAgent stage)
│   ├── vision_agent.py           # Gemini primary → real offline OpenCV fallback
│   ├── safety_agent.py           # Compound risk score 0–100
│   ├── compliance_agent.py       # Deterministic 20-rule OISD engine (no LLM)
│   ├── knowledge_agent.py        # Grounded ChromaDB RAG + honest fallback
│   └── output_agent.py           # Formatting + multilingual incident briefing
├── compliance/safety_rules.json  # 20 OISD/OSHA rules
├── knowledge_base/               # PDF ingestion → ChromaDB (collection "safety_manual")
├── models/train_hazard_model.py  # Reproducible CPU hazard model → hazard_model.npz
├── utils/
│   ├── local_vision.py           # OpenCV HSV fire/smoke/electrical/gas detection
│   ├── exposure_calc.py          # PEL/STEL, %LEL, ventilation, evac radius
│   ├── safety_calendar.py        # Seasonal + shift safety advisories
│   ├── response_directory.py     # Helpline + nearest-facility finder
│   ├── translations.py           # 10-language evacuation messages
│   ├── voice.py                  # Browser Web-Speech TTS component
│   ├── vision_overlay.py         # Bounding-box overlay (PIL)
│   ├── zone_status.py            # Zone colors + time-to-critical
│   ├── audit_logger.py           # Append-only evidence trail (secrets sanitized)
│   └── evidence_export.py        # Evidence ZIP packager
├── ui/app.py                     # Streamlit UI (6 tabs)
├── tests/                        # 70 pytest tests
└── tools/accept.py               # 16 authoritative acceptance tasks (T001–T016)
```

---

## ⚡ Quick start

```powershell
cd $env:USERPROFILE\Desktop\v
.\venv\Scripts\activate           # Python 3.11 venv
pip install -r requirements.txt   # (already installed; lockfile: requirements.lock.txt)

# optional: enable Gemini (vision synthesis + live translation)
copy .env.example .env            # then add GEMINI_API_KEY

# train the offline hazard model (seconds, CPU, no download)
python models\train_hazard_model.py

# launch the UI
streamlit run ui\app.py --server.port 8502
# open http://localhost:8502
```

**Runs with or without a network / API key.** No key → the system uses real offline
computer vision, deterministic compliance, and extractive RAG.

---

## 🖥️ The seven tabs

1. **Dashboard** — preset scenarios *and* full custom sensor controls (sliders + advanced JSON), a 60-second **live stream** with a risk-trend chart, **time-to-critical** estimate, PDF incident package, and evidence ZIP. Supports `maintenance` and `shift_changeover` permit context for compound escalation.
2. **Vision** — upload any JPG/PNG; hazards are drawn as labeled bounding boxes. Gemini online, genuine OpenCV analysis offline.
3. **Knowledge** — grounded RAG with sources & confidence, tri-framework (OISD/Factory Act/DGMS) coverage, plus **Incident Pattern Intelligence** (recurring prevention priorities + similar past incidents).
4. **Zone Map** — plant-layout overlay with **live risk-colored** markers, a weighted risk **heatmap**, and **Permit-Proximity Intelligence** (knowledge-graph conflict detection + graph view).
5. **Emergency Dispatch** — simulate SMS/Email/PA/WhatsApp dispatch with a **multilingual, spoken** evacuation message and full audit logging.
6. **Safety Tools** — exposure & ventilation calculator, nearest-facility finder, seasonal calendar, and the **voice-ready incident briefing** (OutputAgent).
7. **Compound vs Single-Sensor** — the PS1 benchmark: headline false-negative reduction, detector comparison table, and the **Vizag counterfactual replay**.

---

## 🧪 Testing

```powershell
# ~110 unit/integration tests
python -m pytest -q

# the compound-vs-single-sensor benchmark (PS1 headline metric)
python -m tools.benchmark

# 16 authoritative acceptance tasks
for ($i=1; $i -le 16; $i++) { python tools\accept.py ("T{0:D3}" -f $i) }
```

All checks pass (**126 pytest + 16 acceptance**). Tests are offline-deterministic (no network required).

---

## 🔒 Engineering guarantees

- **Immutable schema contract** — agents return dataclasses, never ad-hoc dicts.
- **Deterministic compliance** — the 20-rule engine makes **no LLM calls**; every rule is cross-referenced to **OISD + Factory Act 1948 + DGMS**, and every risk score is reproducible and auditable.
- **Honest benchmarking** — the compound-vs-single-sensor evaluation uses detector-independent physics ground truth and realistic baselines; no test-gaming.
- **LangGraph discipline** — nodes return update dicts only; no in-place state mutation.
- **Grounded, honest RAG** — retrieval first; general-knowledge answers are explicitly labeled and down-weighted. **No keyword-mapping tables.**
- **Security** — the Gemini API key is never printed or logged; the audit logger sanitizes secrets; local-filesystem only.
- **Offline-first** — cached embeddings, local CV, and deterministic engines mean the plant stays protected even with no connectivity.

---

## 📞 Emergency reference

`112` National Emergency · `101` Fire · `108` Ambulance · `1906` Gas-leak / PESO · `1078` NDMA — all 24×7.

*Built for high-stakes industrial environments where a wrong answer costs lives — not just a harvest.*
