import React, { useEffect, useRef, useState } from "react";
import { api } from "./api";
import { band, pctColor, Gauge } from "./lib.jsx";
import { ZoneMapTab, KnowledgeTab, VisionTab, EmergencyTab, ToolsTab, BenchmarkTab } from "./tabs.jsx";

export const ALL_PERMITS = ["hot_work", "confined_space", "maintenance", "electrical", "shift_changeover", "cold_work"];
export const ZONES = ["Zone-A-Tank-Farm", "Zone-B-Process", "Zone-C-Confined", "Zone-D-Substation"];
const PRESETS = {
  Nominal: { gas_ppm: 8, temp_c: 30, oxygen_pct: 20.9, humidity_pct: 50, worker_count: 2, zone: "Zone-A-Tank-Farm", permit_type: "general", permits: [] },
  "Vizag Critical": { gas_ppm: 120, temp_c: 41, oxygen_pct: 18.4, humidity_pct: 70, worker_count: 4, zone: "Zone-C-Confined", permit_type: "hot_work", permits: ["hot_work"] },
  "Confined Maint.": { gas_ppm: 72, temp_c: 33, oxygen_pct: 18.9, humidity_pct: 66, worker_count: 3, zone: "Zone-C-Confined", permit_type: "confined_space", permits: ["maintenance", "shift_changeover", "confined_space"] },
};
const TABS = ["Dashboard", "Zone Map", "Knowledge", "Vision", "Emergency", "Safety Tools", "Benchmark"];

export default function App() {
  const [tab, setTab] = useState("Dashboard");
  const [r, setR] = useState(PRESETS["Vizag Critical"]);
  const [permits, setPermits] = useState(PRESETS["Vizag Critical"].permits);
  const [online, setOnline] = useState(true);

  useEffect(() => {
    const id = setInterval(() => api.health().then(() => setOnline(true)).catch(() => setOnline(false)), 5000);
    api.health().then(() => setOnline(true)).catch(() => setOnline(false));
    return () => clearInterval(id);
  }, []);

  const set = (k, v) => setR((p) => ({ ...p, [k]: v }));
  const togglePermit = (p) => setPermits((prev) => (prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]));
  const applyPreset = (name) => { const p = PRESETS[name]; setR(p); setPermits(p.permits); };
  const shared = { r, set, permits, togglePermit, applyPreset };

  return (
    <div className="app">
      <div className="topbar">
        <div className="brand">
          <div className="logo">🛡️</div>
          <div><h1>IndustrialSafetyAI</h1><p>Zero-Harm Command Center</p></div>
        </div>
        <div className="pills">
          <span className="pill">offline · deterministic</span>
          <span className="pill live"><span className="dot" style={{ background: online ? "#2ecc71" : "#e74c3c" }} />{online ? "BACKEND LIVE" : "BACKEND DOWN"}</span>
        </div>
      </div>
      <div className="wrap">
        <div className="tabs">
          {TABS.map((t) => <button key={t} className={t === tab ? "on" : ""} onClick={() => setTab(t)}>{t}</button>)}
        </div>
        {tab === "Dashboard" && <Dashboard {...shared} />}
        {tab === "Zone Map" && <ZoneMapTab r={r} permits={permits} />}
        {tab === "Knowledge" && <KnowledgeTab />}
        {tab === "Vision" && <VisionTab />}
        {tab === "Emergency" && <EmergencyTab r={r} permits={permits} />}
        {tab === "Safety Tools" && <ToolsTab r={r} />}
        {tab === "Benchmark" && <BenchmarkTab />}
        <div className="footer">Warm FastAPI backend · real multi-agent AI · fully offline · 131 automated tests</div>
      </div>
    </div>
  );
}

function Dashboard({ r, set, permits, togglePermit, applyPreset }) {
  const [scan, setScan] = useState(null);
  const [err, setErr] = useState(null);
  const [latency, setLatency] = useState(null);
  const t = useRef(null);

  useEffect(() => {
    if (t.current) clearTimeout(t.current);
    t.current = setTimeout(async () => {
      const reading = { gas_ppm: r.gas_ppm, temp_c: r.temp_c, oxygen_pct: r.oxygen_pct, humidity_pct: r.humidity_pct, worker_count: r.worker_count, zone: r.zone, permit_type: r.permit_type };
      try {
        const t0 = performance.now();
        const s = await api.scan(reading, permits);
        setLatency(Math.round(performance.now() - t0));
        setScan(s); setErr(null);
      } catch (e) { setErr("Backend unreachable — start: uvicorn backend.main:app --port 8000"); }
    }, 140);
    return () => clearTimeout(t.current);
  }, [r, permits]);

  const b = band(scan ? scan.risk_score : 0);
  return (
    <div className="grid">
      <div className="col">
        <Controls r={r} set={set} permits={permits} togglePermit={togglePermit} applyPreset={applyPreset} PRESETS={PRESETS} />
      </div>
      <div className="col">
        {err && <div className="card err">{err}</div>}
        <RiskHero scan={scan} b={b} latency={latency} />
        {scan && <div className="row2"><CompoundCompare scan={scan} /><Confidence conf={scan.confidence} /></div>}
        {scan && <div className="row2"><Interventions iv={scan.interventions} /><Limits limits={scan.limits} /></div>}
        {scan && <Violations comp={scan.compliance} />}
      </div>
    </div>
  );
}

function Controls({ r, set, permits, togglePermit, applyPreset, PRESETS }) {
  const Slider = ({ k, label, min, max, step, unit }) => (
    <div className="ctrl">
      <label>{label}<b>{r[k]}{unit}</b></label>
      <input type="range" min={min} max={max} step={step} value={r[k]} onChange={(e) => set(k, parseFloat(e.target.value))} />
    </div>
  );
  return (
    <div className="card">
      <h3>Sensor & Permit Controls</h3>
      <div className="preset-row">
        {Object.keys(PRESETS).map((n) => <button key={n} onClick={() => applyPreset(n)}>{n}</button>)}
      </div>
      <div style={{ height: 12 }} />
      <Slider k="gas_ppm" label="Gas (H₂S)" min={0} max={200} step={1} unit=" ppm" />
      <Slider k="oxygen_pct" label="Oxygen" min={5} max={25} step={0.1} unit=" %" />
      <Slider k="temp_c" label="Temperature" min={0} max={60} step={0.5} unit=" °C" />
      <Slider k="humidity_pct" label="Humidity" min={0} max={100} step={1} unit=" %" />
      <Slider k="worker_count" label="Workers in zone" min={0} max={12} step={1} unit="" />
      <div className="ctrl"><label>Zone</label>
        <select value={r.zone} onChange={(e) => set("zone", e.target.value)}>{ZONES.map((z) => <option key={z}>{z}</option>)}</select></div>
      <div className="ctrl"><label>Active permits</label>
        <div className="permits">{ALL_PERMITS.map((p) => (
          <button key={p} className={permits.includes(p) ? "on" : ""} onClick={() => togglePermit(p)}>{p.replace("_", " ")}</button>))}</div></div>
    </div>
  );
}

function RiskHero({ scan, b, latency }) {
  const score = scan ? scan.risk_score : 0;
  return (
    <div className="card hero">
      <h3 style={{ textAlign: "center" }}>Compound Risk {latency != null && <span className="sub">· {latency} ms</span>}</h3>
      <Gauge score={score} color={b.color} />
      <div className="score" style={{ color: b.color }}>{score}<span style={{ fontSize: 22 }}>/100</span></div>
      <div className="band" style={{ color: b.color }}>{b.name}</div>
      <div className="meter"><div style={{ width: `${score}%`, background: b.color }} /></div>
      <div className="action">{scan ? scan.recommended_action : "Adjust the controls to run a live compound-risk assessment."}</div>
    </div>
  );
}

function CompoundCompare({ scan }) {
  const s = scan.single_sensor;
  return (
    <div className="card">
      <h3>Compound vs Single-Sensor</h3>
      <div className="cmp-row"><span className="cmp-tag">Individual sensor alarms</span>
        <span className="cmp-val" style={{ color: s.count ? "#e67e22" : "#2ecc71" }}>{s.count} / {s.total} triggered</span></div>
      <div className="cmp-row"><span className="cmp-tag">Compound engine</span>
        <span className="cmp-val" style={{ color: scan.risk_score >= 50 ? "#e74c3c" : "#2ecc71" }}>{scan.compliance.highest_severity || "nominal"} · {scan.risk_score}/100</span></div>
      {s.compound_fires && s.count === 0 &&
        <div className="banner-warn">⚠ Without compound intelligence, <b>no single-sensor alarm would have fired</b> — the blind spot that kills.</div>}
    </div>
  );
}

function Confidence({ conf }) {
  const Bar = ({ label, v }) => (
    <div className="bar"><div className="top"><span>{label}</span><b>{Math.round(v * 100)}%</b></div>
      <div className="track"><div style={{ width: `${v * 100}%`, background: v >= 0.66 ? "#2ecc71" : v >= 0.33 ? "#f1c40f" : "#e74c3c" }} /></div></div>
  );
  const color = conf.label === "high" ? "#2ecc71" : conf.label === "medium" ? "#f1c40f" : "#e74c3c";
  return (
    <div className="card">
      <h3>Assessment Confidence</h3>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
        <span className="big-num" style={{ color, fontSize: 26 }}>{Math.round(conf.confidence * 100)}%</span>
        <span className="tag" style={{ background: `${color}22`, color }}>{conf.label.toUpperCase()}</span></div>
      <Bar label="Sensor coverage" v={conf.coverage} />
      <Bar label="Signal decisiveness" v={conf.decisiveness} />
      <Bar label="Data freshness" v={conf.freshness} />
      <div className="sub" style={{ marginTop: 8 }}>{conf.notes.join(" ")}</div>
    </div>
  );
}

function Interventions({ iv }) {
  return (
    <div className="card">
      <h3>Recommended Interventions</h3>
      {iv.recommended ? iv.interventions.filter((c) => c.risk_reduction > 0).slice(0, 4).map((c, i) => (
        <div className={`iv ${i === 0 ? "top" : ""}`} key={c.action}>
          <div className="head"><span className="act">{i === 0 ? "➡ " : ""}{c.action}</span><span className="delta">−{c.risk_reduction}</span></div>
          <div className="flow">risk {c.risk_before} → {c.risk_after}</div>
          <div className="desc">{c.description}</div>
        </div>)) : <div className="sub">Conditions nominal — no risk-reducing action required.</div>}
      {iv.residual_action && <div className="banner-warn">🚨 {iv.residual_action}</div>}
    </div>
  );
}

function Limits({ limits }) {
  return (
    <div className="card">
      <h3>Measured vs Regulatory Limit</h3>
      {limits.map((l) => (
        <div className="bar" key={l.parameter}>
          <div className="top"><span>{l.parameter}</span><b style={{ color: pctColor(l.pct_of_limit) }}>{l.measured}{l.unit} · {l.pct_of_limit}%</b></div>
          <div className="track"><div style={{ width: `${Math.min(150, l.pct_of_limit) / 1.5}%`, background: pctColor(l.pct_of_limit) }} /></div>
        </div>))}
      <div className="sub" style={{ marginTop: 6 }}>100% = OISD/Factory Act safe limit (oxygen is a lower bound).</div>
    </div>
  );
}

function Violations({ comp }) {
  if (!comp.violations.length) return <div className="card"><h3>Compliance</h3><div className="sub">No violations — {comp.pass_status ? "PASS" : "review"}.</div></div>;
  return (
    <div className="card">
      <h3>Compliance Violations · {comp.highest_severity}</h3>
      <table><thead><tr><th>Rule</th><th>Severity</th><th>Name</th><th>Reference (OISD / Factory Act / DGMS)</th></tr></thead>
        <tbody>{comp.violations.map((v) => (
          <tr key={v.rule_id}><td className="mono">{v.rule_id}</td><td>{v.severity}</td><td>{v.name}</td><td className="sub">{v.reference}</td></tr>))}</tbody></table>
    </div>
  );
}
