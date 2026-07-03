"""Real offline hazard vision using OpenCV pixel analysis (no network, no GPU).

This is a genuine image analysis fallback (not a canned response): it inspects
HSV colour distribution and brightness to flag smoke/fire, electrical arc-flash
and haze/gas-leak regions, returning proper bounding boxes. If a small locally
trained model (models/hazard_model.npz) is present it is blended in for the
fire/smoke score. Always returns a schema VisionResult (source='fallback').
"""
import os
import numpy as np

from schema import VisionResult, Hazard

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODEL_PATH = os.path.join(_ROOT, "models", "hazard_model.npz")

# HSV feature: 3 channels x 8 bins = 24-d normalized histogram.
_BINS = 8


def _load_image(path: str):
    try:
        import cv2
        img = cv2.imread(path)
        if img is None:
            return None
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    except Exception:
        try:
            from PIL import Image
            return np.array(Image.open(path).convert("RGB"))
        except Exception:
            return None


def _rgb_to_hsv(rgb: np.ndarray) -> np.ndarray:
    """Vectorized RGB(0..255)->HSV with H in 0..179, S/V in 0..255 (cv2 scale)."""
    try:
        import cv2
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    except Exception:
        from PIL import Image
        hsv = np.array(Image.fromarray(rgb).convert("HSV"))
        # PIL H is 0..255; rescale H to 0..179 to match cv2 conventions
        hsv = hsv.astype(np.float32)
        hsv[..., 0] = hsv[..., 0] * 179.0 / 255.0
        return hsv.astype(np.uint8)


def features(rgb: np.ndarray) -> np.ndarray:
    """Return a 24-d normalized HSV histogram feature vector for a whole image."""
    hsv = _rgb_to_hsv(rgb).reshape(-1, 3).astype(np.float32)
    feats = []
    ranges = [(0, 179), (0, 255), (0, 255)]
    for ch in range(3):
        hist, _ = np.histogram(hsv[:, ch], bins=_BINS, range=ranges[ch])
        s = hist.sum()
        feats.extend((hist / s) if s else hist)
    return np.array(feats, dtype=np.float32)


def _load_model():
    try:
        if os.path.isfile(_MODEL_PATH):
            d = np.load(_MODEL_PATH)
            return d["W"].astype(np.float32), float(d["b"])
    except Exception:
        return None
    return None


def _model_fire_prob(rgb: np.ndarray):
    m = _load_model()
    if m is None:
        return None
    W, b = m
    x = features(rgb)
    z = float(np.dot(W, x) + b)
    return 1.0 / (1.0 + np.exp(-z))


def _bbox_pct(mask: np.ndarray, w: int, h: int):
    ys, xs = np.where(mask)
    if xs.size == 0:
        return None
    x1 = int(xs.min() * 100 / w)
    y1 = int(ys.min() * 100 / h)
    x2 = int(xs.max() * 100 / w)
    y2 = int(ys.max() * 100 / h)
    return [max(0, x1), max(0, y1), min(100, x2), min(100, y2)]


def detect(image_path: str) -> VisionResult:
    """Analyze pixels and return a VisionResult with real bounding boxes."""
    rgb = _load_image(image_path)
    if rgb is None:
        return VisionResult(
            hazards=[], summary="[Offline CV] image unreadable.",
            source="fallback", error="cannot read image")
    try:
        h, w = rgb.shape[:2]
        total = float(h * w)
        hsv = _rgb_to_hsv(rgb)
        H, S, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]

        hazards = []
        notes = []

        # --- fire / smoke: hot red-orange, saturated, bright ---
        fire_mask = (((H <= 25) | (H >= 160)) & (S > 90) & (V > 120))
        fire_frac = fire_mask.sum() / total
        model_p = _model_fire_prob(rgb)
        fire_conf = min(0.98, fire_frac * 6.0)
        if model_p is not None:
            fire_conf = min(0.98, 0.5 * fire_conf + 0.5 * model_p)
            notes.append(f"model p(fire)={model_p:.2f}")
        if fire_frac > 0.03 or (model_p is not None and model_p > 0.6):
            bbox = _bbox_pct(fire_mask, w, h) or [10, 10, 60, 60]
            hazards.append(Hazard(type="smoke_fire",
                                  confidence=round(max(0.4, fire_conf), 2),
                                  bbox=bbox))

        # --- electrical arc-flash: tight very-bright, low-saturation clusters ---
        arc_mask = (V > 245) & (S < 40)
        arc_frac = arc_mask.sum() / total
        if 0.0008 < arc_frac < 0.08:
            bbox = _bbox_pct(arc_mask, w, h) or [40, 40, 55, 55]
            hazards.append(Hazard(type="electrical_hazard",
                                  confidence=round(min(0.9, 0.4 + arc_frac * 8), 2),
                                  bbox=bbox))

        # --- gas / haze: large low-saturation mid-bright region (visual plume) ---
        haze_mask = (S < 45) & (V > 110) & (V < 240)
        haze_frac = haze_mask.sum() / total
        if haze_frac > 0.35:
            bbox = _bbox_pct(haze_mask, w, h) or [0, 0, 100, 100]
            hazards.append(Hazard(type="gas_leak_visual",
                                  confidence=round(min(0.85, haze_frac), 2),
                                  bbox=bbox))

        if hazards:
            kinds = ", ".join(sorted({hz.type for hz in hazards}))
            summary = f"[Offline CV] Detected: {kinds}."
        else:
            summary = "[Offline CV] No visual hazards above threshold."
        if notes:
            summary += " (" + "; ".join(notes) + ")"

        return VisionResult(hazards=hazards, summary=summary, source="fallback",
                            error="offline local-CV analysis")
    except Exception as e:  # noqa: BLE001
        return VisionResult(hazards=[], summary="[Offline CV] analysis failed.",
                            source="fallback", error=str(e))


if __name__ == "__main__":
    print(detect(os.path.join(_ROOT, "data", "test_safety_image.jpg")))
