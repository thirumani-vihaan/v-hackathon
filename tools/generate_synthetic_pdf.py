"""Generate a multi-page synthetic safety manual PDF and a test image.

Produces:
  knowledge_base/raw/synthetic_safety.pdf  (reportlab)
  data/test_safety_image.jpg               (Pillow)
"""
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(_ROOT, "knowledge_base", "raw")
DATA_DIR = os.path.join(_ROOT, "data")
PDF_PATH = os.path.join(RAW_DIR, "synthetic_safety.pdf")
IMG_PATH = os.path.join(DATA_DIR, "test_safety_image.jpg")


SECTIONS = [
    (
        "Permit to Work System (OISD-STD-105 Sec 4.1)",
        [
            "The Permit to Work (PTW) system controls all non-routine work in a "
            "hazardous facility. No work shall commence in a process area without a "
            "valid, signed permit issued by the area authority.",
            "Every permit must specify the permit type, the zone, the maximum number "
            "of workers, and the required precautions. Workers present in a zone with "
            "no active permit constitutes a critical violation under Sec 4.1.1.",
            "Recognized permit types include hot_work, confined_space, electrical, "
            "excavation, cold_work, and working_at_height. Unrecognized permit types "
            "must be verified with the issuing authority (Sec 4.1.3).",
        ],
    ),
    (
        "Hot Work and Gas Testing (OISD-STD-105 Sec 8.1)",
        [
            "Hot work covers welding, cutting, grinding and any spark-producing "
            "activity. A gas test must be performed immediately before and "
            "periodically during hot work.",
            "Hot work is prohibited when combustible gas concentration exceeds 50 ppm "
            "(Sec 8.1.1). At concentrations above 10 ppm a fire watch must be posted "
            "and the atmosphere re-tested (Sec 8.1.2).",
            "Ambient temperature above 45 C during hot work increases heat stress and "
            "ignition risk; frequent breaks are required (Sec 8.3.1). Work is suspended "
            "above 55 C (Sec 8.3.4).",
        ],
    ),
    (
        "Confined Space Entry (OISD-STD-105 Sec 7.4)",
        [
            "A confined space has limited entry/exit and is not designed for "
            "continuous occupancy. Entry requires a dedicated confined space permit.",
            "Confined space entry is strictly prohibited without a standby rescue team "
            "present at the entry point (Sec 7.4.2). This is a critical, non-waivable "
            "requirement.",
            "No more than two workers should occupy a confined space simultaneously to "
            "keep rescue feasible (Sec 7.4.5). Continuous atmospheric monitoring for "
            "oxygen and toxic gas is mandatory throughout the entry.",
        ],
    ),
    (
        "Oxygen Deficiency and Enrichment (OISD-STD-105 Sec 6.1)",
        [
            "Normal atmospheric oxygen is 20.9%. The safe entry range is 19.5% to "
            "23.5%. Oxygen below 18.0% is immediately dangerous to life and health "
            "(Sec 6.1.1) and requires evacuation and SCBA.",
            "Oxygen between 18.0% and 19.5% is a warning band (Sec 6.1.2): ventilate "
            "and re-test before continued occupancy.",
            "Oxygen above 23.5% is an enrichment hazard that dramatically increases "
            "fire risk (Sec 6.1.4). Elevated gas above 40 ppm together with oxygen "
            "below 19.5% indicates oxygen displacement (Sec 6.2.1) — evacuate "
            "immediately.",
        ],
    ),
    (
        "Emergency Response and Evacuation (OISD-STD-105 Sec 12.0)",
        [
            "On any STOP WORK condition, workers evacuate to the designated muster "
            "point via the nearest safe egress. The area authority accounts for all "
            "personnel using the permit register.",
            "Emergency response includes isolating the hazard source, activating "
            "ventilation, and summoning the rescue team. Do not re-enter until the "
            "atmosphere is re-tested and declared safe.",
            "All critical violations (oxygen below 18%, gas above 100 ppm, confined "
            "space entry without rescue) trigger immediate evacuation and an incident "
            "report.",
        ],
    ),
]


def build_pdf():
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    )

    os.makedirs(RAW_DIR, exist_ok=True)
    styles = getSampleStyleSheet()
    h = ParagraphStyle("Heading", parent=styles["Heading1"], fontSize=15,
                       spaceAfter=12)
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=11,
                          leading=16, spaceAfter=10)

    doc = SimpleDocTemplate(PDF_PATH, pagesize=LETTER,
                            title="Industrial Safety Manual (Synthetic)")
    flow = [
        Paragraph("Industrial Safety Operating Manual", styles["Title"]),
        Paragraph("Synthetic reference derived from OISD-STD-105 (fictional "
                  "section numbers for testing).", body),
        Spacer(1, 0.3 * inch),
    ]
    for i, (title, paras) in enumerate(SECTIONS):
        flow.append(Paragraph(title, h))
        for p in paras:
            flow.append(Paragraph(p, body))
        if i < len(SECTIONS) - 1:
            flow.append(PageBreak())
    doc.build(flow)
    return PDF_PATH


def build_image():
    from PIL import Image, ImageDraw
    os.makedirs(DATA_DIR, exist_ok=True)
    img = Image.new("RGB", (640, 480), color=(40, 44, 52))
    d = ImageDraw.Draw(img)
    d.rectangle([20, 20, 620, 460], outline=(255, 200, 0), width=4)
    d.text((60, 200), "SAFETY TEST IMAGE - ZONE A", fill=(255, 255, 255))
    d.text((60, 240), "worker / no helmet / gas leak", fill=(255, 120, 120))
    img.save(IMG_PATH, "JPEG", quality=85)
    return IMG_PATH


if __name__ == "__main__":
    print("PDF:", build_pdf())
    print("IMG:", build_image())
