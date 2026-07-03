# 🛡️ IndustrialSafetyAI — Agentic Process-Safety Command Center

**Multi-Agent AI for Industrial & Confined-Space Safety** · Vision + Deterministic Compliance + Grounded RAG + Live Dispatch

> Point a camera or a gas sensor at a hazard → get a risk score, the exact regulations violated, a grounded expert answer, an evacuation radius, and a spoken multilingual alert — **fully offline if needed.**

---

## 🚀 Why this beats a single-domain advisory app

IndustrialSafetyAI is built to out-engineer prior hackathon winners (e.g. *AgriBloom Agentic*) on **every axis**: it matches their feature set and adds a deterministic risk engine, a real offline computer-vision fallback, an industrial-hygiene calculator, and a full audit/evidence trail suitable for a regulated plant.

| Capability | AgriBloom Agentic | **IndustrialSafetyAI** |
|---|---|---|
| Domain | Crop disease advisory | **Life-safety / process safety** (higher stakes) |
| Agent pipeline | 5 agents (LangGraph) | **5 agents** (Orchestrator · Vision · Safety · Compliance · Knowledge) + **OutputAgent** formatting stage |
| Vision — online | Gemini Vision fallback | Gemini 2.5 Vision with % bounding boxes |
| Vision — **offline** | Needs GPU + 91k-image download | **Real OpenCV HSV pixel analysis** + a **CPU-trained model** (`hazard_model.npz`, trains in seconds, no dataset download) |
| Deterministic guardrail | 46 banned pesticides (lookup) | **20 OISD/OSHA safety rules with compound risk scoring** (0–100) — no LLM, fully auditable |
| Domain calculator | Fertilizer / NPK | **Industrial-hygiene calculator**: PEL/STEL exposure, %LEL, ventilation CFM, purge time, evacuation radius |
| Knowledge base | ICAR RAG | **Grounded ChromaDB RAG** — retrieves *then* synthesizes with citations; honest low-confidence fallback (never "keyword-mapped") |
| Languages | 10 Indian languages | **10 Indian languages** (English, Hindi, Telugu, Tamil, Marathi, Kannada, Punjabi, Gujarati, Bengali, Odia) |
| Voice output | Server-side TTS | **Browser Web-Speech TTS** — offline, multilingual, zero extra deps |
| Seasonal guidance | Crop calendar | **Seasonal safety calendar** (monsoon/summer/winter hazards + shift risk) |
| Helpline finder | KVK finder | **Nearest response-facility finder** (haversine ranking) + 24×7 helpline banner |
| Emergency response | — | **Emergency Dispatch** simulation (SMS/Email/PA/WhatsApp) with multilingual evacuation message |
| Live monitoring | — | **Live sensor stream**, risk-trend chart, **time-to-critical** extrapolation |
| Reports | PDF | PDF incident package **+ downloadable evidence ZIP** |
| Audit trail | Basic | **Append-only JSONL evidence log** of every agent decision (secrets sanitized) |
| Offline ready | Partial (local GPU) | **True offline path**: local CV + cached embeddings + deterministic compliance |
| Tests | 14 | **70 pytest + 16 authoritative acceptance tasks** (86 total, all green) |
| UI | Gradio | **Streamlit** — 6 interactive tabs, real uploads, live map |

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

## 🖥️ The six tabs

1. **Dashboard** — preset scenarios *and* full custom sensor controls (sliders + advanced JSON), a 60-second **live stream** with a risk-trend chart, **time-to-critical** estimate, PDF incident package, and evidence ZIP.
2. **Vision** — upload any JPG/PNG; hazards are drawn as labeled bounding boxes. Gemini online, genuine OpenCV analysis offline.
3. **Knowledge** — grounded RAG: retrieves top-k regulation chunks, synthesizes an answer, and **shows its sources & confidence** (never a canned lookup).
4. **Zone Map** — plant-layout overlay on the Vizag site with **live risk-colored** zone markers and a legend.
5. **Emergency Dispatch** — simulate SMS/Email/PA/WhatsApp dispatch with a **multilingual, spoken** evacuation message and full audit logging.
6. **Safety Tools** — exposure & ventilation calculator, nearest-facility finder, seasonal calendar, and the **voice-ready incident briefing** (OutputAgent).

---

## 🧪 Testing

```powershell
# 70 unit/integration tests
python -m pytest -q

# 16 authoritative acceptance tasks
for ($i=1; $i -le 16; $i++) { python tools\accept.py ("T{0:D3}" -f $i) }
```

All **86 checks pass**. Tests are offline-deterministic (no network required).

---

## 🔒 Engineering guarantees

- **Immutable schema contract** — agents return dataclasses, never ad-hoc dicts.
- **Deterministic compliance** — the 20-rule OISD engine makes **no LLM calls**; every risk score is reproducible and auditable.
- **LangGraph discipline** — nodes return update dicts only; no in-place state mutation.
- **Grounded, honest RAG** — retrieval first; general-knowledge answers are explicitly labeled and down-weighted. **No keyword-mapping tables.**
- **Security** — the Gemini API key is never printed or logged; the audit logger sanitizes secrets; local-filesystem only.
- **Offline-first** — cached embeddings, local CV, and deterministic engines mean the plant stays protected even with no connectivity.

---

## 📞 Emergency reference

`112` National Emergency · `101` Fire · `108` Ambulance · `1906` Gas-leak / PESO · `1078` NDMA — all 24×7.

*Built for high-stakes industrial environments where a wrong answer costs lives — not just a harvest.*
