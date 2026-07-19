# HANDOFF — IndustrialSafetyAI (read this first)

> **Purpose of this file:** a complete brief for a *new AI agent (or developer)* to
> understand this project and continue the work — architecture, every subsystem, how to
> run/test it, the conventions and contracts that MUST be respected, the competitive
> landscape, and what to do next. Read this end-to-end before changing anything.

**Repo:** local git at `C:\Users\kathyayanit\Desktop\v`, pushed to GitHub
`thirumani-vihaan/v-hackathon` (personal remote). Windows, Python 3.11 venv, Node 22.

---

## 1. What this is

**IndustrialSafetyAI** — a hackathon submission for **Problem Statement 1: "AI-Powered
Industrial Safety Intelligence for Zero-Harm Operations."** It fuses IoT/gas sensors,
permit-to-work logs, CCTV, and shift records into a **predictive compound-risk layer**
that detects dangerous *combinations* no single sensor flags (e.g. hot work + gas
accumulation in a confined space at shift changeover — the **Visakhapatnam Steel Plant
Jan-2025 coke-oven explosion**, 8 deaths, which anchors the whole narrative), and acts
*before* an incident: geospatial risk map, RAG over OISD/Factory Act/DGMS regulations,
emergency response orchestration (multilingual voice), and incident-pattern intelligence.

**Judging criteria (PS1):** Innovation 25 / Business Impact 25 / Technical Excellence 20
/ Scalability 15 / UX 15. **Evaluation focus:** compound accuracy vs single-sensor
baselines, prediction lead time, geospatial quality, regulatory coverage
(OISD/Factory Act/DGMS), and **false-negative reduction** ("the metric that saves lives").

---

## 2. Architecture (two-tier + legacy Streamlit)

```
┌─────────────────────────┐        ┌──────────────────────────────────────────┐
│  React + Vite frontend  │  /api  │  FastAPI backend (backend/main.py)         │
│  frontend/  (SPA, dark) │◀──────▶│  WARM: loads once, ~20ms scans             │
│  served at "/" by FastAPI│  JSON  │  lazy-loads heavy RAG stack on 1st use     │
└─────────────────────────┘        │  reuses the SAME Python packages below     │
                                    └──────────────────────────────────────────┘
                                                     │ imports
   ┌────────────────────────────────────────────────┴───────────────────────────┐
   │ agents/ (LangGraph orchestrator + 5 agents)   utils/ (risk, vision, forecast,│
   │ schema.py (IMMUTABLE dataclass contract)      knowledge graph, incidents,    │
   │ compliance/safety_rules.json (20 rules)       confidence, interventions, …)  │
   │ knowledge_base/ (ChromaDB build)  models/ (offline hazard model)  tools/     │
   └──────────────────────────────────────────────────────────────────────────────┘

ALSO: ui/app.py  — the original all-in-one **Streamlit** app (still works, port 8502).
It predates the React rewrite. The React+FastAPI stack is the primary/demo UI now.
```

**Two UIs exist and both work.** The React app (served by FastAPI at `http://localhost:8000/`)
is the headline. The Streamlit app (`streamlit run ui/app.py --server.port 8502`) is a
legacy all-in-one that still passes its headless tests. Keep both working.

---

## 3. Run it

```powershell
# Windows PowerShell
cd $env:USERPROFILE\Desktop\v
# venv is at .\venv (Python 3.11). ALWAYS set UTF-8 on this Windows console.
$env:PYTHONUTF8=1; $env:PYTHONIOENCODING="utf-8"; $env:HF_HUB_OFFLINE=1; $env:TRANSFORMERS_OFFLINE=1
```
```bash
# Mac/Linux bash
cd ~/Desktop/v
export PYTHONUTF8=1 PYTHONIOENCODING="utf-8" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
```

# --- React command center (recommended) ---
# Build once:
# cd frontend && npm install && npm run build && cd ..

# Run backend (Windows):
.\venv\Scripts\python.exe -m uvicorn backend.main:app --port 8000
# Run backend (Mac/Linux):
./venv/bin/python -m uvicorn backend.main:app --port 8000
#   open http://localhost:8000/   (UI at /, API at /api/*, docs at /docs)
#   frontend hot-reload dev: cd frontend && npm run dev  (proxies /api to :8000)

# --- OR the all-in-one Streamlit app ---
# Windows: .\venv\Scripts\python.exe -m streamlit run ui\app.py --server.port 8502
# Mac/Linux: ./venv/bin/python -m streamlit run ui/app.py --server.port 8502

# --- One-command offline narrated demo (no browser) ---
# Windows: .\venv\Scripts\python.exe -m tools.judge_demo
# Mac/Linux: ./venv/bin/python -m tools.judge_demo
```

**Gemini (optional, big accuracy boost):** put `GEMINI_API_KEY=...` in `.env` (already
gitignored, NEVER commit it). `backend/main.py` calls `load_dotenv()`, so the backend
picks it up → Vision uses real Gemini scene understanding + Knowledge uses grounded
Gemini synthesis. Without a key (or on any failure/rate-limit) everything **falls back
to the fully-offline path automatically**. That hybrid ("cloud-accurate when connected,
fully functional offline / air-gapped") is the strongest pitch — keep the fallback intact.

---

## 4. Test it (all must stay green)

```powershell
# Windows PowerShell
$env:PYTHONUTF8=1; $env:PYTHONIOENCODING="utf-8"; $env:HF_HUB_OFFLINE=1; $env:TRANSFORMERS_OFFLINE=1
.\venv\Scripts\python.exe -m pytest -q                       # ~139 tests
for($i=1;$i -le 16;$i++){ .\venv\Scripts\python.exe tools\accept.py ("T{0:D3}" -f $i) }  # 16 authoritative acceptance tasks
.\venv\Scripts\python.exe tools\ui_apptest.py                # headless Streamlit UI (8 tabs)
.\venv\Scripts\python.exe -m tools.benchmark                 # the compound-vs-single benchmark
cd frontend; npm run build                                   # frontend must build clean
```
```bash
# Mac/Linux bash
export PYTHONUTF8=1 PYTHONIOENCODING="utf-8" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
./venv/bin/python -m pytest -q
for i in {1..16}; do ./venv/bin/python tools/accept.py "T$(printf "%03d" $i)"; done
./venv/bin/python tools/ui_apptest.py
./venv/bin/python -m tools.benchmark
cd frontend && npm run build
```

Current status: **139 pytest + 16 acceptance all green.** Frontend builds clean
(~104 KB gzipped). Run the FULL suite after any change.

---

## 5. Core subsystems (what each does + gotchas)

### 5a. Contract — `schema.py` is IMMUTABLE
All dataclasses live here (`SensorReading`, `VisionResult`, `SafetyAlert`,
`ComplianceResult/Violation`, `KnowledgeResult`, `OrchestratorResult`, `*Input`). **Do
NOT add/modify dataclasses or add new `@dataclass` elsewhere.** Agents return these
types; the orchestrator converts loose dicts → typed inputs before calling agents.

### 5b. Compound risk — TWO models, used in different places (important!)
- **Rule engine** `agents/safety_agent.py` — the **EXACT** additive formula pinned in
  `CLAUDE.md §10` (`gas>50 +30`, `O2<19.5 +40`, `gas>50 & hot_work +50`, `gas>80 +30`,
  cap 100) **plus** documented additive escalations for vision, **maintenance-in-confined
  (+25)**, and **shift-changeover (+15)** (mirrors the pre-existing vision-escalation
  pattern; gated on explicit tokens so the pinned base + all tests are unchanged).
  This is the **auditable** score. The **benchmark uses this** (its integrity is the
  whole "compound-vs-single" proof). Tests assert exact values — do not change the base.
- **Graduated model** `utils/risk_model.py` — a **continuous** 0-100 risk where EVERY
  factor + interaction contributes smoothly (no threshold cliff), with a per-factor
  **contribution breakdown**. This is the **primary risk shown in the live UI**
  (`/api/scan` returns `risk_score` = graduated, plus `rule_score` = the auditable rule
  engine, plus `contributions`). Interventions on the dashboard also run against this
  model so deltas match. Built because the rule engine felt unresponsive live.

### 5c. The benchmark (PS1's headline evidence) — `tools/benchmark.py`
- `utils/scenario_generator.py` — generates **physics-labeled** time-series scenarios.
  **Ground truth is detector-independent**: incident = gas≥IDLH(100), OR O2<16 with
  workers, OR combustible gas + ignition(hot_work) + confined + workers, OR
  gas≥60 + confined + workers + O2<19.5 (maintenance/entrapment). Treats `gas_ppm` as
  **H2S** (uses `utils/exposure_calc` limits). Scenario kinds: conjunction_incident,
  maintenance_shift_incident, idlh_incident, asphyxiation_incident, safe_stable,
  safe_transient.
- `utils/baseline_detector.py` — single-sensor alarms, two profiles (evac-grade
  `high_alarm` and sensitive `low_alarm`) — the honest foil (miss-vs-alarm-fatigue).
- `utils/forecast.py` — predictive lead-time (extrapolate trajectory to thresholds).
- `tools/benchmark.py` — 4 detectors (single_high, single_low, compound, compound_pred),
  confusion matrix, **operational false-negatives** (a detection with less lead than the
  ~10-min evac window counts as a miss), median lead, per-scenario-kind breakdown.
  Result: single-sensor ~80% operational miss → ours ~0% on the benchmark; ~18-19 min
  lead; false alarms ~0-3%. **In the UI we show honest COUNTS (e.g. "21/26" vs "0/26")
  with a "real-world rates are non-zero" caveat — never a bare "0%".** No test-gaming:
  ground truth is physics, baselines are realistic, results stable across seeds.

### 5d. Vision — `agents/vision_agent.py`, `utils/gemini_vision.py`, `utils/local_vision.py`
- **Primary:** Gemini (`gemini_vision.analyze_image`) when `GEMINI_API_KEY` set — real
  multi-hazard scene understanding. It **caches the first working model** (avoids
  retrying all 5 models per call → that caused intermittent rate-limit fallbacks),
  extracts text robustly, and retries once on 429/quota.
- **Offline fallback:** `utils/local_vision.py` — OpenCV/NumPy. It detects **fire/smoke
  ONLY** (electrical/gas heuristics were REMOVED — they false-positived on any
  bright/hazy image). Fire is decided by a **trained logistic model**
  (`models/hazard_model.npz`, retrained by `models/train_hazard_model.py`) gated by fire
  pixel fraction + spatial concentration + a **warm-core** feature (a real flame has an
  orange-yellow core; red text/logos are pure red → not fire). Features are 22-d,
  standardized (mu/sigma saved in the npz). Trained on a **diverse synthetic dataset with
  hard negatives** (album gradients, red text/logos, warm-diffuse, colorful blobs, noise)
  so it does NOT flag random/album images. Held-out acc ~0.98. Verified: real flame →
  detected; red text/logo/banner, warm album, white, gray → none.
- `VisionAgent` returns Gemini result if `source=="gemini"`, else the offline result with
  the Gemini failure reason attached to `.error` so the UI can explain the fallback.
- **UI:** shows a source badge (🛰 Gemini / ⚙ Offline), the fallback *reason*, and
  formatted hazard cards with icons + confidence bars.

### 5e. Knowledge / RAG — `agents/knowledge_agent.py`, `knowledge_base/build_db.py`
- ChromaDB (`data/chroma_db`) + `all-MiniLM-L6-v2` embeddings. `build_db.py` ingests
  `knowledge_base/raw/*.pdf|*.txt|*.md` (markdown split by heading). The corpus is
  `knowledge_base/raw/safety_standards.md` (structured OISD/Factory Act/DGMS reference) +
  a synthetic PDF. **Rebuild after changing the corpus:** `python -m knowledge_base.build_db`.
- Answer: grounded **Gemini synthesis** if key + `KNOWLEDGE_LLM!=0`; else a **sentence-
  ranked extractive** answer (picks the most relevant sentences, honest "not directly
  addressed" note when overlap is weak). Backend **pre-warms** the RAG model in a
  background thread at startup so the first query is fast (not ~16s).

### 5f. Other engines
- `utils/knowledge_graph.py` — plant graph (zones·equipment·permits·adjacency); **permit-
  proximity intelligence**: flags ignition/intrusive permits in/adjacent to elevated-gas
  zones. Rendered as a labeled network + on the Leaflet map.
- `utils/incident_intelligence.py` + `knowledge_base/incidents.json` (18 near-miss
  records) — recurring severity-weighted **prevention priorities** + similar-incident
  retrieval.
- `utils/confidence.py` — assessment confidence (coverage / decisiveness / freshness).
- `utils/interventions.py` (rule-engine) and `risk_model.rank_interventions` (graduated) —
  counterfactual "which action most reduces risk" ranking.
- `utils/limit_check.py` — measured-vs-regulatory-limit utilisation (direction-aware).
- `agents/compliance_agent.py` + `compliance/safety_rules.json` — currently 20 deterministic rules (R001-R020), **each cross-referenced to OISD + Factory Act 1948 + DGMS**. New rules can be added as long as they follow this structure.
- `utils/audit_logger.py` — **tamper-evident SHA-256 hash-chained** evidence log with
  `verify_chain()` (legacy entries tolerated). Never logs secrets.
- `agents/output_agent.py` + `utils/translations.py` — multilingual (10 languages)
  briefing + evacuation messages. `utils/report_generator.py`, `evidence_export.py`.
- `utils/risk_banner.py`, `utils/safety_calendar.py`, `utils/response_directory.py`
  (facilities + coords), `utils/sensor_simulator.py`, `utils/zone_status.py`.

### 5g. Backend API — `backend/main.py`
`/api/health`, `/api/scan` (graduated risk + rule_score + contributions + compliance +
confidence + interventions + limits + single_sensor compare), `/api/zones` (colors +
conflicts + graph + coords + facilities), `/api/forecast`, `/api/incidents`,
`/api/benchmark`, `/api/audit/verify`, `/api/audit/events`, `/api/knowledge`,
`/api/vision` (multipart), `/api/exposure`, `/api/gases`, `/api/languages`,
`/api/briefing`, `/api/dispatch` (returns localized + english_message), `/api/facilities`.
Serves the React build at `/` and `/assets`. Light imports at top; heavy (torch/chromadb/
vision) lazy-loaded. Tests: `tests/test_backend_api.py`.

### 5h. Frontend — `frontend/src/`
`App.jsx` (shell, 8 tabs, shared sensor state, i18n provider, Dashboard + LiveStream),
`tabs.jsx` (ZoneMap[Leaflet], Knowledge[chat+localStorage], Vision[upload+camera],
Emergency[voice], Tools, Intelligence[incidents+audit+pipeline], Benchmark),
`api.js`, `lib.jsx` (band/gauge), `voice.js` (robust TTS — prefers LOCAL voices, Chrome
`resume()`, chunks long text, optimistic start so English never falsely reports
"no voice", English falls back to default voice, English fallback when a language voice
is absent), `i18n.js` (English/Hindi/Telugu shell translation), `index.css`. Deps kept
minimal: react, vite, leaflet. Stable page (no ambient motion). `npm run build` → `dist/`.

---

## 6. Environment quirks (WILL bite you — see also `CLAUDE.md`)
- **Windows console:** always `$env:PYTHONUTF8=1; $env:PYTHONIOENCODING="utf-8"` before
  running Python (non-ASCII crashes cp1252).
- **HuggingFace offline:** MiniLM is cached → set `HF_HUB_OFFLINE=1; TRANSFORMERS_OFFLINE=1`
  to avoid multi-second hub HEAD hangs / offline crashes.
- **Python 3.11** venv required (chromadb/chroma-hnswlib have no 3.13 wheels + need MSVC).
- **ChromaDB SQLite lock:** don't run the full pytest suite while a UI is serving and
  holding `data/chroma_db` — it can crash. Stop servers before rebuilding the KB.
- **`create` tool won't overwrite** — `Remove-Item` first (if regenerating files).
- **Detached servers get reaped** when the CLI turn/session ends — relaunch as needed.
- **OneDrive-synced folder:** use Vite (`npm run build`/`preview`), fine; avoid Next.js
  Turbopack HMR (file-in-use errors) — not used here.
- **Stop a process:** `Stop-Process -Id <PID>` (name-based kills are blocked).

---

## 7. Git / security policy (STRICT)
- **Push ONLY** to the personal remote whose URL contains `thirumani-vihaan`
  (`v-hackathon`). A `.git/hooks/pre-push` hook enforces this (allows only that URL).
  Never add/modify other remotes.
- **Commit identity:** author as **`thirumani-vihaan` / `arjunthirumani02@gmail.com`**
  (set in repo-local git config). **Do NOT add a `Co-authored-by: Copilot` trailer** —
  the user wants commits attributed only to their profile.
- **Commit + push after each feature/update** (user preference), not just at the end.
- **`.env` is gitignored and must stay untracked** — it holds `GEMINI_API_KEY`. Never
  commit secrets; the audit logger sanitizes secrets; never print the key.
- **No other-project names anywhere** (README/code/comments/commit messages). The repo
  was scrubbed of comparisons to "AgriBloom" etc. — keep it standalone.

---

## 8. Contracts & rules to respect (from CLAUDE.md)
1. `schema.py` immutable; no new dataclasses; agents return schema dataclasses.
2. Orchestrator LangGraph nodes return **update dicts only**; `route_`-prefixed node names
   (must not collide with state keys); compile once, invoke per request.
3. **ComplianceAgent stays deterministic** (no LLM). Rules must be hardcoded and deterministic.
4. **No test-gaming** — real generalizing logic; the benchmark ground truth is physics.
5. Agents never let exceptions escape — return a valid dataclass with `.error` set.
6. The pinned compound-scoring base (CLAUDE.md §10) must keep producing the exact values
   the tests assert; add only clearly-gated *additive escalations* (as done).

---

## 9. Competitive landscape (for the re-scan before deadline)
The user plans to re-analyze competitor repos near the deadline and integrate new ideas.
When re-scanning other PS1 repositories, focus purely on technical architecture and patterns to learn from:
- Watch for teams using sophisticated causal models or agent-variance novelty signals.
- Check if others are employing genuine real-time computer vision models.
- Look out for how others approach offline RAG capabilities.
- Note any strong UI/UX choices, particularly in geospatial visualization.

**Patterns we have successfully adopted from others:** 
- Evidence/uncertainty score ideas (adapted into our confidence engine).
- SHA-256 chained audit logs.
- Structured citation formatting.
- Measured-vs-limit charts for easy reading.

Our strategic focus remains on real AI depth, robust testing, offline viability, the physics-based benchmark, and high-performance UI (React + warm FastAPI). Integrate any genuinely superior patterns discovered near the deadline.

---

## 10. What's been done (iteration history, newest first)
Warm FastAPI backend + React SPA (full feature parity, one URL) → graduated risk model →
Leaflet map + voice + camera + live predictive stream + Intelligence tab → chat
persistence + RAG prewarm → tamper-evident audit → confidence engine → counterfactual
interventions + compound-vs-single panel → benchmark (physics-labeled) → knowledge graph,
incident intelligence, tri-framework compliance, geospatial heatmap → vision model
retrained (accurate, no false positives) → Gemini vision+RAG enabled via `.env` →
vision UI polish + benchmark methodology/honest counts. All committed to
`thirumani-vihaan/v-hackathon`.

## 11. What to do NEXT (roadmap)
**Non-code (highest priority — you're feature-complete):**
1. Record the **demo video** and build the **slide deck** — script + outline in
   `docs/pitch_deck_and_demo.md`. Lead with Vizag → live compound risk → benchmark →
   Gemini vision → multilingual voice; then pull the network to show it works OFFLINE.
2. Rehearse the 60-sec judge walkthrough + prepared Q&A (same file).
3. Pre-demo: start backend, confirm `.env` key, do one warm-up scan (warms Gemini+RAG),
   have a real hazard photo + a random photo ready.

**Optional code (only if it clearly helps, no bloat):**
- Re-scan competitors near deadline; integrate any genuinely superior pattern.
- Deploy to a live URL if judges want one (offline story is stronger, so optional).
- Possible depth adds: incident-pattern RAG over a larger corpus, knowledge-graph
  conflicts written to the audit trail on the live pipeline, Factory Act/DGMS rule
  expansion (keep count logic if you touch the 20-rule assertion).

## 12. Known limitations (be honest with judges)
- Offline vision detects **fire/smoke only** (accurately). Full multi-hazard (PPE, person,
  equipment) needs the Gemini key. This is by design (color heuristics were unreliable).
- All sensor/scenario/incident data is **synthetic** (offline, no downloads); ground truth
  is physics-based and documented — say so openly.
- Benchmark numbers are on a synthetic test set; real-world rates are non-zero (UI says so).
- Two frontends (React + Streamlit) — slight redundancy; React is the headline.

---

## 13. Key files index
```
backend/main.py            FastAPI (serves React + all /api endpoints)
frontend/src/{App,tabs,api,lib,voice,i18n}.{jsx,js}   React SPA
schema.py                  IMMUTABLE dataclass contract
agents/{orchestrator,safety_agent,compliance_agent,knowledge_agent,vision_agent,output_agent}.py
utils/{risk_model,scenario_generator,baseline_detector,forecast,confidence,interventions,
       limit_check,knowledge_graph,incident_intelligence,local_vision,gemini_vision,
       audit_logger,translations,exposure_calc,response_directory,risk_banner,...}.py
models/train_hazard_model.py  -> models/hazard_model.npz   (offline fire model)
knowledge_base/build_db.py + raw/safety_standards.md + incidents.json
compliance/safety_rules.json  (20 rules, tri-framework refs)
tools/{benchmark,judge_demo,accept,ui_apptest}.py
tests/test_*.py            (~139 pytest)   CLAUDE.md  (engineering contract)
docs/pitch_deck_and_demo.md  (deck outline + demo script + Q&A)
ui/app.py                  legacy Streamlit app (port 8502)
.env                       GEMINI_API_KEY (gitignored — NEVER commit)
```

**Start by running the app + the tests, read `CLAUDE.md`, then this file's §5 for any
subsystem you touch. Respect §7 (git) and §8 (contracts). Keep everything green and keep
the offline fallback intact.**
