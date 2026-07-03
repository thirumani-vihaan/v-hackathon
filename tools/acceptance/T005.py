"""T005 acceptance: VisionAgent.analyze returns VisionResult dataclass."""
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def main():
    try:
        from schema import VisionInput, VisionResult
        from agents.vision_agent import VisionAgent

        agent = VisionAgent()
        res = agent.analyze(VisionInput(image_path="no_such_file.jpg"))
        assert isinstance(res, VisionResult), "must return VisionResult dataclass"
        assert not isinstance(res, dict)
        assert res.source in ("gemini", "fallback")
        for h in res.hazards:
            assert 0.0 <= h.confidence <= 1.0
            assert len(h.bbox) == 4
    except Exception:
        traceback.print_exc()
        return 1
    print("T005 PASS: VisionAgent OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
