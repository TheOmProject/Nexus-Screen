"""Brushed graphite texture, generated once per size and cached."""
import numpy as np
from PyQt6.QtGui import QImage, QPixmap

_cache = {}


def brushed_pixmap(w, h, base=13, spread=9, seed=7):
    """Horizontal brushed-metal streaks: per-pixel noise box-blurred along x."""
    key = (w, h, base, spread, seed)
    px = _cache.get(key)
    if px is not None:
        return px
    rng = np.random.default_rng(seed)
    noise = rng.random((h, w + 120), dtype=np.float32)
    k = 120
    c = np.cumsum(noise, axis=1)
    streak = (c[:, k:] - c[:, :-k])[:, :w] / k            # long horizontal blur
    streak = (streak - streak.mean()) / (streak.std() + 1e-6)
    rows = rng.normal(0, 0.35, (h, 1)).astype(np.float32)  # faint per-row banding
    fine = rng.normal(0, 0.25, (h, w)).astype(np.float32)
    v = base + spread * 0.33 * (streak + rows + fine)
    # soft vertical sheen, brighter towards the top like the references
    v += np.linspace(spread * 0.45, -spread * 0.2, h, dtype=np.float32)[:, None]
    img8 = np.clip(v, 0, 255).astype(np.uint8)
    img8 = np.ascontiguousarray(img8)
    qimg = QImage(img8.data, w, h, w, QImage.Format.Format_Grayscale8).copy()
    px = QPixmap.fromImage(qimg)
    _cache[key] = px
    return px
