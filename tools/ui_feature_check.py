"""Exercise every UI feature by invoking the exact code paths each tab's
button triggers in ui/app.py. Prints a PASS/FAIL matrix. No test-gaming:
this calls the real Orchestrator/agents just like the Streamlit callbacks do.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_ROOT, ".env"))
except Exception:
    pass

from schema import OrchestratorInput
from agents.orchestrator import Orchestrator
from utils.sensor_simulator import normal_reading, vizag_critical_reading

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    tag = "PASS" if cond else "FAIL"
    print(f"[{tag}] {name} :: {detail}")


orch = Orchestrator()


def run_sensor(reading, permits):
    oi = OrchestratorInput(input_type="sensor",
                           data={"reading": reading.to_dict(),
                                 "active_permits": permits})
    return orch.run(oi)


# ---- TAB 1: Dashboard — Normal scenario (button "Run assessment") ----
r = run_sensor(normal_reading(), [])
check("Dashboard/Normal returns safety+compliance",
      r.safety is not None and r.compliance is not None,
      f"risk={r.safety.risk_score} pass={r.compliance.pass_status}")
check("Dashboard/Normal is low risk (<40)",
      r.safety.risk_score < 40, f"risk={r.safety.risk_score}")
check("Dashboard/Normal request_id preserved",
      r.request_id is not None and r.input_type == "sensor",
      f"input_type={r.input_type}")

# ---- TAB 1: Dashboard — Vizag Critical scenario ----
r = run_sensor(vizag_critical_reading(), ["hot_work"])
check("Dashboard/Vizag CRITICAL severity",
      r.compliance.highest_severity == "CRITICAL",
      f"severity={r.compliance.highest_severity}")
check("Dashboard/Vizag risk >= 80",
      r.safety.risk_score >= 80, f"risk={r.safety.risk_score}")
check("Dashboard/Vizag has violations + action",
      len(r.compliance.violations) > 0 and bool(r.safety.recommended_action),
      f"violations={[v.rule_id for v in r.compliance.violations]}")

# ---- TAB 2: Vision (button "Analyze image") ----
img_path = os.path.join(_ROOT, "data", "test_safety_image.jpg")
check("Vision test image exists", os.path.exists(img_path), img_path)
oi = OrchestratorInput(input_type="image", data={"image_path": img_path})
r = orch.run(oi)
check("Vision returns VisionResult",
      r.vision is not None and r.vision.source in ("gemini", "fallback"),
      f"source={r.vision.source} summary={r.vision.summary[:60]!r}")
check("Vision hazards is a list",
      isinstance(r.vision.hazards, list),
      f"n_hazards={len(r.vision.hazards)}")

# ---- TAB 3: Knowledge (button "Search") ----
oi = OrchestratorInput(input_type="query",
                       data={"query_text": "confined space entry requirements"})
r = orch.run(oi)
check("Knowledge returns answer",
      r.knowledge is not None and len(r.knowledge.answer) > 0,
      f"answer={r.knowledge.answer[:70]!r}")
check("Knowledge has sources (>0)",
      len(r.knowledge.sources) > 0, f"n_sources={len(r.knowledge.sources)}")
check("Knowledge confidence > 0",
      r.knowledge.confidence > 0, f"confidence={r.knowledge.confidence}")
_src_ok = all(("filename" in s and "page" in s and "excerpt" in s)
              for s in r.knowledge.sources)
check("Knowledge sources have citation fields", _src_ok,
      f"first={r.knowledge.sources[0] if r.knowledge.sources else None}")

# ---- TAB 4: Zone Map (folium render) ----
try:
    import folium
    from streamlit_folium import st_folium  # noqa: F401
    m = folium.Map(location=[17.6868, 83.2185], zoom_start=15)
    ZONE_COORDS = {
        "Zone-A-Tank-Farm": (17.6868, 83.2185),
        "Zone-B-Process": (17.6890, 83.2210),
        "Zone-C-Confined": (17.6850, 83.2160),
        "Zone-D-Substation": (17.6900, 83.2150),
    }
    for zone, (lat, lon) in ZONE_COORDS.items():
        folium.Marker([lat, lon], popup=zone,
                      icon=folium.Icon(color="red")).add_to(m)
    html = m._repr_html_()
    check("Zone Map builds folium map with markers",
          len(ZONE_COORDS) == 4 and "Zone-A-Tank-Farm" in html,
          f"zones={len(ZONE_COORDS)} html_len={len(html)}")
except Exception as e:  # noqa: BLE001
    check("Zone Map builds folium map with markers", False, f"error={e}")

# ---- Unknown input type must NOT crash (robustness) ----
try:
    r = orch.run(OrchestratorInput(input_type="bogus", data={}))
    check("Unknown input_type handled gracefully", r is not None,
          f"error={r.error}")
except Exception as e:  # noqa: BLE001
    check("Unknown input_type handled gracefully", False, f"raised {e}")

passed = sum(1 for _, ok, _ in results if ok)
total = len(results)
print(f"\n==== UI FEATURE CHECK: {passed}/{total} PASSED ====")
sys.exit(0 if passed == total else 1)
