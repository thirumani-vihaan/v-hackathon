"""Headless UI smoke test using Streamlit's AppTest harness.

Runs ui/app.py without a browser, exercises each tab's primary button, and
asserts the script never raises. Keeps Gemini off for determinism/speed.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

os.environ["KNOWLEDGE_LLM"] = "0"      # deterministic extractive answers
os.environ.setdefault("GEMINI_API_KEY", "")  # force vision fallback, no network

from streamlit.testing.v1 import AppTest  # noqa: E402

APP = os.path.join(_ROOT, "ui", "app.py")
failures = []


def check(name, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    print(f"[{tag}] {name} :: {detail}")
    if not cond:
        failures.append(name)


def fresh():
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    return at


# 1) initial render, no exception, 5 tabs
at = fresh()
check("initial render no exception", not at.exception, str(at.exception))
check("has 5 tabs", len(at.tabs) == 5, f"tabs={len(at.tabs)}")

# 2) Dashboard: Run once
at = fresh()
btns = [b for b in at.button if "Run once" in (b.label or "")]
check("dashboard has Run once", len(btns) == 1)
if btns:
    btns[0].click().run()
    check("dashboard run once no exception", not at.exception, str(at.exception))
    check("dashboard produced metrics", len(at.metric) >= 1,
          f"metrics={len(at.metric)}")

# 3) Vision: Analyze image (fallback, no network)
at = fresh()
btns = [b for b in at.button if "Analyze image" in (b.label or "")]
check("vision has Analyze button", len(btns) == 1)
if btns:
    btns[0].click().run()
    check("vision analyze no exception", not at.exception, str(at.exception))

# 4) Knowledge: Search
at = fresh()
btns = [b for b in at.button if (b.label or "") == "Search"]
check("knowledge has Search", len(btns) == 1)
if btns:
    btns[0].click().run()
    check("knowledge search no exception", not at.exception, str(at.exception))

# 5) Dispatch: Simulate Dispatch (should generate critical + log)
at = fresh()
btns = [b for b in at.button if "Simulate Dispatch" in (b.label or "")]
check("dispatch has Simulate", len(btns) == 1)
if btns:
    btns[0].click().run()
    check("dispatch simulate no exception", not at.exception, str(at.exception))

# 6) Apply preset (Vizag) then Run once -> should be CRITICAL
at = fresh()
sel = [s for s in at.selectbox if "Preset" in (s.label or "")]
if sel:
    sel[0].select("Vizag Critical").run()
    ap = [b for b in at.button if (b.label or "") == "Apply preset"]
    if ap:
        ap[0].click().run()
    ro = [b for b in at.button if "Run once" in (b.label or "")]
    if ro:
        ro[0].click().run()
    check("preset+run no exception", not at.exception, str(at.exception))

print("\n==== UI APPTEST:",
      "ALL PASSED" if not failures else f"FAILURES: {failures}", "====")
sys.exit(0 if not failures else 1)
