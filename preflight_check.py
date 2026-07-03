"""preflight_check.py — strict environment + dependency + Gemini preflight.

Exit 0 only if all non-Gemini checks pass AND the smoke test passes.
Gemini: empty key -> WARN only; non-empty key -> real API call must succeed.
"""
import os
import sys
import subprocess

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_ROOT, ".env"))
except Exception:
    pass

VENV_PY = os.path.join(_ROOT, "venv", "Scripts", "python.exe")
PY = VENV_PY if os.path.exists(VENV_PY) else sys.executable

REQUIRED_DIRS = [
    "compliance", "knowledge_base/raw", "knowledge_base/processed", "agents",
    "utils", "ui", "tests", "data", "logs", "tools", "tools/acceptance",
]
REQUIRED_FILES = [
    "schema.py", "CLAUDE.md", "compliance/safety_rules.json", "requirements.in",
    "agents/orchestrator.py", "agents/vision_agent.py", "agents/compliance_agent.py",
    "agents/knowledge_agent.py", "agents/safety_agent.py",
]

_fail = []
_warn = []


def check(cond, msg):
    if cond:
        print(f"[ok] {msg}")
    else:
        print(f"[FAIL] {msg}")
        _fail.append(msg)


def main():
    print("=== IndustrialSafetyAI preflight ===")

    for d in REQUIRED_DIRS:
        check(os.path.isdir(os.path.join(_ROOT, d)), f"dir exists: {d}")
    for f in REQUIRED_FILES:
        check(os.path.isfile(os.path.join(_ROOT, f)), f"file exists: {f}")

    check(os.path.exists(VENV_PY), "venv python exists")

    # critical package imports via venv python
    imp = subprocess.run(
        [PY, "-c",
         "import chromadb, langgraph, langchain, google.generativeai, streamlit, "
         "folium, reportlab, pypdf, sentence_transformers, torch, cv2, pandas, numpy; "
         "print('imports-ok')"],
        capture_output=True, text=True)
    check(imp.returncode == 0 and "imports-ok" in imp.stdout,
          "critical packages import")
    if imp.returncode != 0:
        print(imp.stderr[-800:])

    # at least one PDF; generate if missing
    raw = os.path.join(_ROOT, "knowledge_base", "raw")
    pdfs = [f for f in os.listdir(raw) if f.lower().endswith(".pdf")] \
        if os.path.isdir(raw) else []
    if not pdfs:
        print("[info] no PDF found; generating synthetic PDF")
        subprocess.run([PY, os.path.join("tools", "generate_synthetic_pdf.py")],
                       cwd=_ROOT)
        pdfs = [f for f in os.listdir(raw) if f.lower().endswith(".pdf")]
    check(len(pdfs) > 0, "at least one knowledge PDF present")

    # schema import + instantiate
    try:
        from schema import SensorReading
        SensorReading(gas_ppm=5, temp_c=30, oxygen_pct=20.9, humidity_pct=50,
                      permit_type="general", worker_count=1, zone="Z",
                      timestamp="2026-07-03T00:00:00")
        print("[ok] schema imports and instantiates")
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] schema instantiate: {e}")
        _fail.append("schema instantiate")

    # smoke test (must pass)
    print("--- running smoke test ---")
    smoke = subprocess.run([PY, os.path.join("tools", "smoke_test_deps.py")],
                           cwd=_ROOT, capture_output=True, text=True)
    print(smoke.stdout[-1500:])
    if smoke.returncode != 0:
        print(smoke.stderr[-1500:])
    check(smoke.returncode == 0, "smoke_test_deps passes")

    # Gemini
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        _warn.append("GEMINI_API_KEY empty; vision uses fallback")
        print("[warn] GEMINI_API_KEY empty; vision will use fallback")
    else:
        try:
            from utils.gemini_vision import verify_api_key
            ok, msg = verify_api_key()
            if ok:
                print(f"[ok] Gemini API reachable: {msg}")
            else:
                print(f"[FAIL] Gemini API call failed: {msg}. "
                      f"Fix key / permissions.")
                _fail.append("Gemini API call")
        except Exception as e:  # noqa: BLE001
            print(f"[FAIL] Gemini check crashed: {e}. Fix key / permissions.")
            _fail.append("Gemini check crash")

    print("=== preflight summary ===")
    for w in _warn:
        print(f"WARN: {w}")
    if _fail:
        for fmsg in _fail:
            print(f"FAIL: {fmsg}")
        print("PREFLIGHT FAILED")
        return 1
    print("PREFLIGHT OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
