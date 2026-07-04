import React, { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { api } from "./api";
import { speak, stopSpeaking, voiceInfo } from "./voice";

const readingOf = (r) => ({ gas_ppm: r.gas_ppm, temp_c: r.temp_c, oxygen_pct: r.oxygen_pct, humidity_pct: r.humidity_pct, worker_count: r.worker_count, zone: r.zone, permit_type: r.permit_type });
const HEX = { red: "#e74c3c", orange: "#e67e22", green: "#2ecc71" };
const LABEL = { red: "CRITICAL", orange: "ELEVATED", green: "NOMINAL" };

/* ---------------- Zone Map (real Leaflet) ---------------- */
function MapView({ colors, coords, facilities }) {
  const el = useRef(null), map = useRef(null), grp = useRef(null), me = useRef(null);
  useEffect(() => {
    if (!map.current && el.current) {
      map.current = L.map(el.current, { zoomControl: true }).setView([17.687, 83.218], 14);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        { maxZoom: 19, attribution: "© OpenStreetMap" }).addTo(map.current);
      map.current.on("locationfound", (e) => {
        if (me.current) me.current.remove();
        me.current = L.marker(e.latlng).addTo(map.current).bindPopup("You are here").openPopup();
      });
      setTimeout(() => map.current && map.current.invalidateSize(), 200);
    }
    if (grp.current) grp.current.remove();
    grp.current = L.layerGroup().addTo(map.current);
    Object.entries(coords || {}).forEach(([z, ll]) => {
      const c = colors[z] || "green";
      L.circle(ll, { radius: 130, color: HEX[c], fillColor: HEX[c], fillOpacity: 0.35, weight: 2 })
        .bindPopup(`<b>${z}</b><br>${LABEL[c]}`).addTo(grp.current);
    });
    (facilities || []).forEach((f) => {
      if (f.lat && f.lon)
        L.circleMarker([f.lat, f.lon], { radius: 6, color: "#22d3ee", fillColor: "#22d3ee", fillOpacity: 0.85, weight: 1 })
          .bindPopup(`<b>${f.name}</b><br>${f.type} · ${f.distance_km} km`).addTo(grp.current);
    });
  }, [colors, coords, facilities]);
  return (
    <div>
      <div ref={el} style={{ height: 460, borderRadius: 12, overflow: "hidden", border: "1px solid var(--border)" }} />
      <button className="btn" style={{ marginTop: 10 }} onClick={() => map.current && map.current.locate({ setView: true, maxZoom: 15 })}>📍 Auto-locate me</button>
    </div>
  );
}

export function ZoneMapTab({ r, permits }) {
  const [d, setD] = useState(null);
  useEffect(() => { api.zones(r.gas_ppm, r.oxygen_pct, r.humidity_pct, permits).then(setD).catch(() => setD(null)); }, [r, permits]);
  return (
    <div className="grid">
      <div className="col">
        <div className="card">
          <h3>Live Facility Risk Map · Visakhapatnam</h3>
          {d ? <MapView colors={d.colors} coords={d.coords} facilities={d.facilities} /> : <div className="sub">Loading map…</div>}
          <div className="sub" style={{ marginTop: 8 }}>Zone circles recolor live from Dashboard controls · cyan markers = nearest response facilities.</div>
        </div>
      </div>
      <div className="col">
        <div className="card">
          <h3>Permit-Proximity Intelligence</h3>
          <div className="sub" style={{ marginBottom: 8 }}>Ignition/intrusive permits in — or adjacent to — a zone with elevated gas.</div>
          {d && d.conflicts.length ? d.conflicts.map((c, i) => (
            <div className={`conflict ${c.severity}`} key={i}><b>{c.severity}</b> — {c.message}</div>
          )) : <div className="sub">{d ? "No permit-proximity conflicts for the current plant state." : ""}</div>}
        </div>
        {d && <div className="card"><h3>Zone Status</h3>
          {Object.entries(d.colors).map(([z, c]) => (
            <div className="cmp-row" key={z}><span className="cmp-tag">{z}</span>
              <span className="cmp-val" style={{ color: HEX[c] }}>{LABEL[c]}</span></div>))}
          <div className="sub" style={{ marginTop: 6 }}>{d.graph.nodes.length} graph nodes · {d.graph.edges.length} edges</div></div>}
      </div>
    </div>
  );
}

/* ---------------- Knowledge chat ---------------- */
export function KnowledgeTab() {
  const [q, setQ] = useState("When must a hot work permit be cancelled?");
  const [hist, setHist] = useState([]);
  const [loading, setLoading] = useState(false);
  const ask = async () => {
    if (!q.trim()) return;
    setLoading(true);
    try { const res = await api.knowledge(q); setHist((h) => [...h, { q, ...res }]); setQ(""); }
    catch { setHist((h) => [...h, { q, answer: "Backend error (first call loads the RAG model; retry in a moment).", sources: [], confidence: 0 }]); }
    setLoading(false);
  };
  return (
    <div className="card" style={{ maxWidth: 900, margin: "0 auto" }}>
      <h3>Grounded Safety Knowledge · RAG over OISD / Factory Act / DGMS</h3>
      <div className="chat">
        {hist.map((m, i) => (<React.Fragment key={i}>
          <div className="msg q">{m.q}</div>
          <div className="msg a">{m.answer}
            <div className="cite">confidence {(m.confidence || 0).toFixed(2)} · sources: {(m.sources || []).map((s) => `${s.filename} p.${s.page}`).join(", ") || "none"} · {m.answered_from_documents ? "grounded in documents" : "general knowledge"}
              {" · "}<a style={{ color: "var(--cyan)", cursor: "pointer" }} onClick={() => speak(m.answer, "English")}>🔊 read</a></div>
          </div></React.Fragment>))}
        {loading && <div className="msg a sub">Retrieving &amp; synthesizing… (first query loads the embedding model)</div>}
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <input type="text" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && ask()} placeholder="Ask a safety question…" />
        <button className="btn primary" onClick={ask} disabled={loading}>Ask</button>
      </div>
    </div>
  );
}

/* ---------------- Vision (upload + camera) ---------------- */
export function VisionTab() {
  const [img, setImg] = useState(null);
  const [res, setRes] = useState(null);
  const [loading, setLoading] = useState(false);
  const [cam, setCam] = useState(false);
  const video = useRef(null), stream = useRef(null);

  const analyze = async (file) => { setImg(URL.createObjectURL(file)); setRes(null); setLoading(true);
    try { setRes(await api.vision(file)); } catch { setRes({ error: "vision failed", hazards: [] }); } setLoading(false); };

  const openCam = async () => {
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      setCam(true);
      setTimeout(() => { if (video.current) { video.current.srcObject = stream.current; video.current.play(); } }, 100);
    } catch { alert("Camera unavailable or permission denied."); }
  };
  const closeCam = () => { if (stream.current) stream.current.getTracks().forEach((t) => t.stop()); setCam(false); };
  const capture = () => {
    const v = video.current; if (!v) return;
    const c = document.createElement("canvas"); c.width = v.videoWidth; c.height = v.videoHeight;
    c.getContext("2d").drawImage(v, 0, 0);
    c.toBlob((b) => { closeCam(); analyze(new File([b], "capture.jpg", { type: "image/jpeg" })); }, "image/jpeg", 0.9);
  };
  useEffect(() => () => closeCam(), []);

  return (
    <div className="card" style={{ maxWidth: 1000, margin: "0 auto" }}>
      <h3>Vision Hazard Inspection · offline OpenCV + trained model</h3>
      <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
        <label className="btn">⬆ Upload image<input type="file" accept="image/*" style={{ display: "none" }} onChange={(e) => e.target.files[0] && analyze(e.target.files[0])} /></label>
        {!cam ? <button className="btn" onClick={openCam}>📷 Open camera</button>
              : <><button className="btn primary" onClick={capture}>Capture</button><button className="btn" onClick={closeCam}>Cancel</button></>}
      </div>
      <div className="row2">
        <div>
          {cam && <video ref={video} style={{ width: "100%", borderRadius: 10, background: "#000" }} muted playsInline />}
          {!cam && img && <div className="imgwrap"><img src={img} alt="scan" />
            {res && res.hazards && res.hazards.map((h, i) => { const [x1, y1, x2, y2] = h.bbox;
              return <div key={i} className="bbox" style={{ left: `${x1}%`, top: `${y1}%`, width: `${x2 - x1}%`, height: `${y2 - y1}%` }}><span>{h.type} {(h.confidence * 100).toFixed(0)}%</span></div>; })}</div>}
          {!cam && !img && <div className="dropzone">Upload an image or open the camera to detect hazards.</div>}
        </div>
        <div>
          <h3>Detected Hazards</h3>
          {loading && <div className="sub">Analyzing…</div>}
          {res && !loading && <>
            <div className="sub" style={{ marginBottom: 8 }}>Source: {res.source} · {res.summary}</div>
            {res.hazards && res.hazards.length ? res.hazards.map((h, i) => (
              <div className="list-item" key={i}><b>{h.type.replace(/_/g, " ")}</b> <span className="muted">— confidence {(h.confidence * 100).toFixed(0)}%</span></div>
            )) : <div className="sub">No hazards detected.</div>}</>}
        </div>
      </div>
    </div>
  );
}

/* ---------------- Emergency (voice) ---------------- */
export function EmergencyTab({ r, permits }) {
  const [langs, setLangs] = useState(["English"]);
  const [lang, setLang] = useState("Telugu");
  const [disp, setDisp] = useState(null);
  const [brief, setBrief] = useState(null);
  useEffect(() => { api.languages().then(setLangs).catch(() => {}); }, []);
  const run = async () => {
    const rd = readingOf(r);
    const d = await api.dispatch(rd, permits, lang).catch(() => null);
    const b = await api.briefing(rd, permits, lang).catch(() => null);
    setDisp(d); setBrief(b);
    if (d && d.message) speak(d.message, lang);
  };
  return (
    <div className="grid">
      <div className="col">
        <div className="card">
          <h3>Emergency Response Orchestrator</h3>
          <div className="ctrl"><label>Alert language</label>
            <select value={lang} onChange={(e) => setLang(e.target.value)}>{langs.map((l) => <option key={l}>{l}</option>)}</select></div>
          <button className="btn primary" style={{ width: "100%" }} onClick={run}>🚨 Simulate Dispatch &amp; Speak Alert</button>
          <div className="sub" style={{ marginTop: 10 }}>Uses current sensor state ({r.zone}, gas {r.gas_ppm} ppm). Voice: {voiceInfo(lang)}.</div>
          <button className="btn" style={{ width: "100%", marginTop: 8 }} onClick={stopSpeaking}>⏹ Stop voice</button>
        </div>
      </div>
      <div className="col">
        {disp && <div className="card">
          <h3>Multilingual Evacuation Alert · {disp.severity}</h3>
          <div className="banner-warn" style={{ color: "#ffd8d3", fontSize: 14 }}>{disp.message}</div>
          <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
            <button className="btn" onClick={() => speak(disp.message, lang)}>🔊 Replay alert</button></div>
          <div className="sub" style={{ marginTop: 10 }}>Dispatched via {disp.channels.join(" · ")} · logged to tamper-evident audit trail.</div>
        </div>}
        {brief && <div className="card"><h3>Incident Briefing (voice-ready)</h3>
          <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit", fontSize: 12.5, margin: 0, lineHeight: 1.6 }}>{brief.briefing}</pre>
          <button className="btn" style={{ marginTop: 10 }} onClick={() => speak(brief.briefing, "English")}>🔊 Read briefing</button></div>}
        {!disp && <div className="card sub">Run a dispatch to generate and speak the multilingual alert.</div>}
      </div>
    </div>
  );
}

/* ---------------- Safety Tools ---------------- */
export function ToolsTab({ r }) {
  const [gases, setGases] = useState({ h2s: "Hydrogen Sulfide" });
  const [gas, setGas] = useState("h2s");
  const [ppm, setPpm] = useState(120);
  const [vol, setVol] = useState(100);
  const [ach, setAch] = useState(12);
  const [rep, setRep] = useState(null);
  const [fac, setFac] = useState(null);
  useEffect(() => { api.gases().then(setGases).catch(() => {}); api.facilities(r.zone).then(setFac).catch(() => {}); }, [r.zone]);
  const compute = async () => setRep(await api.exposure(gas, ppm, vol, ach).catch(() => null));
  useEffect(() => { compute(); }, []);
  const badge = { IDLH: "#e74c3c", FLAMMABLE: "#e67e22", OVER_STEL: "#e67e22", OVER_PEL: "#f1c40f", OK: "#2ecc71" };
  return (
    <div className="grid">
      <div className="col">
        <div className="card">
          <h3>Exposure &amp; Ventilation Calculator</h3>
          <div className="ctrl"><label>Gas</label><select value={gas} onChange={(e) => setGas(e.target.value)}>{Object.entries(gases).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
          <div className="ctrl"><label>Concentration (ppm)</label><input type="number" value={ppm} onChange={(e) => setPpm(parseFloat(e.target.value) || 0)} /></div>
          <div className="ctrl"><label>Space volume (m³)</label><input type="number" value={vol} onChange={(e) => setVol(parseFloat(e.target.value) || 1)} /></div>
          <div className="ctrl"><label>Target air changes / hr</label><input type="number" value={ach} onChange={(e) => setAch(parseFloat(e.target.value) || 1)} /></div>
          <button className="btn primary" style={{ width: "100%" }} onClick={compute}>Compute</button>
        </div>
      </div>
      <div className="col">
        {rep && <div className="card">
          <h3>Exposure Assessment</h3>
          <div style={{ marginBottom: 12 }}><span className="tag" style={{ background: `${badge[rep.exposure.status]}22`, color: badge[rep.exposure.status] }}>{rep.exposure.status}</span></div>
          <div className="metrics4">
            <div className="metric"><div className="v">{rep.exposure.pel_ratio}×</div><div className="l">PEL ratio</div></div>
            <div className="metric"><div className="v">{rep.lel_percent}%</div><div className="l">% of LEL</div></div>
            <div className="metric"><div className="v">{rep.evacuation_radius_m}m</div><div className="l">Evac radius</div></div>
            <div className="metric"><div className="v">{rep.recommended_ventilation_cfm}</div><div className="l">Vent CFM</div></div>
          </div>
          <div className="sub" style={{ marginTop: 10 }}>{rep.exposure.notes.join(" ")} Purge ≈ {rep.purge_time_min_at_recommended} min.</div>
        </div>}
        {fac && <div className="card">
          <h3>Nearest Response Facilities · from {r.zone}</h3>
          <table><thead><tr><th>Facility</th><th>Type</th><th>Distance</th></tr></thead>
            <tbody>{fac.nearest.map((f, i) => <tr key={i}><td>{f.name}</td><td>{f.type}</td><td className="mono">{f.distance_km} km</td></tr>)}</tbody></table>
        </div>}
      </div>
    </div>
  );
}

/* ---------------- Benchmark ---------------- */
export function BenchmarkTab() {
  const [b, setB] = useState(null);
  useEffect(() => { api.benchmark().then(setB).catch(() => setB(null)); }, []);
  if (!b) return <div className="card sub">Loading benchmark…</div>;
  const h = b.headline;
  const names = { single_high: "Single-sensor (evac-grade)", single_low: "Single-sensor (sensitive)", compound: "Compound (reactive)", compound_pred: "Compound + prediction (ours)" };
  const pc = (x) => (x == null ? "—" : `${Math.round(x * 100)}%`);
  return (
    <div className="col">
      <div className="row2">
        <div className="card">
          <h3>Headline: False-Negative Reduction</h3>
          <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
            <span className="big-num" style={{ color: "#2ecc71" }}>−{Math.round(h.false_negative_reduction_pct)}<span style={{ fontSize: 16 }}>pts</span></span>
            <span className="sub">missed incidents (operational)</span></div>
          <div className="cmp-row"><span className="cmp-tag">Single-sensor</span><span className="tag bad">{pc(h.single_sensor_operational_false_negative_rate)} miss</span></div>
          <div className="cmp-row"><span className="cmp-tag">Compound + prediction</span><span className="tag ok">{pc(h.compound_predictive_operational_false_negative_rate)} miss</span></div>
          <div className="cmp-row"><span className="cmp-tag">Median early warning</span><span className="cmp-val">{h.compound_median_lead_minutes} min</span></div>
          <div className="sub" style={{ marginTop: 6 }}>{b.incidents} incident / {b.safe} safe physics-labeled scenarios.</div>
        </div>
        <div className="card">
          <h3>Detector Comparison</h3>
          <table><thead><tr><th>Detector</th><th>Miss (op)</th><th>False alarm</th><th>Lead</th></tr></thead>
            <tbody>{Object.keys(names).map((k) => { const d = b.detectors[k]; return (
              <tr key={k}><td>{names[k]}</td><td className="mono">{pc(d.false_negative_rate_operational)}</td><td className="mono">{pc(d.false_alarm_rate)}</td><td className="mono">{d.median_lead_minutes ?? "—"}</td></tr>); })}</tbody></table>
        </div>
      </div>
      <div className="card">
        <h3>By Scenario Kind</h3>
        <table><thead><tr><th>Scenario</th><th>n</th><th>single (evac)</th><th>single (sensitive)</th><th>compound</th><th>ours</th></tr></thead>
          <tbody>{Object.entries(b.by_scenario_kind).map(([k, row]) => (
            <tr key={k}><td>{k} <span className="muted">({row.type})</span></td><td className="mono">{row.n}</td>
              <td className="mono">{pc(row.single_high)}</td><td className="mono">{pc(row.single_low)}</td><td className="mono">{pc(row.compound)}</td><td className="mono">{pc(row.compound_pred)}</td></tr>))}</tbody></table>
        <div className="sub" style={{ marginTop: 8 }}>Incident kinds = operational miss rate; safe kinds = false-alarm rate. Physics-defined ground truth, independent of the detector.</div>
      </div>
    </div>
  );
}

/* ---------------- Intelligence (incidents + audit + pipeline) ---------------- */
const AGENTS = [
  ["Vision", "image → hazards", "🖼️"],
  ["Safety", "compound risk 0-100", "⚠️"],
  ["Compliance", "20 rules · 3 frameworks", "📋"],
  ["Knowledge", "grounded RAG", "📚"],
  ["Output", "briefing + voice", "🔊"],
];
export function IntelligenceTab({ r, permits }) {
  const [inc, setInc] = useState(null);
  const [aud, setAud] = useState(null);
  useEffect(() => {
    api.incidents(r.gas_ppm, r.oxygen_pct, r.zone, permits).then(setInc).catch(() => {});
    api.auditEvents(15).then(setAud).catch(() => {});
  }, [r, permits]);
  return (
    <div className="col">
      <div className="card">
        <h3>5-Agent LangGraph Pipeline</h3>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {AGENTS.map(([n, d, e], i) => (
            <div key={n} style={{ flex: 1, minWidth: 150, background: "var(--panel2)", border: "1px solid var(--border)", borderRadius: 10, padding: 12 }}>
              <div style={{ fontSize: 20 }}>{e}</div>
              <div style={{ fontWeight: 600, fontSize: 13, marginTop: 4 }}>{n}Agent</div>
              <div className="sub">{d}</div>
              <div className="tag ok" style={{ marginTop: 6 }}>● ready</div>
            </div>))}
        </div>
        <div className="sub" style={{ marginTop: 8 }}>Orchestrator routes each input; nodes return update-only state; a failing agent never crashes the run.</div>
      </div>
      <div className="row2">
        <div className="card">
          <h3>Incident Pattern Intelligence {inc && `· ${inc.count} records`}</h3>
          {inc ? <>
            <div className="sub" style={{ marginBottom: 6 }}>Recurring prevention priorities:</div>
            {inc.priorities.slice(0, 4).map((p, i) => <div className="list-item" key={i}>• {p}</div>)}
            {inc.similar && <>
              <div className="sub" style={{ margin: "10px 0 6px" }}>Similar to current state:</div>
              {inc.similar.map((m) => <div className="list-item" key={m.id}><b>{m.id}</b> <span className="muted">({m.severity}, match {m.match_score})</span> — {m.description}</div>)}
            </>}
          </> : <div className="sub">Loading…</div>}
        </div>
        <div className="card">
          <h3>Tamper-Evident Audit Trail</h3>
          {aud ? <>
            <div className="cmp-row"><span className="cmp-tag">Chain integrity</span>
              <span className="cmp-val" style={{ color: aud.chain.valid ? "#2ecc71" : "#e74c3c" }}>{aud.chain.valid ? "INTACT" : "BROKEN"} · {aud.chain.chained} linked</span></div>
            <div className="sub" style={{ margin: "8px 0 6px" }}>Recent events (SHA-256 chained):</div>
            <table><thead><tr><th>Type</th><th>Detail</th><th>Time</th></tr></thead>
              <tbody>{aud.events.slice(0, 8).map((e, i) => (
                <tr key={i}><td>{e.type}</td>
                  <td className="sub">{e.risk_score != null ? `risk ${e.risk_score}` : e.severity || e.zone || e.language || "—"}</td>
                  <td className="sub">{(e.timestamp || "").slice(11, 19)}</td></tr>))}</tbody></table>
          </> : <div className="sub">Loading…</div>}
        </div>
      </div>
    </div>
  );
}
