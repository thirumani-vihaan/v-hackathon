"""report_generator: OrchestratorResult -> PDF safety report."""
import os
from datetime import datetime

from schema import OrchestratorResult

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_OUT = os.path.join(_ROOT, "data", "safety_report.pdf")


def generate_report(result: OrchestratorResult, output_path: str = _DEFAULT_OUT) -> str:
    """Render an OrchestratorResult to a PDF. Returns the output path."""
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    )

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    styles = getSampleStyleSheet()
    h1 = styles["Title"]
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], spaceBefore=10)
    body = ParagraphStyle("B", parent=styles["BodyText"], fontSize=10, leading=14)

    flow = [
        Paragraph("IndustrialSafetyAI — Incident / Scan Report", h1),
        Paragraph(f"Request ID: {result.request_id}", body),
        Paragraph(f"Input type: {result.input_type}", body),
        Paragraph(f"Generated: {datetime.utcnow().isoformat()} UTC", body),
        Spacer(1, 0.2 * inch),
    ]

    if result.error:
        flow.append(Paragraph(f"<b>Run error:</b> {result.error}", body))
        flow.append(Spacer(1, 0.15 * inch))

    if result.safety is not None:
        s = result.safety
        flow.append(Paragraph("Safety Assessment", h2))
        flow.append(Paragraph(f"Zone: {s.zone}", body))
        flow.append(Paragraph(f"Risk score: <b>{s.risk_score}/100</b>", body))
        flow.append(Paragraph(f"Recommended action: {s.recommended_action}", body))
        if s.triggered_rules:
            flow.append(Paragraph("Triggered factors: "
                                  + ", ".join(s.triggered_rules), body))
        flow.append(Spacer(1, 0.15 * inch))

    if result.compliance is not None:
        c = result.compliance
        flow.append(Paragraph("Compliance", h2))
        flow.append(Paragraph(
            f"Status: {'PASS' if c.pass_status else 'FAIL'} | "
            f"Highest severity: {c.highest_severity or 'none'}", body))
        if c.violations:
            data = [["Rule", "Severity", "Name", "OISD Ref"]]
            for v in c.violations:
                data.append([v.rule_id, v.severity, v.name, v.oisd_reference])
            tbl = Table(data, colWidths=[0.7 * inch, 0.9 * inch, 2.8 * inch,
                                         1.8 * inch])
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            flow.append(tbl)
        flow.append(Spacer(1, 0.15 * inch))

    if result.vision is not None:
        v = result.vision
        flow.append(Paragraph("Vision Inspection", h2))
        flow.append(Paragraph(f"Source: {v.source}", body))
        flow.append(Paragraph(f"Summary: {v.summary}", body))
        for hz in v.hazards:
            flow.append(Paragraph(
                f"- {hz.type} (confidence {hz.confidence:.2f})", body))
        flow.append(Spacer(1, 0.15 * inch))

    if result.knowledge is not None:
        k = result.knowledge
        flow.append(Paragraph("Knowledge / Guidance", h2))
        flow.append(Paragraph(f"Confidence: {k.confidence}", body))
        flow.append(Paragraph(k.answer, body))
        for src in k.sources:
            flow.append(Paragraph(
                f"Source: {src.get('filename')} p.{src.get('page')}", body))

    doc = SimpleDocTemplate(output_path, pagesize=LETTER,
                            title="IndustrialSafetyAI Report")
    doc.build(flow)
    return output_path


if __name__ == "__main__":
    from schema import SafetyAlert
    r = OrchestratorResult(request_id="demo", input_type="sensor",
                           safety=SafetyAlert(risk_score=90, triggered_rules=["x"],
                                              recommended_action="STOP", zone="Z"))
    print(generate_report(r))
