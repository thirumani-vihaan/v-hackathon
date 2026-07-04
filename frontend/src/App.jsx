import React, { useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import { band, pctColor, Gauge } from "./lib.jsx";

const ALL_PERMITS = ["hot_work", "confined_space", "maintenance", "electrical", "shift_changeover", "cold_work"];
const ZONES = ["Zone-A-Tank-Farm", "Zone-B-Process", "Zone-C-Confined", "Zone-D-Substation"];

const PRESETS = {
  Nominal: { gas_ppm: 8, temp_c: 30, oxygen_pct: 20.9, humidity_pct: 50, worker_count: 2, zone: "Zone-A-Tank-Farm", permit_type: "general", permits: [] },
  "Vizag Critical": { gas_ppm: 120, temp_c: 41, oxygen_pct: 18.4, humidity_pct: 70, worker_count: 4, zone: "Zone-C-Confined", permit_type: "hot_work", permits: ["hot_work"] },
  "Confined Maint.": { gas_ppm: 72, temp_c: 33, oxygen_pct: 18.9, humidity_pct: 66, worker_count: 3, zone: "Zone-C-Confined", permit_type: "confined_space", permits: ["maintenance", "shift_changeover", "confined_space"] },
};

export default function App() {
  const [r, setR] = useState(PRESETS["Vizag Critical"]);
  const [permits, setPermits] = useState(PRESETS["Vizag Critical"].permits);
  const [scan, setScan] = useState(null);
  const [zones, setZones] = useState(null);
  const [inc, setInc] = useState(null);
  const [bench, setBench] = useState(null);
  const [audit, setAudit] = useState(null);
  const [err, setErr] = useState(null);
  const [latency, setLatency] = useState(null);
  const t = useRef(null);

  useEffect(() => {
    api.benchmark().then(setBench).catch(() => {});
    api.audit().then(setAudit).catch(() => {});
  }, []);

  useEffect(() => {
    if (t.current) clearTimeout(t.current);
    t.current = setTimeout(async () => {
      const reading = { gas_ppm: r.gas_ppm, temp_c: r.temp_c, oxygen_pct: r.oxygen_pct, humidity_pct: r.humidity_pct, worker_count: r.worker_count, zone: r.zone, permit_type: r.permit_type };
      try {
        const t0 = performance.now();
        const s = await api.scan(reading, permits);
        setLatency(Math.round(performance.now() - t0));
        setScan(s); setErr(null);
        api.zones(r.gas_ppm, r.oxygen_pct, r.humidity_pct, permits).then(setZones).catch(() => {});
        api.incidents(r.gas_ppm, r.oxygen_pct, r.zone, permits).then(setInc).catch(() => {});
      } catch (e) { setErr("Backend unreachable — start: uvicorn backend.main:app --port 8000"); }
    }, 140);
    return () => clearTimeout(t.current);
  }, [r, permits]);

  const b = band(scan ? scan.risk_score : 0);
  const set = (k, v) => setR((p) => ({ ...p, [k]: v }));
  const togglePermit = (p) => setPermits((prev) => prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]);
  const applyPreset = (name) => { const p = PRESETS[name]; setR(p); setPermits(p.permits); };

  return (
    <div className={`app risk-${b.cls}`}>
      <div className="wrap">
        <div className="topbar">
          <div className="brand">
            <div className="logo">🛡️</div>
            <div>
              <h1>IndustrialSafetyAI</h1>
              <p>Zero-Harm Command Center</p>
            </div>
          </div>
          <div className="pills">
            {latency != null && <span className="pill">scan {latency} ms</span>}
            <span className="pill">offline · deterministic</span>
            <span className="pill live">LIVE</span>
          </div>
        </div>

        {err && <div className="card err">{err}</div>}

        <div className="grid">
          {/* LEFT: controls */}
          <div className="col">
            <Controls r={r} set={set} permits={permits} togglePermit={togglePermit} applyPreset={applyPreset} />
            {bench && <Benchmark bench={bench} />}
            {audit && <AuditBadge audit={audit} />}
          </div>

          {/* RIGHT: analysis */}
          <div className="col">
            <RiskHero scan={scan} b={b} />
            <div className="row2">
              {scan && <CompoundCompare scan={scan} />}
              {scan && <Confidence conf={scan.confidence} />}
            </div>
            <div className="row2">
              {scan && <Interventions iv={scan.interventions} />}
              {scan && <Limits limits={scan.limits} />}
            </div>
            {zones && <ZonePanel zones={zones} />}
            {inc && <Incidents inc={inc} />}
          </div>
        </div>
        <div className="footer">Powered by a warm FastAPI backend · real multi-agent AI · {bench ? bench.dataset_size : "—"} benchmarked scenarios · fully offline</div>
      </div>
    </div>
  );
}

function Controls({ r, set, permits, togglePermit, applyPreset }) {
  const Slider = ({ k, label, min, max, step, unit }) => (
    <div className="ctrl">
      <label>{label}<b>{r[k]}{unit}</b></label>
      <input type="range" min={min} max={max} step={step} value={r[k]}
        onChange={(e) => set(k, parseFloat(e.target.value))} />
    </div>
  );
  return (
    <div className="card">
      <h3>Sensor & Permit Controls</h3>
      <div className="preset-row">
        {Object.keys(PRESETS).map((n) => (
          <button key={n} className={n.includes("Vizag") ? "danger" : ""} onClick={() => applyPreset(n)}>{n}</button>
        ))}
      </div>
      <div style={{ height: 12 }} />
      <Slider k="gas_ppm" label="Gas (H₂S)" min={0} max={200} step={1} unit=" ppm" />
      <Slider k="oxygen_pct" label="Oxygen" min={5} max={25} step={0.1} unit=" %" />
      <Slider k="temp_c" label="Temperature" min={0} max={60} step={0.5} unit=" °C" />
      <Slider k="humidity_pct" label="Humidity" min={0} max={100} step={1} unit=" %" />
      <Slider k="worker_count" label="Workers in zone" min={0} max={12} step={1} unit="" />
      <div className="ctrl">
        <label>Zone</label>
        <select value={r.zone} onChange={(e) => set("zone", e.target.value)}>
          {ZONES.map((z) => <option key={z}>{z}</option>)}
        </select>
      </div>
      <div className="ctrl">
        <label>Active permits</label>
        <div className="permits">
          {ALL_PERMITS.map((p) => (
            <button key={p} className={permits.includes(p) ? "on" : ""} onClick={() => togglePermit(p)}>
              {p.replace("_", " ")}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function RiskHero({ scan, b }) {
  const score = scan ? scan.risk_score : 0;
  return (
    <div className="card hero">
      <h3 style={{ textAlign: "center" }}>Compound Risk</h3>
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
        <span className="cmp-val" style={{ color: scan.risk_score >= 50 ? "#e74c3c" : "#2ecc71" }}>
          {scan.compliance.highest_severity || "nominal"} · {scan.risk_score}/100</span></div>
      {s.compound_fires && s.count === 0 &&
        <div className="banner-warn">⚠ Without compound intelligence, <b>no single-sensor alarm would have fired</b> — the blind spot that kills.</div>}
    </div>
  );
}

function Confidence({ conf }) {
  const Bar = ({ label, v }) => (
    <div className="bar"><div className="top"><span>{label}</span><b>{Math.round(v * 100)}%</b></div>
      <div className="track"><div style={{ width: `${v * 100}%`, background: pctColor(100 - v * 100 + (v >= 0.75 ? 60 : 0)) }} /></div></div>
  );
  const color = conf.label === "high" ? "#2ecc71" : conf.label === "medium" ? "#f1c40f" : "#e74c3c";
  return (
    <div className="card">
      <h3>Assessment Confidence</h3>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
        <span className="big-num" style={{ color, fontSize: 26 }}>{Math.round(conf.confidence * 100)}%</span>
        <span className="tag" style={{ background: `${color}22`, color }}>{conf.label.toUpperCase()}</span>
      </div>
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
          <div className="head"><span className="act">{i === 0 ? "➡ " : ""}{c.action}</span>
            <span className="delta" style={{ color: "#2ecc71" }}>−{c.risk_reduction}</span></div>
          <div className="flow" style={{ color: "#8b98ad" }}>risk {c.risk_before} → {c.risk_after}</div>
          <div className="desc">{c.description}</div>
        </div>
      )) : <div className="sub">Conditions nominal — no risk-reducing action required.</div>}
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
          <div className="top"><span>{l.parameter}</span>
            <b style={{ color: pctColor(l.pct_of_limit) }}>{l.measured}{l.unit} · {l.pct_of_limit}%</b></div>
          <div className="track"><div style={{ width: `${Math.min(150, l.pct_of_limit) / 1.5}%`, background: pctColor(l.pct_of_limit) }} /></div>
        </div>
      ))}
      <div className="sub" style={{ marginTop: 6 }}>100% = OISD/Factory Act safe limit (oxygen is a lower bound).</div>
    </div>
  );
}

function ZonePanel({ zones }) {
  return (
    <div className="card">
      <h3>Geospatial Risk & Permit-Proximity Intelligence</h3>
      <div className="zones">
        {Object.entries(zones.colors).map(([z, c]) => (
          <div className={`zone ${c}`} key={z}>
            <div className="zn">{z}</div>
            <div className="zs" style={{ color: c === "red" ? "#e74c3c" : c === "orange" ? "#e67e22" : "#2ecc71" }}>{c === "red" ? "CRITICAL" : c === "orange" ? "ELEVATED" : "NOMINAL"}</div>
          </div>
        ))}
      </div>
      {zones.conflicts.length > 0 ? zones.conflicts.map((c, i) => (
        <div className={`conflict ${c.severity}`} key={i}><b>{c.severity}</b> — {c.message}</div>
      )) : <div className="sub" style={{ marginTop: 10 }}>No permit-proximity conflicts for the current plant state.</div>}
    </div>
  );
}

function Benchmark({ bench }) {
  const h = bench.headline;
  return (
    <div className="card">
      <h3>Proof: False-Negative Reduction</h3>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
        <span className="big-num" style={{ color: "#2ecc71" }}>−{Math.round(h.false_negative_reduction_pct)}<span style={{ fontSize: 16 }}>pts</span></span>
        <span className="sub">missed incidents</span>
      </div>
      <div className="cmp-row"><span className="cmp-tag">Single-sensor</span><span className="cmp-val"><span className="tag bad">{Math.round(h.single_sensor_operational_false_negative_rate * 100)}% miss</span></span></div>
      <div className="cmp-row"><span className="cmp-tag">Compound + prediction</span><span className="cmp-val"><span className="tag ok">{Math.round(h.compound_predictive_operational_false_negative_rate * 100)}% miss</span></span></div>
      <div className="cmp-row"><span className="cmp-tag">Median early warning</span><span className="cmp-val">{h.compound_median_lead_minutes} min</span></div>
      <div className="sub" style={{ marginTop: 6 }}>{bench.incidents} incident / {bench.safe} safe physics-labeled scenarios.</div>
    </div>
  );
}

function Incidents({ inc }) {
  return (
    <div className="card">
      <h3>Incident Pattern Intelligence · {inc.count} records</h3>
      <div style={{ marginBottom: 10 }}>
        {inc.priorities.slice(0, 3).map((p, i) => <div className="list-item" key={i}>• {p}</div>)}
      </div>
      {inc.similar && <>
        <div className="sub" style={{ marginBottom: 6 }}>Past incidents similar to current state:</div>
        {inc.similar.map((m) => (
          <div className="list-item" key={m.id}><b>{m.id}</b> <span className="muted">({m.severity}, match {m.match_score})</span> — {m.description}</div>
        ))}
      </>}
    </div>
  );
}

function AuditBadge({ audit }) {
  const ok = audit.valid;
  return (
    <div className="card">
      <h3>Tamper-Evident Audit</h3>
      <div className="audit">
        <span className="dot" style={{ background: ok ? "#2ecc71" : "#e74c3c", boxShadow: `0 0 10px ${ok ? "#2ecc71" : "#e74c3c"}` }} />
        <span>{ok ? "Chain intact" : `Broken at entry ${audit.broken_at}`} — {audit.chained} hash-linked entries</span>
      </div>
      <div className="sub" style={{ marginTop: 6 }}>SHA-256 hash chain · OISD/PESO-grade evidence integrity.</div>
    </div>
  );
}
