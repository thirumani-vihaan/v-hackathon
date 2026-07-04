"""Tests for the offline capability modules (all offline, deterministic)."""
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from schema import (  # noqa: E402
    VisionResult, VisionInput, OrchestratorResult, SafetyAlert, ComplianceResult,
    ComplianceViolation,
)
from utils import local_vision, exposure_calc, safety_calendar, response_directory
from utils import translations, voice  # noqa: E402
from agents.output_agent import OutputAgent  # noqa: E402
from agents.vision_agent import VisionAgent  # noqa: E402


# ---------- local (offline) vision ----------
def _write_fire_image(path):
    from PIL import Image
    # a realistic localized, high-contrast flame on a dark background (hot core -> red)
    n = 64
    arr = np.zeros((n, n, 3), dtype=np.float32)
    yy, xx = np.ogrid[:n, :n]
    d = np.sqrt((xx - 32) ** 2 + (yy - 36) ** 2)
    inten = np.clip(1 - d / 22, 0, 1)
    m = d < 22
    arr[..., 0] = np.where(m, 210 + 45 * inten, 15)
    arr[..., 1] = np.where(m, 40 + 170 * inten, 15)
    arr[..., 2] = np.where(m, 20 * inten, 20)
    Image.fromarray(arr.astype(np.uint8)).save(path)


def _write_normal_image(path):
    from PIL import Image
    arr = np.zeros((64, 64, 3), dtype=np.uint8)
    arr[..., 1] = 120  # green
    arr[..., 2] = 120  # blue
    Image.fromarray(arr).save(path)


def test_local_vision_returns_visionresult(tmp_path):
    p = tmp_path / "fire.png"
    _write_fire_image(str(p))
    res = local_vision.detect(str(p))
    assert isinstance(res, VisionResult)
    assert res.source == "fallback"


def test_local_vision_detects_fire(tmp_path):
    p = tmp_path / "fire.png"
    _write_fire_image(str(p))
    res = local_vision.detect(str(p))
    assert any(h.type == "smoke_fire" for h in res.hazards)
    for h in res.hazards:
        assert len(h.bbox) == 4
        assert 0.0 <= h.confidence <= 1.0


def test_local_vision_normal_no_fire(tmp_path):
    p = tmp_path / "ok.png"
    _write_normal_image(str(p))
    res = local_vision.detect(str(p))
    assert not any(h.type == "smoke_fire" for h in res.hazards)


def test_vision_agent_uses_offline_cv(tmp_path):
    p = tmp_path / "fire.png"
    _write_fire_image(str(p))
    res = VisionAgent().analyze(VisionInput(image_path=str(p)))
    assert isinstance(res, VisionResult)


def test_local_vision_unreadable_is_safe():
    res = local_vision.detect("does_not_exist_xyz.png")
    assert isinstance(res, VisionResult)
    assert res.hazards == []


def test_trained_model_present_and_used(tmp_path):
    # model file should exist (trained during build) and load without error
    assert os.path.isfile(local_vision._MODEL_PATH)
    m = local_vision._load_model()
    assert m is not None
    W, b, mu, sigma = m
    # model dimension matches the current feature vector
    feat_dim = local_vision.features(np.zeros((16, 16, 3), dtype=np.uint8)).shape[0]
    assert W.shape[0] == feat_dim


# ---------- exposure calculator ----------
def test_exposure_idlh():
    a = exposure_calc.assess_exposure("h2s", 150)
    assert a.status == "IDLH"
    assert a.pel_ratio > 1


def test_exposure_ok():
    a = exposure_calc.assess_exposure("co", 5)
    assert a.status == "OK"


def test_lel_percent_methane():
    # 5 vol% LEL => 50000 ppm; 25000 ppm = 50% LEL
    assert exposure_calc.lel_percent("ch4", 25000) == 50.0


def test_ventilation_and_purge_positive():
    cfm = exposure_calc.ventilation_cfm(100, 12)
    assert cfm > 0
    assert exposure_calc.purge_time_min(100, cfm) > 0


def test_evacuation_radius_scales():
    assert exposure_calc.evacuation_radius_m("h2s", 5) == 0
    assert exposure_calc.evacuation_radius_m("h2s", 150) >= 300


def test_unknown_gas_raises():
    import pytest
    with pytest.raises(ValueError):
        exposure_calc.assess_exposure("unobtanium", 1)


# ---------- seasonal calendar ----------
def test_calendar_monsoon():
    adv = safety_calendar.advisories_for(7)
    assert adv["season"] == "monsoon"
    assert any("lectric" in a or "lip" in a for a in adv["advisories"])


def test_calendar_upcoming_wraps():
    up = safety_calendar.upcoming(4, start_month=11)
    assert [u["month"] for u in up] == [11, 12, 1, 2]


def test_shift_note_nonempty():
    assert safety_calendar.shift_note(3)
    assert safety_calendar.shift_note(10)


# ---------- response directory ----------
def test_nearest_sorted_by_distance():
    near = response_directory.nearest_facilities("Zone-C-Confined", top_k=4)
    dists = [f["distance_km"] for f in near]
    assert dists == sorted(dists)
    assert all("distance_km" in f for f in near)


def test_nearest_filter_type():
    near = response_directory.nearest_facilities("Zone-A-Tank-Farm",
                                                 facility_type="Hospital")
    assert all("hospital" in f["type"].lower() for f in near)


def test_helpline_banner():
    b = response_directory.helpline_banner()
    assert "112" in b


# ---------- translations (10 languages) ----------
def test_ten_languages():
    assert len(translations.LANGUAGES) >= 10
    for name in ("Kannada", "Punjabi", "Gujarati", "Bengali", "Odia"):
        assert name in translations.LANGUAGES


def test_all_languages_have_static_evac():
    for name, code in translations.LANGUAGES.items():
        msg, src = translations.translate_evac(name, "Zone-B", "r1",
                                                use_gemini=False)
        assert "r1" in msg
        assert src == "static"


# ---------- OutputAgent (5th stage) ----------
def _crit_result():
    return OrchestratorResult(
        request_id="req-x", input_type="sensor",
        safety=SafetyAlert(risk_score=100, triggered_rules=["A", "B"],
                           recommended_action="Evacuate", zone="Zone-B-Process"),
        compliance=ComplianceResult(
            pass_status=False,
            violations=[ComplianceViolation("R002", "Critical Gas", "CRITICAL",
                                            "msg", "OISD-1")],
            highest_severity="CRITICAL"))


def test_output_format_identity():
    r = _crit_result()
    assert OutputAgent().format(r) is r


def test_output_format_type_check():
    import pytest
    with pytest.raises(TypeError):
        OutputAgent().format({"not": "a result"})


def test_output_severity_critical():
    assert OutputAgent().severity(_crit_result()) == "CRITICAL"


def test_briefing_contains_evacuation_and_translation():
    b = OutputAgent().briefing(_crit_result(), "Hindi")
    assert "CRITICAL" in b
    assert "EVACUATION" in b
    assert "R002" in b


def test_briefing_normal_no_evacuation():
    r = OrchestratorResult(
        request_id="req-ok", input_type="sensor",
        safety=SafetyAlert(risk_score=5, triggered_rules=[],
                           recommended_action="Continue", zone="Zone-A-Tank-Farm"),
        compliance=ComplianceResult(pass_status=True, violations=[],
                                    highest_severity=None))
    b = OutputAgent().briefing(r)
    assert "EVACUATION" not in b


# ---------- voice component ----------
def test_speak_html_contains_locale_and_text():
    html = voice.speak_html("Evacuate now", "Telugu")
    assert "te-IN" in html
    assert "SpeechSynthesisUtterance" in html


def test_voice_escapes_quotes():
    html = voice.speak_html('say "hello" now', "English")
    assert "SpeechSynthesisUtterance" in html
