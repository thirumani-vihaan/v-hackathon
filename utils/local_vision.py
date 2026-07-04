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
    """Return a 21-d feature vector describing the image for the hazard model.

    Combines a coarse HSV histogram with FIRE-SPECIFIC spatial cues so that a real
    (localized, high-contrast) flame is separable from a merely warm/colourful image
    such as an album cover or a sunset: 16 histogram bins + fire-pixel fraction +
    fire localisation (max fire density over a 4x4 grid) + brightness variance +
    mean saturation + edge density.
    """
    hsv = _rgb_to_hsv(rgb)
    H = hsv[..., 0].astype(np.float32)
    S = hsv[..., 1].astype(np.float32)
    V = hsv[..., 2].astype(np.float32)
    feats = []
    for ch, bins, hi in ((H, 8, 179), (S, 4, 255), (V, 4, 255)):
        hist, _ = np.histogram(ch, bins=bins, range=(0, hi))
        s = hist.sum()
        feats.extend((hist / s) if s else hist)
    total = float(H.size)
    fire = (((H <= 22) | (H >= 162)) & (S > 110) & (V > 130))
    fire_frac = fire.sum() / total
    h, w = H.shape
    gh, gw = max(1, h // 4), max(1, w // 4)
    local = 0.0
    for i in range(4):
        for j in range(4):
            cell = fire[i * gh:(i + 1) * gh, j * gw:(j + 1) * gw]
            if cell.size:
                local = max(local, float(cell.mean()))
    v_std = float(np.std(V)) / 128.0
    s_mean = float(np.mean(S)) / 255.0
    gx = np.abs(np.diff(V, axis=1))
    gy = np.abs(np.diff(V, axis=0))
    edge = (float((gx > 40).mean()) + float((gy > 40).mean())) / 2.0
    feats.extend([fire_frac, local, v_std, s_mean, edge])
    return np.array(feats, dtype=np.float32)


def _load_model():
    try:
        if os.path.isfile(_MODEL_PATH):
            d = np.load(_MODEL_PATH)
            W = d["W"].astype(np.float32)
            b = float(d["b"])
            mu = d["mu"].astype(np.float32) if "mu" in d.files else None
            sigma = d["sigma"].astype(np.float32) if "sigma" in d.files else None
            return W, b, mu, sigma
    except Exception:
        return None
    return None


def _model_fire_prob(rgb: np.ndarray):
    m = _load_model()
    if m is None:
        return None
    W, b, mu, sigma = m
    x = features(rgb)
    if x.shape[0] != W.shape[0]:   # feature/model version mismatch — ignore stale model
        return None
    if mu is not None and sigma is not None:
        sigma = np.where(sigma < 1e-6, 1.0, sigma)
        x = (x - mu) / sigma
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

        # --- fire / smoke: decided by the trained model (a localized, high-contrast
        #     flame), gated by the presence of fire-coloured pixels. Warm/colourful but
        #     diffuse images (album covers, sunsets) score low and are not flagged. ---
        fire_mask = (((H <= 22) | (H >= 162)) & (S > 110) & (V > 130))
        fire_frac = fire_mask.sum() / total
        model_p = _model_fire_prob(rgb)
        if model_p is not None:
            notes.append(f"model p(fire)={model_p:.2f}")
        model_fire = (model_p is not None and model_p >= 0.6 and fire_frac > 0.02)
        heuristic_fire = (model_p is None and fire_frac > 0.12)  # only if no model present
        if model_fire or heuristic_fire:
            conf = (model_p if model_p is not None else min(0.9, 0.5 + fire_frac * 0.4))
            conf = max(0.5, min(0.98, conf))
            bbox = _bbox_pct(fire_mask, w, h) or [10, 10, 60, 60]
            hazards.append(Hazard(type="smoke_fire", confidence=round(conf, 2),
                                  bbox=bbox))

        # --- electrical arc-flash: tight, very-bright, near-white cluster (rare) ---
        arc_mask = (V > 248) & (S < 30)
        arc_frac = arc_mask.sum() / total
        if 0.003 < arc_frac < 0.04:
            bbox = _bbox_pct(arc_mask, w, h) or [40, 40, 55, 55]
            hazards.append(Hazard(type="electrical_hazard",
                                  confidence=round(min(0.9, 0.45 + arc_frac * 9), 2),
                                  bbox=bbox))

        # --- gas / haze: a large, uniform low-saturation mid-bright plume with real
        #     texture (a flat wall/gray background has near-zero variance -> not a plume) ---
        haze_mask = (S < 38) & (V > 120) & (V < 235)
        haze_frac = haze_mask.sum() / total
        v_std = float(np.std(V.astype(np.float32)))
        if 0.55 < haze_frac < 0.9 and v_std > 14:
            bbox = _bbox_pct(haze_mask, w, h) or [0, 0, 100, 100]
            hazards.append(Hazard(type="gas_leak_visual",
                                  confidence=round(min(0.85, haze_frac), 2),
                                  bbox=bbox))

        # Precision filter: keep only confident detections, strongest first (avoid
        # crying wolf with several weak, contradictory boxes).
        hazards = sorted([hz for hz in hazards if hz.confidence >= 0.5],
                         key=lambda hz: -hz.confidence)[:2]

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
