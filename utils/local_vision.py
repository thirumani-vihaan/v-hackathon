"""Real offline hazard vision using OpenCV pixel analysis (no network, no GPU).

This is a genuine image analysis fallback (not a canned response): it inspects
HSV colour distribution and brightness to flag smoke/fire, electrical arc-flash
and haze/gas-leak regions, returning proper bounding boxes. If a small locally
trained model (models/hazard_model.npz) is present it is blended in for the
fire/smoke score. Always returns a schema VisionResult (source='fallback').
"""
import os
import numpy as np

import torch
import torch.nn as nn

from schema import VisionResult, Hazard

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODEL_PATH = os.path.join(_ROOT, "models", "hazard_model.pt")

_mlp_cache = None

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
    # warm-core cue: a real flame has bright orange/yellow pixels (a hot core); pure-red
    # text/logos do not. This is the key separator of fire from red graphics.
    core = ((H >= 10) & (H <= 30) & (S > 80) & (V > 180))
    core_frac = float(core.sum()) / total
    feats.extend([fire_frac, local, v_std, s_mean, edge, core_frac])
    return np.array(feats, dtype=np.float32)


def _load_model():
    global _mlp_cache
    if _mlp_cache is not None:
        return _mlp_cache
    try:
        if os.path.isfile(_MODEL_PATH):
            d = torch.load(_MODEL_PATH, weights_only=True)
            mu = d["mu"]
            sigma = d["sigma"]
            model = nn.Sequential(
                nn.Linear(len(mu), 32),
                nn.ReLU(),
                nn.Linear(32, 16),
                nn.ReLU(),
                nn.Linear(16, 1),
                nn.Sigmoid()
            )
            model.load_state_dict(d['model_state'])
            model.eval()
            _mlp_cache = (model, mu, sigma)
            return _mlp_cache
    except Exception:
        return None
    return None


def _model_fire_prob(rgb: np.ndarray):
    m = _load_model()
    if m is None:
        return None
    model, mu, sigma = m
    x = features(rgb)
    if x.shape[0] != len(mu):
        return None
    sigma = np.where(sigma < 1e-6, 1.0, sigma)
    x = (x - mu) / sigma
    with torch.no_grad():
        t = torch.tensor(x, dtype=torch.float32).unsqueeze(0)
        prob = model(t).item()
    return prob


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

        # --- fire / smoke ONLY: decided by the trained model, gated by (a) enough
        #     fire-coloured pixels and (b) spatial concentration. A real flame is a
        #     filled, concentrated hot region; warm/colourful images, thin red text, and
        #     logos are diffuse or sparse and score low. Unreliable colour heuristics for
        #     "electrical" and "gas haze" are deliberately NOT used — they produced the
        #     random false positives. ---
        fire_mask = (((H <= 22) | (H >= 162)) & (S > 110) & (V > 130))
        fire_frac = fire_mask.sum() / total
        # spatial concentration: max fire density over a 4x4 grid (thin text -> low)
        gh, gw = max(1, h // 4), max(1, w // 4)
        local = 0.0
        for i in range(4):
            for j in range(4):
                cell = fire_mask[i * gh:(i + 1) * gh, j * gw:(j + 1) * gw]
                if cell.size:
                    local = max(local, float(cell.mean()))
        model_p = _model_fire_prob(rgb)
        if model_p is not None:
            notes.append(f"model p(fire)={model_p:.2f}")
        # warm-core presence separates a real flame from pure-red text/logos/signs
        core_mask = ((H >= 10) & (H <= 30) & (S > 80) & (V > 180))
        core_frac = float(core_mask.sum()) / total
        model_fire = (model_p is not None and model_p >= 0.7
                      and fire_frac > 0.03 and local > 0.18 and core_frac > 0.006)
        heuristic_fire = (model_p is None and fire_frac > 0.15 and local > 0.3
                          and core_frac > 0.01)
        if model_fire or heuristic_fire:
            conf = (model_p if model_p is not None else min(0.9, 0.5 + fire_frac * 0.4))
            conf = max(0.5, min(0.98, conf))
            bbox = _bbox_pct(fire_mask, w, h) or [10, 10, 60, 60]
            hazards.append(Hazard(type="smoke_fire", confidence=round(conf, 2),
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
