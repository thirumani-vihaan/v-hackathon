"""Dependency-free risk visualisation helpers (HTML/CSS for Streamlit markdown).

Gives the dashboard a polished, colour-coded risk banner and gauge meter that recolour
by severity — the "ambient" alert visual competitors achieve with React — without adding
any dependency (no Plotly, no JS). Pure string builders so they are unit-testable.
"""
from __future__ import annotations

# (min_score, name, color, glow)
_BANDS = [
    (80, "CRITICAL", "#e74c3c", "rgba(231,76,60,0.35)"),
    (50, "HIGH", "#e67e22", "rgba(230,126,34,0.30)"),
    (20, "ELEVATED", "#f1c40f", "rgba(241,196,15,0.25)"),
    (0, "NOMINAL", "#2ecc71", "rgba(46,204,113,0.20)"),
]


def risk_band(score: int):
    """Return (name, color, glow) for a 0-100 risk score."""
    for threshold, name, color, glow in _BANDS:
        if score >= threshold:
            return name, color, glow
    return _BANDS[-1][1], _BANDS[-1][2], _BANDS[-1][3]


def risk_banner_html(score: int, severity: str = None) -> str:
    """A full-width, colour-coded risk banner with an ambient glow."""
    score = max(0, min(100, int(score)))
    name, color, glow = risk_band(score)
    sev = (severity or name).upper()
    return (
        f'<div style="border-radius:12px;padding:16px 20px;margin:4px 0 12px 0;'
        f'background:linear-gradient(135deg,{color}22,{color}0a);'
        f'border:1px solid {color};box-shadow:0 0 22px {glow};">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;">'
        f'<div style="font-size:15px;font-weight:600;color:{color};'
        f'letter-spacing:.5px;">COMPOUND RISK &mdash; {name}</div>'
        f'<div style="font-size:34px;font-weight:800;color:{color};'
        f'font-family:monospace;">{score}<span style="font-size:16px;">/100</span></div>'
        f'</div>'
        f'<div style="font-size:12px;color:#9aa;">Compliance severity: {sev}</div>'
        f'</div>'
    )


def risk_meter_html(score: int) -> str:
    """A horizontal gauge meter filled to `score`% and coloured by band."""
    score = max(0, min(100, int(score)))
    _, color, _ = risk_band(score)
    return (
        f'<div style="background:#20232a;border-radius:8px;height:16px;width:100%;'
        f'overflow:hidden;margin:2px 0 10px 0;">'
        f'<div style="height:100%;width:{score}%;background:{color};'
        f'transition:width .4s ease;"></div></div>'
    )


if __name__ == "__main__":
    for s in (10, 35, 65, 95):
        print(s, risk_band(s))
