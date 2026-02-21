import io
from datetime import datetime
from typing import Optional
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import structlog

logger = structlog.get_logger()

RISK_COLORS = {
    "LOW": colors.HexColor("#22c55e"),
    "MEDIUM": colors.HexColor("#f59e0b"),
    "HIGH": colors.HexColor("#ef4444"),
}

MODULE_NAMES = {
    "ai_detection": "AI Content Detection",
    "plagiarism": "Plagiarism Analysis",
    "writing_profile": "Writing Style Profile",
    "proctoring": "Behavioral Proctoring",
}


def generate_pdf_report(report_data: dict, submission_data: dict) -> bytes:
    """Generate a professional PDF integrity report."""
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    story = []

    # ── Header ──────────────────────────────────────────────────────────────
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Title"],
        fontSize=20,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#64748b"),
        alignment=TA_CENTER,
    )

    story.append(Paragraph("Academic Integrity Report", title_style))
    story.append(Paragraph(
        f"Generated: {datetime.utcnow().strftime('%B %d, %Y at %H:%M UTC')}",
        subtitle_style,
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#e2e8f0")))
    story.append(Spacer(1, 0.2 * inch))

    # ── Submission Info ──────────────────────────────────────────────────────
    risk_level = report_data.get("risk_level", "LOW")
    integrity_score = report_data.get("integrity_score", 0.0)
    risk_color = RISK_COLORS.get(risk_level, colors.grey)

    info_data = [
        ["Submission ID", submission_data.get("id", "N/A")],
        ["File", submission_data.get("original_filename", "N/A")],
        ["Word Count", str(submission_data.get("word_count", "N/A"))],
        ["Student", submission_data.get("student_email", "N/A")],
        ["Assignment", submission_data.get("assignment_id", "N/A")],
        ["Status", submission_data.get("status", "done").upper()],
    ]

    info_table = Table(info_data, colWidths=[2 * inch, 4.5 * inch])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#475569")),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.3 * inch))

    # ── Score Summary ────────────────────────────────────────────────────────
    h2 = ParagraphStyle("H2", parent=styles["Heading2"],
                        textColor=colors.HexColor("#1e293b"), fontSize=14)
    story.append(Paragraph("Overall Risk Assessment", h2))
    story.append(Spacer(1, 0.1 * inch))

    score_pct = int(integrity_score * 100)
    score_data = [
        [
            Paragraph(f"<b>Integrity Score</b>", styles["Normal"]),
            Paragraph(f"<b>{score_pct}%</b>", styles["Normal"]),
        ],
        [
            Paragraph("<b>Risk Level</b>", styles["Normal"]),
            Paragraph(f"<b>{risk_level}</b>", styles["Normal"]),
        ],
        [
            Paragraph("<b>Confidence</b>", styles["Normal"]),
            Paragraph(
                f"{int(report_data.get('confidence', 0) * 100)}%",
                styles["Normal"]
            ),
        ],
    ]
    score_table = Table(score_data, colWidths=[3 * inch, 3.5 * inch])
    score_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("BACKGROUND", (1, 1), (1, 1), risk_color),
        ("TEXTCOLOR", (1, 1), (1, 1), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 0.15 * inch))

    rec = report_data.get("recommendation", "")
    if rec:
        rec_style = ParagraphStyle(
            "Rec",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#334155"),
            backColor=colors.HexColor("#f8fafc"),
            borderPad=8,
            leading=14,
        )
        story.append(Paragraph(f"<i>Recommendation: {rec}</i>", rec_style))
    story.append(Spacer(1, 0.3 * inch))

    # ── Module Results ───────────────────────────────────────────────────────
    story.append(Paragraph("Module Analysis Results", h2))
    story.append(Spacer(1, 0.1 * inch))

    modules = report_data.get("breakdown", {})
    module_rows = [["Module", "Score", "Weight", "Confidence", "Status"]]

    for mod_id, data in modules.items():
        score_val = data.get("score", 0.0)
        module_rows.append([
            MODULE_NAMES.get(mod_id, mod_id),
            f"{int(score_val * 100)}%",
            f"{data.get('weight', 0):.2f}",
            f"{int(data.get('confidence', 0) * 100)}%",
            "HIGH RISK" if score_val >= 0.65 else ("FLAGGED" if score_val >= 0.35 else "CLEAN"),
        ])

    mod_table = Table(
        module_rows,
        colWidths=[2.2 * inch, 1 * inch, 1 * inch, 1 * inch, 1.3 * inch]
    )
    mod_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))

    # Color the status cells
    for i, (mod_id, data) in enumerate(modules.items(), start=1):
        score_val = data.get("score", 0.0)
        if score_val >= 0.65:
            mod_table.setStyle(TableStyle([
                ("BACKGROUND", (4, i), (4, i), RISK_COLORS["HIGH"]),
                ("TEXTCOLOR", (4, i), (4, i), colors.white),
            ]))
        elif score_val >= 0.35:
            mod_table.setStyle(TableStyle([
                ("BACKGROUND", (4, i), (4, i), RISK_COLORS["MEDIUM"]),
                ("TEXTCOLOR", (4, i), (4, i), colors.white),
            ]))
        else:
            mod_table.setStyle(TableStyle([
                ("BACKGROUND", (4, i), (4, i), RISK_COLORS["LOW"]),
                ("TEXTCOLOR", (4, i), (4, i), colors.white),
            ]))

    story.append(mod_table)
    story.append(Spacer(1, 0.3 * inch))

    # ── Evidence Details ─────────────────────────────────────────────────────
    story.append(Paragraph("Evidence Details", h2))
    story.append(Spacer(1, 0.1 * inch))

    small = ParagraphStyle("Small", parent=styles["Normal"], fontSize=8,
                           textColor=colors.HexColor("#475569"), leading=12)
    label = ParagraphStyle("Label", parent=styles["Normal"], fontSize=9,
                           fontName="Helvetica-Bold",
                           textColor=colors.HexColor("#1e293b"))

    for mod_id, data in modules.items():
        evidence = data.get("evidence", {})
        mod_name = MODULE_NAMES.get(mod_id, mod_id)
        story.append(Paragraph(mod_name, label))

        if mod_id == "ai_detection":
            chunk_scores = evidence.get("chunk_scores", [])
            if chunk_scores:
                story.append(Paragraph(
                    f"Chunk scores: {', '.join(f'{s:.2f}' for s in chunk_scores)}",
                    small
                ))
            flagged = evidence.get("flagged_segments", [])
            if flagged:
                for flag in flagged[:3]:
                    story.append(Paragraph(
                        f"  • Segment {flag.get('index','')} "
                        f"(score {flag.get('score',''):.2f}): "
                        f"{flag.get('snippet','')}",
                        small
                    ))

        elif mod_id == "plagiarism":
            matches = evidence.get("matches", [])
            if matches:
                for m in matches[:5]:
                    story.append(Paragraph(
                        f"  • Doc {m.get('doc_id','')} — "
                        f"similarity {m.get('similarity',0):.1%}",
                        small
                    ))
            else:
                story.append(Paragraph("  No external matches found.", small))

        elif mod_id == "writing_profile":
            flagged_feats = evidence.get("flagged_features", [])
            if flagged_feats:
                story.append(Paragraph(
                    f"  Anomalous features: {', '.join(flagged_feats)}",
                    small
                ))
            else:
                story.append(Paragraph("  Style consistent with baseline.", small))

        story.append(Spacer(1, 0.08 * inch))

    # ── Footer ───────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e2e8f0")))
    footer_style = ParagraphStyle(
        "Footer",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#94a3b8"),
        alignment=TA_CENTER,
    )
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(
        "This report is generated automatically and should be reviewed by a qualified "
        "educator before any academic integrity action is taken. Scores are probabilistic "
        "indicators, not definitive proof.",
        footer_style,
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
