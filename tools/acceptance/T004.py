"""T004 acceptance: gemini_vision returns a valid VisionResult even without key."""
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def main():
    try:
        from schema import VisionResult
        from utils import gemini_vision

        # Missing image => must fall back, never raise.
        res = gemini_vision.analyze_image("no_such_file.jpg")
        assert isinstance(res, VisionResult)
        assert res.source in ("gemini", "fallback")
        assert isinstance(res.hazards, list)
        assert res.summary

        # Force no-key path explicitly.
        saved = os.environ.get("GEMINI_API_KEY")
        os.environ["GEMINI_API_KEY"] = ""
        res2 = gemini_vision.analyze_image("no_such_file.jpg")
        assert res2.source == "fallback"
        assert res2.error is not None
        if saved is not None:
            os.environ["GEMINI_API_KEY"] = saved
    except Exception:
        traceback.print_exc()
        return 1
    print("T004 PASS: gemini_vision safe fallback OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
