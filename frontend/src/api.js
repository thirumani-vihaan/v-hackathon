// API client for the FastAPI backend (same origin when served by the backend).
const j = (r) => {
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json();
};
const post = (url, body) =>
  fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then(j);

export const api = {
  health: () => fetch("/api/health").then(j),
  scan: (reading, active_permits) => post("/api/scan", { reading, active_permits }),
  zones: (gas, oxygen, humidity, permits) =>
    fetch(`/api/zones?gas=${gas}&oxygen=${oxygen}&humidity=${humidity}&permits=${permits.join(",")}`).then(j),
  incidents: (gas, oxygen, zone, permits) =>
    fetch(`/api/incidents?gas=${gas}&oxygen=${oxygen}&zone=${encodeURIComponent(zone)}&permits=${permits.join(",")}`).then(j),
  benchmark: () => fetch("/api/benchmark").then(j),
  audit: () => fetch("/api/audit/verify").then(j),
  knowledge: (query) => post("/api/knowledge", { query }),
  languages: () => fetch("/api/languages").then(j),
  gases: () => fetch("/api/gases").then(j),
  exposure: (gas, ppm, volume, ach) =>
    fetch(`/api/exposure?gas=${gas}&ppm=${ppm}&volume=${volume}&ach=${ach}`).then(j),
  briefing: (reading, active_permits, language) => post("/api/briefing", { reading, active_permits, language }),
  dispatch: (reading, active_permits, language) => post("/api/dispatch", { reading, active_permits, language }),
  facilities: (zone) => fetch(`/api/facilities?zone=${encodeURIComponent(zone)}`).then(j),
  forecast: (gas_history, oxygen_history, seconds_per_step = 60) =>
    post("/api/forecast", { gas_history, oxygen_history, seconds_per_step }),
  auditEvents: (n = 15) => fetch(`/api/audit/events?n=${n}`).then(j),
  vision: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch("/api/vision", { method: "POST", body: fd }).then(j);
  },
  stressTest: (trials = 100) => fetch(`/api/stress-test?trials=${trials}`, { method: "POST" }).then(j),
};
