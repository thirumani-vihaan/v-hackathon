"""Streamlit UI for IndustrialSafetyAI — 4 tabs + folium map."""
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

import streamlit as st  # noqa: E402

from schema import OrchestratorInput  # noqa: E402
from agents.orchestrator import Orchestrator  # noqa: E402
from utils.sensor_simulator import (  # noqa: E402
    normal_reading, vizag_critical_reading,
)

st.set_page_config(page_title="IndustrialSafetyAI", layout="wide")

ZONE_COORDS = {
    "Zone-A-Tank-Farm": (17.6868, 83.2185),
    "Zone-B-Process": (17.6890, 83.2210),
    "Zone-C-Confined": (17.6850, 83.2160),
    "Zone-D-Substation": (17.6900, 83.2150),
}


@st.cache_resource
def get_orchestrator():
    return Orchestrator()


def _run_sensor(reading, permits):
    orch = get_orchestrator()
    oi = OrchestratorInput(input_type="sensor",
                           data={"reading": reading.to_dict(),
                                 "active_permits": permits})
    return orch.run(oi)


st.title("🛡️ IndustrialSafetyAI")
st.caption("Multi-agent industrial safety monitoring — vision, compliance, "
           "risk scoring and knowledge RAG.")

tab_dash, tab_vision, tab_knowledge, tab_map = st.tabs(
    ["Dashboard", "Vision", "Knowledge", "Zone Map"])

with tab_dash:
    st.subheader("Sensor Safety Assessment")
    scenario = st.selectbox("Scenario", ["Normal", "Vizag Critical"])
    reading = normal_reading() if scenario == "Normal" else vizag_critical_reading()
    permits = [] if scenario == "Normal" else ["hot_work"]
    if st.button("Run assessment"):
        result = _run_sensor(reading, permits)
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Risk score", f"{result.safety.risk_score}/100")
            st.write("**Action:**", result.safety.recommended_action)
            st.write("**Triggered:**", result.safety.triggered_rules)
        with c2:
            st.write("**Compliance pass:**", result.compliance.pass_status)
            st.write("**Highest severity:**", result.compliance.highest_severity)
            for v in result.compliance.violations:
                st.write(f"- `{v.rule_id}` {v.severity}: {v.name}")

with tab_vision:
    st.subheader("Vision Hazard Inspection")
    img_path = os.path.join(_ROOT, "data", "test_safety_image.jpg")
    if os.path.exists(img_path):
        st.image(img_path, caption="Test safety image", width=360)
    if st.button("Analyze image"):
        orch = get_orchestrator()
        oi = OrchestratorInput(input_type="image",
                               data={"image_path": img_path})
        result = orch.run(oi)
        st.write("**Source:**", result.vision.source)
        st.write("**Summary:**", result.vision.summary)
        for h in result.vision.hazards:
            st.write(f"- {h.type} (confidence {h.confidence:.2f})")

with tab_knowledge:
    st.subheader("Safety Knowledge Base (RAG)")
    q = st.text_input("Ask a safety question",
                      "confined space entry requirements")
    if st.button("Search"):
        orch = get_orchestrator()
        oi = OrchestratorInput(input_type="query", data={"query_text": q})
        result = orch.run(oi)
        st.write("**Answer:**", result.knowledge.answer)
        st.write("**Confidence:**", result.knowledge.confidence)
        for s in result.knowledge.sources:
            st.write(f"- {s.get('filename')} p.{s.get('page')}: "
                     f"{s.get('excerpt')[:160]}...")

with tab_map:
    st.subheader("Facility Zone Map")
    try:
        import folium
        from streamlit_folium import st_folium
        m = folium.Map(location=[17.6868, 83.2185], zoom_start=15)
        for zone, (lat, lon) in ZONE_COORDS.items():
            folium.Marker([lat, lon], popup=zone,
                          icon=folium.Icon(color="red")).add_to(m)
        st_folium(m, width=700, height=450)
    except Exception as e:  # noqa: BLE001
        st.warning(f"Map unavailable: {e}")
