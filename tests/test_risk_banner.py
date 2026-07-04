"""Tests for the dependency-free risk banner/meter HTML builders."""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from utils.risk_banner import risk_band, risk_banner_html, risk_meter_html  # noqa: E402


def test_bands_at_boundaries():
    assert risk_band(0)[0] == "NOMINAL"
    assert risk_band(19)[0] == "NOMINAL"
    assert risk_band(20)[0] == "ELEVATED"
    assert risk_band(49)[0] == "ELEVATED"
    assert risk_band(50)[0] == "HIGH"
    assert risk_band(79)[0] == "HIGH"
    assert risk_band(80)[0] == "CRITICAL"
    assert risk_band(100)[0] == "CRITICAL"


def test_banner_contains_score_and_band():
    html = risk_banner_html(95, "CRITICAL")
    assert "95" in html and "CRITICAL" in html
    assert "#e74c3c" in html  # critical color


def test_meter_width_matches_score():
    assert "width:65%" in risk_meter_html(65)
    # clamped
    assert "width:100%" in risk_meter_html(140)
    assert "width:0%" in risk_meter_html(-5)
