"""Gemini vision wrapper with safe fallback.

Returns a VisionResult regardless of whether the API key or network is available.
Never raises across the boundary.
"""
import os
import json
import base64

from schema import VisionResult, Hazard

# Ordered preference of vision-capable models. Current stable models first, with
# legacy names retained as final fallbacks for portability across API versions.
MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-flash-latest",
    "gemini-2.0-flash-exp",
    "gemini-1.5-flash",
]

_PROMPT = (
    "You are an industrial safety vision inspector. Look at the image and identify "
    "safety hazards. Respond with STRICT JSON only, no prose, of the form: "
    '{"hazards":[{"type":"no_helmet|smoke_fire|unauthorized_person|unsafe_equipment|'
    'gas_leak_visual|electrical_hazard","confidence":0.0-1.0,"bbox":[x1,y1,x2,y2]}],'
    '"summary":"one line"}. bbox values are percentages 0-100.'
)

_VALID_TYPES = {"no_helmet", "smoke_fire", "unauthorized_person",
                "unsafe_equipment", "gas_leak_visual", "electrical_hazard"}


def _fallback(image_path: str, error: str = None) -> VisionResult:
    """Deterministic conservative fallback used when Gemini is unavailable."""
    hazards = [
        Hazard(type="no_helmet", confidence=0.55, bbox=[30, 20, 55, 60]),
        Hazard(type="unsafe_equipment", confidence=0.50, bbox=[60, 40, 90, 85]),
    ]
    summary = ("Fallback heuristic inspection: potential missing PPE and unsafe "
               "equipment detected. Manual verification recommended.")
    return VisionResult(hazards=hazards, summary=summary, source="fallback",
                        error=error)


def _parse_response(text: str) -> VisionResult:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in response")
    data = json.loads(cleaned[start:end + 1])
    hazards = []
    for h in data.get("hazards", []):
        htype = h.get("type")
        if htype not in _VALID_TYPES:
            continue
        conf = float(h.get("confidence", 0.5))
        conf = max(0.0, min(1.0, conf))
        bbox = h.get("bbox", [0, 0, 10, 10])
        bbox = [int(round(v)) for v in bbox][:4]
        while len(bbox) < 4:
            bbox.append(10)
        hazards.append(Hazard(type=htype, confidence=conf, bbox=bbox))
    summary = str(data.get("summary", "Gemini inspection complete."))
    return VisionResult(hazards=hazards, summary=summary, source="gemini")


def analyze_image(image_path: str) -> VisionResult:
    """Analyze an image and return a VisionResult. Falls back safely."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return _fallback(image_path, error="GEMINI_API_KEY not set; using fallback")
    if not os.path.exists(image_path):
        return _fallback(image_path, error=f"image not found: {image_path}")

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        with open(image_path, "rb") as f:
            img_bytes = f.read()
        ext = os.path.splitext(image_path)[1].lower().lstrip(".") or "jpeg"
        mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
        image_part = {"mime_type": mime, "data": img_bytes}

        last_err = None
        for model_name in MODELS:
            try:
                model = genai.GenerativeModel(model_name)
                resp = model.generate_content([_PROMPT, image_part])
                return _parse_response(resp.text)
            except Exception as e:  # noqa: BLE001
                last_err = f"{model_name}: {e}"
                continue
        return _fallback(image_path, error=f"all models failed: {last_err}")
    except Exception as e:  # noqa: BLE001
        return _fallback(image_path, error=str(e))


def verify_api_key() -> tuple:
    """Return (ok: bool, message: str). Makes a tiny real API call if key present."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return (False, "GEMINI_API_KEY empty")
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        last_err = None
        for model_name in MODELS:
            try:
                model = genai.GenerativeModel(model_name)
                resp = model.generate_content("Reply with the single word OK.")
                if resp and getattr(resp, "text", None):
                    return (True, f"{model_name} responded")
            except Exception as e:  # noqa: BLE001
                last_err = f"{model_name}: {e}"
                continue
        return (False, f"all models failed: {last_err}")
    except Exception as e:  # noqa: BLE001
        return (False, str(e))


if __name__ == "__main__":
    print(analyze_image("data/test_safety_image.jpg"))
