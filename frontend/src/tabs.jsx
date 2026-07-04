import React, { useEffect, useState } from "react";
import { api } from "./api";

const readingOf = (r) => ({ gas_ppm: r.gas_ppm, temp_c: r.temp_c, oxygen_pct: r.oxygen_pct, humidity_pct: r.humidity_pct, worker_count: r.worker_count, zone: r.zone, permit_type: r.permit_type });
const FILL = { red: "rgba(231,76,60,0.25)", orange: "rgba(230,126,34,0.2)", green: "rgba(46,204,113,0.14)" };
const STROKE = { red: "#e74c3c", orange: "#e67e22", green: "#2ecc71" };
const LABEL = { red: "CRITICAL", orange: "ELEVATED", green: "NOMINAL" };

const POS = {
  "Zone-A-Tank-Farm": { x: 40, y: 40, w: 210, h: 120 },
  "Zone-B-Process": { x: 205, y: 150, w: 190, h: 130 },
  "Zone-D-Substation": { x: 360, y: 40, w: 200, h: 110 },
  "Zone-C-Confined": { x: 360, y: 205, w: 200, h: 120 },
};
const center = (z) => ({ cx: POS[z].x + POS[z].w / 2, cy: POS[z].y + POS[z].h / 2 });

export function ZoneMapTab({ r, permits }) {
  const [d, setD] = useState(null);
  useEffect(() => { api.zones(r.gas_ppm, r.oxygen_pct, r.humidity_pct, permits).then(setD).catch(() => setD(null)); }, [r, permits]);
  if (!d) return <div className="card sub">Loading plant state…</div>;
  const edges = d.graph.edges.filter((e) => e.relation === "adjacent" && POS[e.source] && POS[e.target]);
  return (
    <div className="grid">
      <div className="col">
        <div className="card">
          <h3>Facility Risk Map</h3>
          <svg className="plant" viewBox="0 0 600 360">
            {edges.map((e, i) => { const a = center(e.source), b = center(e.target);
              return <line key={i} x1={a.cx} y1={a.cy} x2={b.cx} y2={b.cy} stroke="rgba(150,170,200,0.25)" strokeDasharray="5 5" />; })}
            {Object.entries(d.colors).map(([z, c]) => { const p = POS[z]; if (!p) return null;
              return (<g key={z}>
                <rect x={p.x} y={p.y} width={p.w} height={p.h} rx="10" fill={FILL[c]} stroke={STROKE[c]} strokeWidth="2" />
                <text x={p.x + 12} y={p.y + 24} fill="#e6ecf5" fontSize="13" fontWeight="600">{z}</text>
                <text x={p.x + 12} y={p.y + 44} fill={STROKE[c]} fontSize="12" fontFamily="monospace">{LABEL[c]}</text>
              </g>); })}
          </svg>
          <div className="sub" style={{ marginTop: 8 }}>Dashed lines = spatial adjacency. Colors update live from the Dashboard controls.</div>
        </div>
      </div>
      <div className="col">
        <div className="card">
          <h3>Permit-Proximity Intelligence (knowledge graph)</h3>
          <div className="sub" style={{ marginBottom: 8 }}>Flags ignition/intrusive permits in a zone that is — or is adjacent to — a zone with elevated gas.</div>
          {d.conflicts.length ? d.conflicts.map((c, i) => (
            <div className={`conflict ${c.severity}`} key={i}><b>{c.severity}</b> — {c.message}</div>
          )) : <div className="sub">No permit-proximity conflicts for the current plant state.</div>}
        </div>
        <div className="card">
          <h3>Graph relationships</h3>
          <div className="sub">{d.graph.nodes.length} nodes · {d.graph.edges.length} edges (zones · equipment · permits · adjacency)</div>
        </div>
      </div>
    </div>
  );
}

export function KnowledgeTab() {
  const [q, setQ] = useState("When must a hot work permit be cancelled?");
  const [hist, setHist] = useState([]);
  const [loading, setLoading] = useState(false);
  const ask = async () => {
    if (!q.trim()) return;
    setLoading(true);
    try { const res = await api.knowledge(q);
      setHist((h) => [...h, { q, ...res }]); setQ("");
    } catch { setHist((h) => [...h, { q, answer: "Backend error (first call loads the RAG model; retry in a moment).", sources: [], confidence: 0 }]); }
    setLoading(false);
  };
  return (
    <div className="card" style={{ maxWidth: 900, margin: "0 auto" }}>
      <h3>Grounded Safety Knowledge (RAG over OISD / Factory Act / DGMS)</h3>
      <div className="chat">
        {hist.map((m, i) => (<React.Fragment key={i}>
          <div className="msg q">{m.q}</div>
          <div className="msg a">{m.answer}
            <div className="cite">confidence {(m.confidence || 0).toFixed(2)} · sources: {(m.sources || []).map((s) => `${s.filename} p.${s.page}`).join(", ") || "none"} · {m.answered_from_documents ? "grounded in documents" : "general knowledge"}</div>
          </div></React.Fragment>))}
        {loading && <div className="msg a sub">Retrieving & synthesizing… (first query loads the embedding model)</div>}
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <input type="text" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && ask()} placeholder="Ask a safety question…" />
        <button className="btn primary" onClick={ask} disabled={loading}>Ask</button>
      </div>
    </div>
  );
}

export function VisionTab() {
  const [img, setImg] = useState(null);
  const [res, setRes] = useState(null);
  const [loading, setLoading] = useState(false);
  const onFile = async (f) => {
    if (!f) return;
    setImg(URL.createObjectURL(f)); setRes(null); setLoading(true);
    try { setRes(await api.vision(f)); } catch { setRes({ error: "vision failed", hazards: [] }); }
    setLoading(false);
  };
  return (
    <div className="grid">
      <div className="col">
        <div className="card">
          <h3>Upload CCTV / Site Image</h3>
          <label className="dropzone">
            {img ? "Change image" : "Click to upload a JPG/PNG — offline OpenCV hazard detection"}
            <input type="file" accept="image/*" style={{ display: "none" }} onChange={(e) => onFile(e.target.files[0])} />
          </label>
          {img && <div className="imgwrap" style={{ marginTop: 14 }}>
            <img src={img} alt="upload" />
            {res && res.hazards && res.hazards.map((h, i) => {
              const [x1, y1, x2, y2] = h.bbox;
              return <div key={i} className="bbox" style={{ left: `${x1}%`, top: `${y1}%`, width: `${x2 - x1}%`, height: `${y2 - y1}%` }}>
                <span>{h.type} {(h.confidence * 100).toFixed(0)}%</span></div>;
            })}
          </div>}
        </div>
      </div>
      <div className="col">
        <div className="card">
          <h3>Detected Hazards</h3>
          {loading && <div className="sub">Analyzing…</div>}
          {res && !loading && <>
            <div className="sub" style={{ marginBottom: 8 }}>Source: {res.source} · {res.summary}</div>
            {res.hazards && res.hazards.length ? res.hazards.map((h, i) => (
              <div className="list-item" key={i}><b>{h.type.replace("_", " ")}</b> <span className="muted">— confidence {(h.confidence * 100).toFixed(0)}%</span></div>
            )) : <div className="sub">No hazards detected.</div>}
          </>}
          {!res && !loading && <div className="sub">Upload an image to run detection.</div>}
        </div>
      </div>
    </div>
  );
}

export function EmergencyTab({ r, permits }) {
  const [langs, setLangs] = useState(["English"]);
  const [lang, setLang] = useState("Telugu");
  const [disp, setDisp] = useState(null);
  const [brief, setBrief] = useState(null);
  useEffect(() => { api.languages().then((l) => setLangs(l)).catch(() => {}); }, []);
  const run = async () => {
    const rd = readingOf(r);
    setDisp(await api.dispatch(rd, permits, lang).catch(() => null));
    setBrief(await api.briefing(rd, permits, lang).catch(() => null));
  };
  return (
    <div className="grid">
      <div className="col">
        <div className="card">
          <h3>Emergency Response Orchestrator</h3>
          <div className="ctrl"><label>Alert language</label>
            <select value={lang} onChange={(e) => setLang(e.target.value)}>{langs.map((l) => <option key={l}>{l}</option>)}</select></div>
          <button className="btn primary" onClick={run} style={{ width: "100%" }}>🚨 Simulate Dispatch & Briefing</button>
          <div className="sub" style={{ marginTop: 10 }}>Uses the current Dashboard sensor state ({r.zone}, gas {r.gas_ppm} ppm).</div>
        </div>
      </div>
      <div className="col">
        {disp && <div className="card">
          <h3>Multilingual Evacuation Alert · {disp.severity}</h3>
          <div className="banner-warn" style={{ color: "#ffd8d3" }}>{disp.message}</div>
          <div className="sub" style={{ marginTop: 10 }}>Dispatched via: {disp.channels.join(" · ")} · logged to tamper-evident audit trail.</div>
        </div>}
        {brief && <div className="card"><h3>Incident Briefing (voice-ready)</h3>
          <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit", fontSize: 12.5, margin: 0, lineHeight: 1.6 }}>{brief.briefing}</pre></div>}
        {!disp && <div className="card sub">Run a dispatch to generate the multilingual alert and briefing.</div>}
      </div>
    </div>
  );
}

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
          <h3>Exposure & Ventilation Calculator</h3>
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
