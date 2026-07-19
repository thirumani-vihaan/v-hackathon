# Minute-by-Minute Demo Script

This script is designed for a strict 4-minute hackathon presentation. It details exactly what to say, what to click in the UI, and how to trigger live proofs to preempt judge skepticism.

## Pre-Flight Checklist (Do this 5 minutes before demo)
1. Start backend: `./venv/bin/python -m uvicorn backend.main:app --port 8000`
2. Open React UI at `http://localhost:8000`
3. Have a terminal window open and visible side-by-side with the browser (to show the LangGraph agent trace).
4. Pre-load the **Benchmark** tab.

---

## 0:00 - 0:45 | The Hook & The Problem
**Visual**: Browser open to the Benchmark tab.

**Speaker**: "At the Visakhapatnam Steel Plant, the gas detectors worked. The permits were filed. The SCADA system was online. Eight people still died because nothing connected those signals in time. We built the missing intelligence layer: a compound-risk platform that fuses sensors, vision, and shift logs in real-time."

**Action**: Point to the Benchmark table.
**Speaker**: "If you tune a single sensor to avoid nuisance alarms, it misses 80% of compound incidents operationally. If you tune it to be sensitive, it false-alarms 100% of the time, causing alarm fatigue. We built a physics-labeled benchmark that proves our compound predictive engine drops that 80% miss rate to exactly 0%, with a median early warning of 18 minutes."

## 0:45 - 1:30 | The Live Trace & Agent Proof
**Visual**: Switch to the **Dashboard** tab. Ensure terminal is visible.

**Action**: Click the "Apply Vizag Critical Preset" button, then click "Run Scan".
**Speaker**: "Let's run a live scenario. A hot work permit is active, and gas is creeping up but still below the high alarm."

**Action**: Gesturing to the terminal output where LangGraph tool calls are printing.
**Speaker**: "This isn't just an LLM wrapper. Watch the terminal. You are seeing our 5-agent LangGraph ReAct loop autonomously query the edge TSDB, cross-reference the OISD safety manual via RAG, and compute the structural risk score. It has instantly identified a CRITICAL violation and ranked the exact counterfactual interventions."

## 1:30 - 2:30 | Live Actuation & Fallback
**Visual**: Switch to the **Emergency** tab.

**Action**: Click "Simulate Dispatch". 
*(The browser will play the voice alert)*
**Speaker**: "Within seconds, it orchestrates a multilingual evacuation alert and logs a tamper-evident, hash-chained audit record. It doesn't just monitor; it actuates."

**Action**: Switch to the **Vision** tab.
**Speaker**: "And if the cloud goes down? Our architecture degrades gracefully. We trained a custom PyTorch Vision Transformer (ViT) head that runs 100% locally on the edge. Even if the Gemini API rate-limits or the plant loses Wi-Fi, the safety loop never breaks."

## 2:30 - 3:30 | Preempting the Judges (The Live Proof)
**Visual**: Open a new terminal tab (or split pane).

**Speaker**: "We know you see a lot of 'AI demos' that fall apart outside the happy path. You might wonder if our scoring engine just hallucinates escalations. Let's run a stress test live."

**Action**: In the terminal, run: `curl -X POST http://localhost:8000/api/stress-test?trials=100`
**Speaker**: "I just hit our stress-test API to generate 100 random zero-context anomalies—extreme temperatures and humidity, but safe gas and no permits. Because we implemented a strict structural hard gate in code before the graduated model, you can see the false escalation rate is exactly 0%."

## 3:30 - 4:00 | The Moat & The Close (₹ Impact)
**Visual**: Switch back to the **Benchmark** tab, scroll to the ₹ Impact.

**Speaker**: "Every feature you saw—from the TSDB to the custom PyTorch head and the LangGraph pipeline—was built entirely during this hackathon sprint. 
But more importantly, our 80-point reduction in false negatives translates to roughly ₹50,00,000 in incident cost avoidance and compliance liability per prevented event.
IndustrialSafetyAI isn't a demo; it is a production-shaped platform built for zero-harm operations. Thank you."
