"""Train the offline hazard classifier on a diverse synthetic dataset (CPU, seconds).

Why synthetic: the platform must run fully offline with no dataset download. To make
the model accurate on REAL photos (and not flag album covers, sunsets, or colourful
scenes as fire), the training set pairs realistic *localized, high-contrast* flames and
smoke plumes against a wide range of HARD NEGATIVES — colourful gradients, multi-blob
"album art", warm-but-diffuse scenes, metallic/industrial greys, blue/green scenes, and
noise. The model learns that fire is a concentrated, high-contrast hot region, not merely
warm colour. Features come from utils/local_vision.features(); inputs are standardized and
mu/sigma are saved alongside W/b.

Run:  python models/train_hazard_model.py
"""
import os
import sys
import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from utils.local_vision import features  # noqa: E402

RNG = np.random.default_rng(42)
OUT = os.path.join(_ROOT, "models", "hazard_model.npz")
IMG = 56


def _noise(img):
    return np.clip(img + RNG.normal(0, RNG.uniform(6, 22), img.shape), 0, 255).astype(np.uint8)


def _flame():
    """A localized, high-contrast flame on a dark background (hot core -> orange -> red)."""
    img = np.zeros((IMG, IMG, 3), np.float32)
    img[..., :] = RNG.uniform(0, 45, 3)  # dark background
    cx, cy = RNG.integers(IMG // 4, 3 * IMG // 4, 2)
    rad = RNG.integers(IMG // 6, IMG // 2)
    yy, xx = np.ogrid[:IMG, :IMG]
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    inten = np.clip(1 - d / rad, 0, 1)
    m = d < rad
    img[..., 0] = np.where(m, 200 + 55 * inten, img[..., 0])
    img[..., 1] = np.where(m, 40 + 170 * inten, img[..., 1])   # core -> yellow
    img[..., 2] = np.where(m, 25 * inten, img[..., 2])
    return _noise(img)


def _smoke():
    """A grey plume (upper) sometimes over a small fire base."""
    img = np.full((IMG, IMG, 3), RNG.uniform(15, 55), np.float32)
    g = RNG.uniform(95, 195)
    cx = RNG.integers(IMG // 4, 3 * IMG // 4)
    yy, xx = np.ogrid[:IMG, :IMG]
    d = np.sqrt((xx - cx) ** 2 + ((yy - IMG // 3) * 1.6) ** 2)
    m = d < RNG.integers(IMG // 4, IMG // 2)
    for c in range(3):
        img[..., c] = np.where(m, g + RNG.uniform(-15, 15), img[..., c])
    if RNG.random() < 0.5:  # small fire base
        img[int(IMG * 0.75):, IMG // 2 - 5:IMG // 2 + 5, 0] = 230
        img[int(IMG * 0.75):, IMG // 2 - 5:IMG // 2 + 5, 1] = 120
    return _noise(img)


def _neg_solid():
    return _noise(np.full((IMG, IMG, 3), RNG.uniform(0, 255, 3), np.float32))


def _neg_gradient():
    a, b = RNG.uniform(0, 255, 3), RNG.uniform(0, 255, 3)
    t = np.linspace(0, 1, IMG)[:, None] if RNG.random() < 0.5 else np.linspace(0, 1, IMG)[None, :]
    img = a[None, None, :] * (1 - t[..., None]) + b[None, None, :] * t[..., None]
    return _noise(np.broadcast_to(img, (IMG, IMG, 3)).astype(np.float32))


def _neg_blobs():
    """Colourful multi-blob 'album art'."""
    img = np.full((IMG, IMG, 3), RNG.uniform(0, 255, 3), np.float32)
    for _ in range(RNG.integers(3, 7)):
        cx, cy = RNG.integers(0, IMG, 2)
        rad = RNG.integers(IMG // 6, IMG // 2)
        col = RNG.uniform(0, 255, 3)
        yy, xx = np.ogrid[:IMG, :IMG]
        m = ((xx - cx) ** 2 + (yy - cy) ** 2) < rad ** 2
        for c in range(3):
            img[..., c] = np.where(m, col[c], img[..., c])
    return _noise(img)


def _neg_warm_diffuse():
    """Warm/orange but uniform and low-contrast (sunset / warm album) — the classic
    false positive for a naive detector."""
    base = np.array([RNG.uniform(180, 255), RNG.uniform(90, 170), RNG.uniform(20, 110)])
    img = np.full((IMG, IMG, 3), base, np.float32)
    t = np.linspace(0.7, 1.0, IMG)[:, None, None]
    return _noise(img * t)


def _neg_cool():
    base = np.array([RNG.uniform(0, 90), RNG.uniform(60, 200), RNG.uniform(80, 230)])
    return _noise(np.full((IMG, IMG, 3), base, np.float32))


def _neg_metal():
    g = RNG.uniform(60, 190)
    return _noise(np.full((IMG, IMG, 3), [g, g + RNG.uniform(-10, 10), g + RNG.uniform(-10, 10)], np.float32))


def _neg_noise():
    return RNG.integers(0, 256, (IMG, IMG, 3), dtype=np.uint8)


_POS = [_flame, _smoke]
_NEG = [_neg_solid, _neg_gradient, _neg_blobs, _neg_warm_diffuse, _neg_cool, _neg_metal, _neg_noise]


def _dataset(n_pos=700, n_neg=900):
    X, y = [], []
    for _ in range(n_pos):
        X.append(features(RNG.choice(_POS)())); y.append(1)
    for _ in range(n_neg):
        X.append(features(RNG.choice(_NEG)())); y.append(0)
    return np.array(X, np.float32), np.array(y, np.float32)


def _train(X, y, epochs=800, lr=0.4, l2=2e-3):
    n, d = X.shape
    W, b = np.zeros(d, np.float32), 0.0
    for _ in range(epochs):
        p = 1.0 / (1.0 + np.exp(-(X @ W + b)))
        W -= lr * (X.T @ (p - y) / n + l2 * W)
        b -= lr * float(np.mean(p - y))
    return W, b


def main():
    X, y = _dataset()
    mu, sigma = X.mean(0), X.std(0)
    sigma = np.where(sigma < 1e-6, 1.0, sigma)
    Xs = (X - mu) / sigma
    # held-out split for an honest accuracy figure
    idx = RNG.permutation(len(y))
    cut = int(0.8 * len(y))
    tr, te = idx[:cut], idx[cut:]
    W, b = _train(Xs[tr], y[tr])
    pte = 1.0 / (1.0 + np.exp(-(Xs[te] @ W + b)))
    acc = float(np.mean((pte > 0.5) == (y[te] > 0.5)))
    np.savez(OUT, W=W.astype(np.float32), b=np.float32(b),
             mu=mu.astype(np.float32), sigma=sigma.astype(np.float32),
             accuracy=np.float32(acc))
    print(f"Trained hazard model: {len(y)} samples ({int(y.sum())} pos / "
          f"{int(len(y) - y.sum())} neg), held-out accuracy {acc:.3f} -> {OUT}")


if __name__ == "__main__":
    main()
