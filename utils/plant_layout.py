"""Generate a simple labeled plant-layout PNG for the Folium ImageOverlay."""
import os
from PIL import Image, ImageDraw, ImageFont

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_PATH = os.path.join(_ROOT, "data", "plant_layout.png")

# (label, box as fractions x0,y0,x1,y1, fill RGBA)
_ZONES = [
    ("Zone A - Tank Farm", (0.04, 0.06, 0.47, 0.47), (60, 140, 200)),
    ("Zone B - Process / Coke", (0.53, 0.06, 0.96, 0.47), (200, 90, 60)),
    ("Zone C - Confined Vessel", (0.04, 0.53, 0.47, 0.94), (150, 110, 190)),
    ("Zone D - Substation", (0.53, 0.53, 0.96, 0.94), (210, 180, 60)),
]


def _font(size):
    try:
        return ImageFont.truetype("arialbd.ttf", size)
    except Exception:
        try:
            return ImageFont.truetype("arial.ttf", size)
        except Exception:
            return ImageFont.load_default()


def ensure_plant_layout(path: str = _DEFAULT_PATH, force: bool = False,
                        size: int = 720) -> str:
    """Create the plant layout image if missing. Returns the path."""
    if os.path.isfile(path) and not force:
        return path
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    w = h = size
    img = Image.new("RGBA", (w, h), (245, 245, 245, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([2, 2, w - 3, h - 3], outline=(80, 80, 80), width=3)
    title_font = _font(max(16, size // 30))
    label_font = _font(max(14, size // 34))
    draw.text((14, 8), "VIZAG REFINERY - PLANT LAYOUT", fill=(30, 30, 30),
              font=title_font)

    for label, (fx0, fy0, fx1, fy1), color in _ZONES:
        x0, y0, x1, y1 = int(fx0 * w), int(fy0 * h), int(fx1 * w), int(fy1 * h)
        fill = color + (70,)
        draw.rectangle([x0, y0, x1, y1], fill=fill, outline=color + (255,), width=4)
        draw.text((x0 + 12, y0 + 10), label, fill=(20, 20, 20), font=label_font)

    img.save(path)
    return path


if __name__ == "__main__":
    print(ensure_plant_layout(force=True))
