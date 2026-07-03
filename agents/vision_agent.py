"""VisionAgent: image -> VisionResult (Gemini primary, real offline-CV fallback)."""
from schema import VisionInput, VisionResult, Hazard
from utils import gemini_vision
from utils import local_vision


class VisionAgent:
    def analyze(self, vision_input: VisionInput) -> VisionResult:
        try:
            result = gemini_vision.analyze_image(vision_input.image_path)
            # If Gemini was unavailable/canned, do a genuine offline pixel analysis.
            if result is None or result.source == "fallback":
                cv = local_vision.detect(vision_input.image_path)
                # Prefer the CV result when it actually found/qualified hazards.
                if cv.hazards or (result is None) or not result.hazards:
                    return cv
            return result
        except Exception:
            try:
                return local_vision.detect(vision_input.image_path)
            except Exception as e:  # noqa: BLE001
                return VisionResult(
                    hazards=[Hazard(type="unsafe_equipment", confidence=0.5,
                                    bbox=[0, 0, 10, 10])],
                    summary="Vision agent error; returning conservative fallback.",
                    source="fallback",
                    error=str(e),
                )

    def process(self, vision_input: VisionInput) -> VisionResult:
        """Primary entry point; alias of analyze(). Returns a VisionResult."""
        return self.analyze(vision_input)


if __name__ == "__main__":
    print(VisionAgent().analyze(VisionInput(image_path="data/test_safety_image.jpg")))
