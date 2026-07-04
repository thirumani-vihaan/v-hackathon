"""VisionAgent: image -> VisionResult (Gemini primary, real offline-CV fallback)."""
from schema import VisionInput, VisionResult, Hazard
from utils import gemini_vision
from utils import local_vision


class VisionAgent:
    def analyze(self, vision_input: VisionInput) -> VisionResult:
        try:
            result = gemini_vision.analyze_image(vision_input.image_path)
            # Use Gemini only if it genuinely produced a grounded result.
            if result is not None and result.source == "gemini":
                return result
            # Offline: real OpenCV pixel analysis ONLY — never canned generic hazards.
            # Surface WHY Gemini wasn't used so the UI can explain the fallback.
            cv = local_vision.detect(vision_input.image_path)
            if result is not None and getattr(result, "error", None):
                cv.error = result.error
            return cv
        except Exception:
            try:
                return local_vision.detect(vision_input.image_path)
            except Exception as e:  # noqa: BLE001
                return VisionResult(
                    hazards=[],
                    summary="Vision analysis unavailable.",
                    source="fallback",
                    error=str(e),
                )

    def process(self, vision_input: VisionInput) -> VisionResult:
        """Primary entry point; alias of analyze(). Returns a VisionResult."""
        return self.analyze(vision_input)


if __name__ == "__main__":
    print(VisionAgent().analyze(VisionInput(image_path="data/test_safety_image.jpg")))
