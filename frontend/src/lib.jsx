// Shared visual helpers.
export const BANDS = [
  [80, "CRITICAL", "#e74c3c", "critical"],
  [50, "HIGH", "#e67e22", "high"],
  [20, "ELEVATED", "#f1c40f", "elevated"],
  [0, "NOMINAL", "#2ecc71", "nominal"],
];

export function band(score) {
  for (const b of BANDS) if (score >= b[0]) return { name: b[1], color: b[2], cls: b[3] };
  return { name: "NOMINAL", color: "#2ecc71", cls: "nominal" };
}

export function pctColor(pct) {
  if (pct >= 100) return "#e74c3c";
  if (pct >= 80) return "#e67e22";
  if (pct >= 50) return "#f1c40f";
  return "#2ecc71";
}

// SVG arc gauge (0-100).
export function Gauge({ score, color }) {
  const r = 62, cx = 80, cy = 80, C = Math.PI * r; // half circle
  const frac = Math.max(0, Math.min(100, score)) / 100;
  return (
    <svg width="160" height="96" viewBox="0 0 160 96" className="gauge">
      <path d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
        fill="none" stroke="#1b2230" strokeWidth="12" strokeLinecap="round" />
      <path d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
        fill="none" stroke={color} strokeWidth="12" strokeLinecap="round"
        strokeDasharray={C} strokeDashoffset={C * (1 - frac)}
        style={{ transition: "stroke-dashoffset 0.6s ease, stroke 0.4s" }} />
    </svg>
  );
}
