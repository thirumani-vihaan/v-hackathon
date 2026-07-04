// Thin API client for the FastAPI backend (proxied at /api during dev).
const j = (r) => {
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json();
};

export const api = {
  health: () => fetch("/api/health").then(j),
  scan: (reading, active_permits) =>
    fetch("/api/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reading, active_permits }),
    }).then(j),
  zones: (gas, oxygen, humidity, permits) =>
    fetch(`/api/zones?gas=${gas}&oxygen=${oxygen}&humidity=${humidity}&permits=${permits.join(",")}`).then(j),
  incidents: (gas, oxygen, zone, permits) =>
    fetch(`/api/incidents?gas=${gas}&oxygen=${oxygen}&zone=${encodeURIComponent(zone)}&permits=${permits.join(",")}`).then(j),
  benchmark: () => fetch("/api/benchmark").then(j),
  audit: () => fetch("/api/audit/verify").then(j),
  knowledge: (query) =>
    fetch("/api/knowledge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    }).then(j),
};
