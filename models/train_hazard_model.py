"""Train a tiny, reproducible offline hazard classifier (CPU, seconds).

Unlike AgriBloom's 91k-image EfficientNet that needs a GPU and an external
dataset download, this trains a lightweight logistic-regression classifier on
*synthetic* fire/smoke vs. normal imagery in a few seconds on CPU, using the
exact same HSV histogram features as utils/local_vision.features(). The result
(models/hazard_model.npz) is loaded by local_vision to blend a learned
fire/smoke probability into the offline detector.

Run:  python models/train_hazard_model.py
"""
import os
import sys
import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from utils.local_vision import features, _BINS  # noqa: E402

RNG = np.random.default_rng(42)
OUT = os.path.join(_ROOT, "models", "hazard_model.npz")
IMG = 48  # synthetic image side


def _synth_image(kind: str) -> np.ndarray:
    """Generate a small synthetic RGB image of a given class."""
    if kind == "fire":
        base = np.zeros((IMG, IMG, 3), dtype=np.float32)
        base[..., 0] = RNG.uniform(180, 255)          # strong red
        base[..., 1] = RNG.uniform(60, 170)           # some green -> orange
        base[..., 2] = RNG.uniform(0, 60)             # low blue
    elif kind == "smoke":
        g = RNG.uniform(90, 190)
        base = np.stack([np.full((IMG, IMG), g)] * 3, axis=-1).astype(np.float32)
    else:  # normal industrial scene: greys/greens/blues
        base = np.zeros((IMG, IMG, 3), dtype=np.float32)
        base[..., 0] = RNG.uniform(20, 120)
        base[..., 1] = RNG.uniform(60, 180)
        base[..., 2] = RNG.uniform(60, 200)
    noise = RNG.normal(0, 18, base.shape)
    return np.clip(base + noise, 0, 255).astype(np.uint8)


def _dataset(n_per: int = 220):
    X, y = [], []
    for kind, label in (("fire", 1), ("smoke", 1), ("normal", 0)):
        for _ in range(n_per):
            X.append(features(_synth_image(kind)))
            y.append(label)
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)


def _train(X, y, epochs=400, lr=0.5, l2=1e-3):
    n, d = X.shape
    W = np.zeros(d, dtype=np.float32)
    b = 0.0
    for _ in range(epochs):
        z = X @ W + b
        p = 1.0 / (1.0 + np.exp(-z))
        gW = X.T @ (p - y) / n + l2 * W
        gb = float(np.mean(p - y))
        W -= lr * gW
        b -= lr * gb
    return W, b


def main():
    X, y = _dataset()
    W, b = _train(X, y)
    p = 1.0 / (1.0 + np.exp(-(X @ W + b)))
    acc = float(np.mean((p > 0.5) == (y > 0.5)))
    np.savez(OUT, W=W.astype(np.float32), b=np.float32(b),
             bins=np.int32(_BINS), accuracy=np.float32(acc))
    print(f"Trained hazard model: {len(y)} samples, "
          f"train accuracy {acc:.3f} -> {OUT}")


if __name__ == "__main__":
    main()
