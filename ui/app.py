"""Streamlit UI for IndustrialSafetyAI.

Five tabs: Dashboard (dynamic sensors + live stream + trend + time-to-critical),
Vision (upload + bounding-box overlay), Knowledge (grounded RAG with citations),
Zone Map (plant-layout overlay + live risk colors), Emergency Dispatch
(multilingual evacuation simulation). Every orchestrator call is written to the
evidence/audit trail.
"""
import os
import sys
import json
import time
import tempfile
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_ROOT, ".env"))
except Exception:
    pass

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from schema import OrchestratorInput, SensorReading  # noqa: E402
from agents.orchestrator import Orchestrator  # noqa: E402
from utils.audit_logger import append_event, event_from_result, read_last_n  # noqa: E402
from utils.evidence_export import export_zip  # noqa: E402
from utils.report_generator import generate_pdf_report  # noqa: E402
from utils.vision_overlay import draw_hazards  # noqa: E402
from utils.zone_status import zone_colors, time_to_critical, ZONES  # noqa: E402
from utils.plant_layout import ensure_plant_layout  # noqa: E402
from utils import translations  # noqa: E402
from utils import exposure_calc, safety_calendar, response_directory, voice  # noqa: E402
from utils.voice import speak_html  # noqa: E402
from agents.output_agent import OutputAgent  # noqa: E402
import streamlit.components.v1 as components  # noqa: E402

_OUTPUT_AGENT = OutputAgent()

st.set_page_config(page_title="IndustrialSafetyAI", layout="wide")

ZONE_COORDS = {
    "Zone-A-Tank-Farm": (17.6868, 83.2185),
    "Zone-B-Process": (17.6890, 83.2210),
    "Zone-C-Confined": (17.6850, 83.2160),
    "Zone-D-Substation": (17.6900, 83.2150),
}

PRESETS = {
    "Normal": dict(gas=8.0, temp=32.0, oxy=20.9, hum=50.0, workers=2,
                   zone="Zone-A-Tank-Farm", permit="general", permits=[]),
    "Vizag Critical": dict(gas=120.0, temp=41.0, oxy=18.4, hum=70.0, workers=4,
                           zone="Zone-A-Tank-Farm", permit="hot_work",
                           permits=["hot_work"]),
    "Confined Space": dict(gas=15.0, temp=30.0, oxy=18.9, hum=55.0, workers=1,
                           zone="Zone-C-Confined", permit="confined_space",
                           permits=["confined_space"]),
    "Electrical Humidity": dict(gas=10.0, temp=34.0, oxy=20.8, hum=92.0, workers=2,
                                zone="Zone-D-Substation", permit="electrical",
                                permits=["electrical"]),
}
PERMIT_TYPES = ["general", "hot_work", "confined_space", "electrical", "cold_work",
                "inspection", "none"]
ALL_PERMITS = ["hot_work", "confined_space", "electrical", "cold_work"]


@st.cache_resource
def get_orchestrator():
    return Orchestrator()


def run_and_audit(oi, sensor=None, active_permits=None,
                  event_type="orchestrator", extra=None):
    orch = get_orchestrator()
    result = orch.run(oi)
    try:
        append_event(event_from_result(result, sensor=sensor,
                                        active_permits=active_permits,
                                        event_type=event_type, extra=extra))
    except Exception:
        pass
    return result


def run_sensor(reading: SensorReading, permits):
    oi = OrchestratorInput(input_type="sensor",
                           data={"reading": reading.to_dict(),
                                 "active_permits": permits})
    return run_and_audit(oi, sensor=reading.to_dict(), active_permits=permits,
                         event_type="sensor_scan")


def reading_from_state() -> SensorReading:
    return SensorReading(
        gas_ppm=float(st.session_state["d_gas"]),
        temp_c=float(st.session_state["d_temp"]),
        oxygen_pct=float(st.session_state["d_oxy"]),
        humidity_pct=float(st.session_state["d_hum"]),
        permit_type=st.session_state["d_permit"],
        worker_count=int(st.session_state["d_workers"]),
        zone=st.session_state["d_zone"],
        timestamp=datetime.utcnow().isoformat(),
        rescue_team_present=st.session_state.get("d_rescue", True),
    )


# ---- header / sidebar ----
st.title("🛡️ IndustrialSafetyAI")
st.caption("Multi-agent industrial safety — vision, deterministic compliance, "
           "compound risk scoring, grounded knowledge RAG, live dispatch.")

# 24x7 helpline banner (always visible).
st.markdown(
    f"<div style='background:#b71c1c;color:#fff;padding:8px 14px;border-radius:6px;"
    f"font-weight:600;text-align:center'>📞 {response_directory.helpline_banner()}"
    f"</div>", unsafe_allow_html=True)

with st.sidebar:
    st.header("System")
    _key = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    st.write("Gemini:", "🟢 configured" if _key else "🔴 not set (safe fallback)")
    _offline = os.environ.get("OFFLINE_MODE", "0") == "1" or not _key
    st.write("Mode:", "🟠 OFFLINE (local CV + RAG)" if _offline
             else "🟢 ONLINE (Gemini available)")
    import os.path as _op
    st.write("Local hazard model:",
             "🟢 trained" if _op.isfile(_op.join(_ROOT, "models", "hazard_model.npz"))
             else "—")
    st.write("Knowledge LLM:",
             "on" if os.environ.get("KNOWLEDGE_LLM", "1") not in ("0",) else "off")
    st.divider()
    st.subheader("Evidence trail")
    _recent = read_last_n(5)
    st.write(f"{len(read_last_n(10000))} events logged")
    if st.button("Download Evidence ZIP", key="side_zip"):
        zp = export_zip()
        try:
            with open(zp, "rb") as f:
                st.download_button("Save evidence_package.zip", f.read(),
                                   file_name="evidence_package.zip",
                                   mime="application/zip", key="side_zip_dl")
        except Exception as e:  # noqa: BLE001
            st.warning(f"ZIP unavailable: {e}")

tab_dash, tab_vision, tab_knowledge, tab_map, tab_dispatch, tab_tools = st.tabs(
    ["Dashboard", "Vision", "Knowledge", "Zone Map", "Emergency Dispatch",
     "Safety Tools"])

# session init
for k, v in dict(d_gas=8.0, d_temp=32.0, d_oxy=20.9, d_hum=50.0, d_workers=2,
                 d_zone="Zone-A-Tank-Farm", d_permit="general", d_rescue=True).items():
    st.session_state.setdefault(k, v)
st.session_state.setdefault("d_permits", [])
st.session_state.setdefault("risk_history", [])
st.session_state.setdefault("stream_rows", [])
st.session_state.setdefault("last_result", None)


# ============================================================
# DASHBOARD
# ============================================================
with tab_dash:
    st.subheader("Sensor Safety Assessment")

    top = st.columns([2, 1, 1])
    with top[0]:
        preset = st.selectbox("Preset scenario", list(PRESETS.keys()))
    with top[1]:
        if st.button("Apply preset"):
            p = PRESETS[preset]
            st.session_state.update({
                "d_gas": p["gas"], "d_temp": p["temp"], "d_oxy": p["oxy"],
                "d_hum": p["hum"], "d_workers": p["workers"], "d_zone": p["zone"],
                "d_permit": p["permit"], "d_permits": p["permits"]})
            st.rerun()
    with top[2]:
        if st.button("Reset history"):
            st.session_state["risk_history"] = []
            st.session_state["stream_rows"] = []
            st.rerun()

    c1, c2 = st.columns(2)
    with c1:
        st.slider("Gas (ppm)", 0.0, 200.0, key="d_gas", step=1.0)
        st.slider("Temperature (°C)", 0.0, 60.0, key="d_temp", step=0.5)
        st.slider("Oxygen (%)", 0.0, 25.0, key="d_oxy", step=0.1)
    with c2:
        st.slider("Humidity (%)", 0.0, 100.0, key="d_hum", step=1.0)
        st.number_input("Worker count", 0, 50, key="d_workers", step=1)
        st.selectbox("Zone", list(ZONE_COORDS.keys()), key="d_zone")

    c3, c4 = st.columns(2)
    with c3:
        st.selectbox("Primary permit_type", PERMIT_TYPES, key="d_permit")
    with c4:
        st.multiselect("Active permits", ALL_PERMITS, key="d_permits")
    st.checkbox("Rescue team present", key="d_rescue")

    with st.expander("Advanced: edit raw JSON payload"):
        default_json = json.dumps({
            "reading": reading_from_state().to_dict(),
            "active_permits": st.session_state["d_permits"],
        }, indent=2)
        txt = st.text_area("Sensor payload", value=default_json, height=240,
                           key="d_json")
        if st.button("Apply JSON"):
            try:
                obj = json.loads(txt)
                rd = obj.get("reading", obj)
                _r = SensorReading(**rd)  # validates against schema
                st.session_state.update({
                    "d_gas": _r.gas_ppm, "d_temp": _r.temp_c, "d_oxy": _r.oxygen_pct,
                    "d_hum": _r.humidity_pct, "d_workers": _r.worker_count,
                    "d_zone": _r.zone if _r.zone in ZONE_COORDS else "Zone-A-Tank-Farm",
                    "d_permit": _r.permit_type if _r.permit_type in PERMIT_TYPES
                    else "general",
                    "d_permits": obj.get("active_permits", []),
                    "d_rescue": _r.rescue_team_present})
                st.success("Applied JSON payload.")
                st.rerun()
            except Exception as e:  # noqa: BLE001
                st.error(f"Invalid payload: {e}")

    st.divider()
    run_cols = st.columns([1, 1, 2])
    with run_cols[0]:
        run_once = st.button("▶ Run once", type="primary")
    with run_cols[1]:
        run_live = st.button("⏱ Run live stream")
    with run_cols[2]:
        duration = st.slider("Live duration (s)", 5, 60, 15, step=5)

    result_box = st.container()
    metric_ph = st.empty()
    chart_ph = st.empty()

    def render_result(result, reading):
        st.session_state["last_result"] = result
        st.session_state["risk_history"].append(result.safety.risk_score)
        with result_box:
            m = st.columns(4)
            m[0].metric("Risk score", f"{result.safety.risk_score}/100")
            m[1].metric("Compliance",
                        "PASS" if result.compliance.pass_status else "FAIL")
            m[2].metric("Severity", result.compliance.highest_severity or "none")
            eta = time_to_critical(st.session_state["risk_history"])
            eta_txt = ("0 min (CRITICAL)" if eta == 0.0
                       else "—" if eta is None else f"{eta} min")
            m[3].metric("Time to critical", eta_txt)
            st.write("**Recommended action:**",
                     result.safety.recommended_action)
            st.write("**Triggered rules:**", result.safety.triggered_rules or "none")
            st.write("**request_id:**", f"`{result.request_id}`")
            if result.compliance.violations:
                st.write("**Compliance violations:**")
                for v in result.compliance.violations:
                    st.write(f"- `{v.rule_id}` {v.severity} — {v.name} "
                             f"({v.oisd_reference})")

    if run_once:
        reading = reading_from_state()
        res = run_sensor(reading, st.session_state["d_permits"])
        render_result(res, reading)

    if run_live:
        import random
        st.session_state["stream_rows"] = []
        base = reading_from_state()
        permits = list(st.session_state["d_permits"])
        for tick in range(int(duration)):
            drift = 1.0 + tick * 0.05
            live = SensorReading(
                gas_ppm=max(0.0, base.gas_ppm * drift + random.uniform(-2, 4)),
                temp_c=base.temp_c + random.uniform(-0.5, 0.8),
                oxygen_pct=max(0.0, min(25.0, base.oxygen_pct - tick * 0.03)),
                humidity_pct=base.humidity_pct,
                permit_type=base.permit_type,
                worker_count=base.worker_count,
                zone=base.zone,
                timestamp=datetime.utcnow().isoformat(),
                rescue_team_present=base.rescue_team_present)
            res = run_sensor(live, permits)
            st.session_state["risk_history"].append(res.safety.risk_score)
            st.session_state["stream_rows"].append(
                {"t": tick, "risk": res.safety.risk_score,
                 "gas": round(live.gas_ppm, 1), "oxygen": live.oxygen_pct})
            df = pd.DataFrame(st.session_state["stream_rows"]).set_index("t")
            eta = time_to_critical(st.session_state["risk_history"])
            eta_txt = ("0 min (CRITICAL)" if eta == 0.0
                       else "rising…" if eta is None else f"{eta} min")
            with metric_ph.container():
                mm = st.columns(3)
                mm[0].metric("Live risk", f"{res.safety.risk_score}/100")
                mm[1].metric("Gas ppm", f"{live.gas_ppm:.0f}")
                mm[2].metric("Time to critical", eta_txt)
            chart_ph.line_chart(df[["risk"]])
            time.sleep(1)
        st.session_state["last_result"] = res
        st.success(f"Live stream complete ({duration}s).")

    if st.session_state["risk_history"]:
        st.line_chart(pd.DataFrame({"risk": st.session_state["risk_history"]}))

    st.divider()
    ev_cols = st.columns(2)
    with ev_cols[0]:
        if st.button("📄 Generate PDF incident package"):
            res = st.session_state.get("last_result")
            if res is None:
                st.warning("Run an assessment first.")
            else:
                out = os.path.join(_ROOT, "data",
                                   f"incident_{res.request_id[:8]}.pdf")
                generate_pdf_report(res, out)
                append_event({"type": "pdf_report", "request_id": res.request_id,
                              "path": os.path.basename(out)})
                with open(out, "rb") as f:
                    st.download_button("Download incident PDF", f.read(),
                                       file_name=os.path.basename(out),
                                       mime="application/pdf")
    with ev_cols[1]:
        if st.button("🗜 Build & download Evidence ZIP", key="dash_zip"):
            zp = export_zip()
            with open(zp, "rb") as f:
                st.download_button("Download evidence_package.zip", f.read(),
                                   file_name="evidence_package.zip",
                                   mime="application/zip", key="dash_zip_dl")


# ============================================================
# VISION
# ============================================================
with tab_vision:
    st.subheader("Vision Hazard Inspection")
    up = st.file_uploader("Upload a site photo (jpg/png)",
                          type=["jpg", "jpeg", "png"])
    sample = os.path.join(_ROOT, "data", "test_safety_image.jpg")

    if up is not None:
        suffix = os.path.splitext(up.name)[1] or ".jpg"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(up.getbuffer())
        tmp.close()
        img_path = tmp.name
        st.caption(f"Analyzing uploaded image: {up.name}")
    else:
        img_path = sample
        if os.path.exists(sample):
            st.caption("No upload — using bundled sample image.")

    if st.button("Analyze image", type="primary"):
        oi = OrchestratorInput(input_type="image", data={"image_path": img_path})
        result = run_and_audit(oi, event_type="vision_scan")
        v = result.vision
        cols = st.columns([3, 2])
        with cols[0]:
            try:
                overlay = draw_hazards(img_path, v.hazards)
                st.image(overlay, caption="Detected hazards", width='stretch')
            except Exception as e:  # noqa: BLE001
                st.warning(f"Overlay failed: {e}")
                if os.path.exists(img_path):
                    st.image(img_path, width='stretch')
        with cols[1]:
            st.write("**Source:**", v.source)
            st.write("**Summary:**", v.summary)
            st.write("**request_id:**", f"`{result.request_id}`")
            if v.hazards:
                st.write("**Hazards:**")
                for h in v.hazards:
                    st.write(f"- {h.type} — confidence {h.confidence:.2f}")
            else:
                st.info("No hazards detected (or model uncertain).")
            if v.error:
                st.caption(f"note: {v.error}")


# ============================================================
# KNOWLEDGE
# ============================================================
with tab_knowledge:
    st.subheader("Safety Knowledge Base (grounded RAG)")
    q = st.text_input("Ask a safety question", "confined space entry requirements")
    dbg = st.checkbox("Show retrieval debug (raw chunks)")
    if st.button("Search", type="primary"):
        if dbg:
            os.environ["KNOWLEDGE_DEBUG"] = "1"
        else:
            os.environ.pop("KNOWLEDGE_DEBUG", None)
        oi = OrchestratorInput(input_type="query", data={"query_text": q})
        result = run_and_audit(oi, event_type="knowledge_query",
                               extra={"question": q})
        k = result.knowledge
        st.write("**Answer:**", k.answer)
        conf_cols = st.columns(2)
        conf_cols[0].metric("Confidence", f"{k.confidence:.2f}")
        conf_cols[1].write(f"**request_id:** `{result.request_id}`")
        st.write("**Sources / citations:**")
        if not k.sources:
            st.info("No local citations (see answer).")
        for s in k.sources:
            st.markdown(f"- **{s.get('filename')}** p.{s.get('page')}: "
                        f"{s.get('excerpt', '')[:220]}…")
            if dbg and s.get("chunk_preview"):
                st.caption(f"chunk: {s['chunk_preview']}")


# ============================================================
# ZONE MAP
# ============================================================
with tab_map:
    st.subheader("Facility Zone Map — live risk overlay")
    last = st.session_state.get("last_result")
    # derive current context from last result's audit event or defaults
    ctx_gas = float(st.session_state.get("d_gas", 8.0))
    ctx_oxy = float(st.session_state.get("d_oxy", 20.9))
    ctx_hum = float(st.session_state.get("d_hum", 50.0))
    ctx_permits = list(st.session_state.get("d_permits", []))
    colors = zone_colors(ctx_gas, ctx_oxy, ctx_hum, ctx_permits)

    st.caption(f"Colors from current controls — gas={ctx_gas:.0f} ppm, "
               f"O₂={ctx_oxy:.1f}%, humidity={ctx_hum:.0f}%, "
               f"permits={ctx_permits or 'none'}")
    try:
        import folium
        from streamlit_folium import st_folium

        layout_path = ensure_plant_layout()
        lats = [c[0] for c in ZONE_COORDS.values()]
        lons = [c[1] for c in ZONE_COORDS.values()]
        pad = 0.004
        bounds = [[min(lats) - pad, min(lons) - pad],
                  [max(lats) + pad, max(lons) + pad]]
        m = folium.Map(location=[17.6870, 83.2185], zoom_start=15,
                       tiles="OpenStreetMap")
        try:
            folium.raster_layers.ImageOverlay(
                image=layout_path, bounds=bounds, opacity=0.45,
                interactive=False, cross_origin=False).add_to(m)
        except Exception:
            pass
        for zone, (lat, lon) in ZONE_COORDS.items():
            col = colors.get(zone, "green")
            folium.Marker(
                [lat, lon],
                popup=f"{zone}: {col.upper()}",
                icon=folium.Icon(color=col, icon="info-sign")).add_to(m)

        legend = (
            '<div style="position: fixed; bottom: 30px; left: 30px; z-index:9999; '
            'background: white; padding: 8px 12px; border:1px solid #666; '
            'border-radius:6px; font-size:13px;">'
            '<b>Risk legend</b><br>'
            '🟢 Green — normal<br>🟠 Orange — elevated<br>🔴 Red — critical</div>')
        m.get_root().html.add_child(folium.Element(legend))
        st_folium(m, width=760, height=480)
    except Exception as e:  # noqa: BLE001
        st.warning(f"Map unavailable: {e}")

    df_zone = pd.DataFrame(
        [{"zone": z, "status": colors[z].upper()} for z in ZONES])
    st.table(df_zone)


# ============================================================
# EMERGENCY DISPATCH
# ============================================================
with tab_dispatch:
    st.subheader("Emergency Dispatch")
    contacts = [
        {"role": "CISF Control Room", "contact": "+91-891-XX  100"},
        {"role": "Fire & Rescue", "contact": "+91-891-XX  101"},
        {"role": "Medical / Ambulance", "contact": "+91-891-XX  108"},
        {"role": "Chief Safety Officer", "contact": "+91-98XX-XX-XX10"},
    ]
    st.write("**Contact directory**")
    st.table(pd.DataFrame(contacts))

    st.write("**Channels**")
    ch = st.columns(4)
    channels = []
    if ch[0].checkbox("SMS", value=True):
        channels.append("SMS")
    if ch[1].checkbox("Email", value=True):
        channels.append("Email")
    if ch[2].checkbox("PA System", value=True):
        channels.append("PA System")
    if ch[3].checkbox("WhatsApp", value=False):
        channels.append("WhatsApp")

    lang = st.selectbox("Message language", list(translations.LANGUAGES.keys()))

    last = st.session_state.get("last_result")
    if last is not None and last.compliance is not None:
        severity = last.compliance.highest_severity
        zone = (last.safety.zone if last.safety else "Zone-A-Tank-Farm")
        req_id = last.request_id
    else:
        severity, zone, req_id = None, "Zone-A-Tank-Farm", "(run a scan first)"

    st.write(f"Current severity: **{severity or 'unknown'}** "
             f"(zone {zone}, request_id `{req_id}`)")

    if st.button("🚨 Simulate Dispatch", type="primary"):
        # ensure we have a real critical context to demonstrate
        if severity != "CRITICAL":
            crit = run_sensor(
                SensorReading(gas_ppm=120, temp_c=41, oxygen_pct=18.4,
                              humidity_pct=70, permit_type="hot_work",
                              worker_count=4, zone="Zone-A-Tank-Farm",
                              timestamp=datetime.utcnow().isoformat()),
                ["hot_work"])
            severity = crit.compliance.highest_severity
            zone = crit.safety.zone
            req_id = crit.request_id
            st.info("No CRITICAL scan in session — generated a Vizag critical "
                    "scenario to demonstrate dispatch.")

        message, msrc = translations.translate_evac(lang, zone, req_id,
                                                     use_gemini=True)
        st.write(f"**Evacuation message ({lang}, via {msrc}):**")
        st.success(message)
        components.html(speak_html(message, lang,
                                   label=f"🔊 Speak alert ({lang})"), height=70)
        st.write("**Simulated channel payloads:**")
        for c in channels or ["SMS"]:
            st.code(f"[{c}] severity={severity} zone={zone} "
                    f"request_id={req_id}\n{message}", language="text")
        append_event({
            "type": "dispatch_simulation",
            "request_id": req_id,
            "zone": zone,
            "severity": severity,
            "language": lang,
            "channels": channels or ["SMS"],
            "message_source": msrc,
        })
        st.caption("Logged to evidence trail as dispatch_simulation.")


# ============================================================
# SAFETY TOOLS  (exposure calculator, seasonal calendar, response finder,
#                consolidated multilingual voice briefing)
# ============================================================
with tab_tools:
    st.subheader("🧰 Safety Tools")

    c1, c2 = st.columns(2)

    # ---- Industrial-hygiene exposure & ventilation calculator ----
    with c1:
        st.markdown("### Exposure & Ventilation Calculator")
        gas_key = st.selectbox(
            "Gas", list(exposure_calc.GASES.keys()),
            format_func=lambda k: exposure_calc.GASES[k]["name"])
        ppm = st.number_input("Measured concentration (ppm)", 0.0, 100000.0,
                              120.0, step=1.0)
        vol = st.number_input("Space volume (m³)", 1.0, 100000.0, 100.0, step=10.0)
        ach = st.slider("Target air changes / hour", 1, 30, 12)
        if st.button("Compute exposure", type="primary"):
            rep = exposure_calc.full_report(gas_key, ppm, vol, ach)
            ex = rep["exposure"]
            badge = {"IDLH": "🔴", "FLAMMABLE": "🟠", "OVER_STEL": "🟠",
                     "OVER_PEL": "🟡", "OK": "🟢"}.get(ex["status"], "⚪")
            st.metric("Status", f"{badge} {ex['status']}")
            m = st.columns(3)
            m[0].metric("PEL ratio", f"{ex['pel_ratio']}×")
            m[1].metric("% of LEL", f"{rep['lel_percent']}%")
            m[2].metric("Evac radius", f"{rep['evacuation_radius_m']} m")
            st.write(f"Recommended ventilation: **{rep['recommended_ventilation_cfm']} "
                     f"CFM** (purge ≈ {rep['purge_time_min_at_recommended']} min).")
            for n in ex["notes"]:
                st.write("• " + n)
            append_event({"type": "exposure_calc", "gas": gas_key, "ppm": ppm,
                          "status": ex["status"],
                          "lel_percent": rep["lel_percent"]})

    # ---- Response-facility finder ----
    with c2:
        st.markdown("### Nearest Response Facilities")
        z = st.selectbox("From zone", list(response_directory.ZONE_COORDS.keys()))
        ftype = st.selectbox("Type", ["Any", "Hospital", "Fire", "Mutual-Aid",
                                      "Command"])
        near = response_directory.nearest_facilities(
            z, top_k=4, facility_type=None if ftype == "Any" else ftype)
        st.table(pd.DataFrame([
            {"Facility": f["name"], "Type": f["type"],
             "Distance (km)": f["distance_km"]} for f in near]))
        st.markdown("**On-site contacts**")
        st.table(pd.DataFrame(response_directory.CONTACTS))

    st.divider()

    # ---- Seasonal safety calendar ----
    st.markdown("### 📅 Seasonal Safety Calendar")
    months = ["January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December"]
    mi = st.selectbox("Month", months, index=datetime.now().month - 1)
    adv = safety_calendar.advisories_for(months.index(mi) + 1)
    st.write(f"Season: **{adv['season'].replace('_', ' ').title()}** — "
             f"{safety_calendar.shift_note()}")
    for a in adv["advisories"]:
        st.write("• " + a)

    st.divider()

    # ---- Consolidated multilingual voice briefing (OutputAgent) ----
    st.markdown("### 🗣️ Incident Briefing (OutputAgent, voice-ready)")
    last = st.session_state.get("last_result")
    if last is None:
        st.info("Run a Dashboard scan first to generate a briefing.")
    else:
        blang = st.selectbox("Briefing language",
                             list(translations.LANGUAGES.keys()), key="brief_lang")
        brief = _OUTPUT_AGENT.briefing(last, blang)
        st.text(brief)
        components.html(speak_html(brief, blang, label="🔊 Read briefing aloud"),
                        height=70)
        append_event({"type": "briefing", "request_id": last.request_id,
                      "language": blang,
                      "severity": _OUTPUT_AGENT.severity(last)})
