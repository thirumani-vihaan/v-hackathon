"""Draw hazard bounding boxes on an image. Pure PIL, no Streamlit.

Gemini hazard bboxes are percentages [x1,y1,x2,y2] in 0..100. This converts
them to pixels and draws labeled rectangles. Returns a PIL.Image so callers
(UI or tests) can display or save it.
"""
import os
from PIL import Image, ImageDraw, ImageFont

_COLORS = {
    "smoke_fire": (220, 40, 40),
    "gas_leak_visual": (230, 120, 20),
    "electrical_hazard": (230, 200, 20),
    "no_helmet": (40, 120, 220),
    "unauthorized_person": (180, 60, 200),
    "unsafe_equipment": (230, 120, 20),
}
_DEFAULT_COLOR = (220, 40, 40)


def _font(size: int = 16):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def draw_hazards(image_path: str, hazards, out_path: str = None):
    """Return a PIL.Image with hazard boxes drawn. hazards is a list of objects
    (or dicts) exposing .type/.confidence/.bbox (bbox = 0..100 percentages).

    If the image cannot be opened, a small placeholder image is returned so the
    UI never crashes.
    """
    try:
        img = Image.open(image_path).convert("RGB")
    except Exception:
        img = Image.new("RGB", (480, 320), (235, 235, 235))
        d = ImageDraw.Draw(img)
        d.text((20, 150), "image unavailable", fill=(120, 0, 0), font=_font(18))
        return img

    w, h = img.size
    draw = ImageDraw.Draw(img)
    font = _font(max(12, w // 40))

    for hz in hazards or []:
        htype = getattr(hz, "type", None) if not isinstance(hz, dict) else hz.get("type")
        conf = getattr(hz, "confidence", None) if not isinstance(hz, dict) else hz.get("confidence")
        bbox = getattr(hz, "bbox", None) if not isinstance(hz, dict) else hz.get("bbox")
        if not bbox or len(bbox) != 4:
            continue
        x1 = _clamp(int(bbox[0] * w / 100.0), 0, w - 1)
        y1 = _clamp(int(bbox[1] * h / 100.0), 0, h - 1)
        x2 = _clamp(int(bbox[2] * w / 100.0), 0, w - 1)
        y2 = _clamp(int(bbox[3] * h / 100.0), 0, h - 1)
        if x2 < x1:
            x1, x2 = x2, x1
        if y2 < y1:
            y1, y2 = y2, y1
        color = _COLORS.get(htype, _DEFAULT_COLOR)
        for off in range(3):  # thick border
            draw.rectangle([x1 - off, y1 - off, x2 + off, y2 + off], outline=color)

        label = htype or "hazard"
        if isinstance(conf, (int, float)):
            label = f"{label} {conf:.2f}"
        tw = draw.textlength(label, font=font)
        th = (font.size + 4) if hasattr(font, "size") else 16
        ly = max(0, y1 - th)
        draw.rectangle([x1, ly, x1 + tw + 6, ly + th], fill=color)
        draw.text((x1 + 3, ly + 1), label, fill=(255, 255, 255), font=font)

    if out_path:
        try:
            os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
            img.save(out_path)
        except Exception:
            pass
    return img


if __name__ == "__main__":
    from schema import Hazard
    im = draw_hazards("data/test_safety_image.jpg",
                      [Hazard(type="smoke_fire", confidence=0.8, bbox=[10, 10, 60, 70])])
    print("drawn image size:", im.size)
