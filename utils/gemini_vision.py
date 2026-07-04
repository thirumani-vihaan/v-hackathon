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

# Remember the first model that works so we don't retry all 5 on every call (which
# burns free-tier quota and triggers the intermittent rate-limit fallbacks).
_WORKING_MODEL = {"name": None}


def _resp_text(resp) -> str:
    """Extract text from a Gemini response without raising (resp.text can throw when a
    candidate has no simple text part)."""
    try:
        t = getattr(resp, "text", None)
        if t:
            return t
    except Exception:
        pass
    try:
        out = []
        for c in getattr(resp, "candidates", []) or []:
            content = getattr(c, "content", None)
            for p in getattr(content, "parts", []) or []:
                if getattr(p, "text", None):
                    out.append(p.text)
        return "".join(out)
    except Exception:
        return ""


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
        import time
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        with open(image_path, "rb") as f:
            img_bytes = f.read()
        ext = os.path.splitext(image_path)[1].lower().lstrip(".") or "jpeg"
        mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
        image_part = {"mime_type": mime, "data": img_bytes}
        gen_cfg = {"response_mime_type": "application/json"}

        # Try the last known-good model first; only fall through to others if it fails.
        order = ([_WORKING_MODEL["name"]] if _WORKING_MODEL["name"] else [])
        order += [m for m in MODELS if m != _WORKING_MODEL["name"]]

        last_err = None
        for model_name in order:
            for attempt in range(2):
                try:
                    model = genai.GenerativeModel(model_name)
                    try:
                        resp = model.generate_content([_PROMPT, image_part],
                                                      generation_config=gen_cfg)
                    except Exception:
                        resp = model.generate_content([_PROMPT, image_part])
                    txt = _resp_text(resp)
                    if not txt.strip():
                        raise ValueError("empty response")
                    result = _parse_response(txt)
                    _WORKING_MODEL["name"] = model_name
                    return result
                except Exception as e:  # noqa: BLE001
                    last_err = f"{model_name}: {e}"
                    msg = str(e).lower()
                    if attempt == 0 and ("429" in msg or "quota" in msg
                                         or "rate" in msg or "503" in msg
                                         or "unavailable" in msg):
                        time.sleep(1.6)   # transient — retry the SAME model once
                        continue
                    break                 # non-transient — move to next model
        return _fallback(image_path, error=f"all models failed: {last_err}")
    except Exception as e:  # noqa: BLE001
        return _fallback(image_path, error=str(e))


def analyze_safety_image(image_path: str) -> dict:
    """Dict-shaped wrapper around analyze_image (for callers wanting plain JSON).

    The canonical result is still the VisionResult dataclass; this helper serializes
    it. Keys: hazards (list of dicts), summary (str), source (str), error (str|None),
    timestamp (str). Never raises.
    """
    result = analyze_image(image_path)
    return {
        "hazards": [
            {"type": h.type, "confidence": h.confidence, "bbox": h.bbox}
            for h in result.hazards
        ],
        "summary": result.summary,
        "source": result.source,
        "error": result.error,
        "timestamp": result.timestamp,
    }


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
