"""
Report Generator
Produces a formatted PDF audit report from transcript, summary, and compliance flags.
Uses ReportLab for PDF generation.
"""

import logging
from pathlib import Path
from datetime import datetime

log = logging.getLogger(__name__)

CATEGORY_LABELS = {
    "regulatory": "Regulatory Reference",
    "red_flag": "Red Flag",
    "custom": "Custom Keyword",
}

CATEGORY_COLORS_HEX = {
    "regulatory": "#1D9E75",   # teal — informational
    "red_flag": "#D85A30",     # coral — warning
    "custom": "#378ADD",       # blue — custom
}


def generate_pdf_report(
    source_name: str,
    transcript: str,
    summary: str,
    flags: list[dict],
    output_path: Path,
):
    """Generate a formatted PDF audit report."""
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable, PageBreak,
        )
        from reportlab.lib.enums import TA_LEFT, TA_CENTER
    except ImportError:
        raise ImportError("reportlab not installed. Run: pip install reportlab")

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=LETTER,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=1 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "AuditTitle",
        parent=styles["Title"],
        fontSize=20,
        spaceAfter=6,
        textColor=colors.HexColor("#26215C"),
    )
    subtitle_style = ParagraphStyle(
        "AuditSubtitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#5F5E5A"),
        spaceAfter=4,
    )
    section_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#0C447C"),
        spaceBefore=18,
        spaceAfter=6,
        borderPad=4,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=10,
        leading=15,
        spaceAfter=6,
    )
    mono_style = ParagraphStyle(
        "Mono",
        parent=styles["Code"],
        fontSize=8,
        leading=12,
        leftIndent=12,
        backColor=colors.HexColor("#F1EFE8"),
        spaceAfter=4,
    )
    flag_context_style = ParagraphStyle(
        "FlagContext",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#444441"),
        leftIndent=8,
    )

    story = []
    now = datetime.now().strftime("%B %d, %Y  %I:%M %p")

    # ── Header ──────────────────────────────────────────────────────────────
    story.append(Paragraph("Education Audit Report", title_style))
    story.append(Paragraph(f"Source file: {source_name}", subtitle_style))
    story.append(Paragraph(f"Generated: {now}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CCC"), spaceAfter=12))

    # ── Executive Summary ────────────────────────────────────────────────────
    story.append(Paragraph("Executive Summary", section_style))
    if summary:
        for line in summary.split("\n"):
            line = line.strip()
            if not line:
                story.append(Spacer(1, 4))
            elif line.startswith("## "):
                story.append(Paragraph(line[3:], section_style))
            elif line.startswith("- "):
                story.append(Paragraph(f"• {line[2:]}", body_style))
            else:
                story.append(Paragraph(line, body_style))
    else:
        story.append(Paragraph("(Summary not available)", body_style))

    story.append(PageBreak())

    # ── Compliance Flags ─────────────────────────────────────────────────────
    story.append(Paragraph("Compliance Flags", section_style))
    story.append(Paragraph(f"Total flags detected: {len(flags)}", body_style))

    if flags:
        table_data = [["#", "Category", "Keyword / Phrase", "Line"]]
        for i, flag in enumerate(flags, 1):
            label = CATEGORY_LABELS.get(flag["category"], flag["category"].title())
            table_data.append([
                str(i),
                label,
                flag["keyword"],
                str(flag["line_number"]),
            ])

        col_widths = [0.4 * inch, 1.5 * inch, 3.5 * inch, 0.7 * inch]
        flag_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        flag_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#26215C")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1EFE8")]),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D3D1C7")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(flag_table)

        # Context snippets for red flags only
        red_flags = [f for f in flags if f["category"] == "red_flag"]
        if red_flags:
            story.append(Spacer(1, 12))
            story.append(Paragraph("Red Flag Context", section_style))
            for flag in red_flags:
                story.append(Paragraph(
                    f"<b>Line {flag['line_number']} — \"{flag['keyword']}\"</b>",
                    body_style,
                ))
                story.append(Paragraph(f"...{flag['context']}...", flag_context_style))
                story.append(Spacer(1, 6))
    else:
        story.append(Paragraph("No compliance flags detected.", body_style))

    story.append(PageBreak())

    # ── Full Transcript ──────────────────────────────────────────────────────
    story.append(Paragraph("Full Transcript", section_style))
    # Limit transcript in PDF to first 15,000 chars with a note
    display_transcript = transcript
    truncated = False
    if len(transcript) > 15_000:
        display_transcript = transcript[:15_000]
        truncated = True

    for line in display_transcript.split("\n"):
        if line.strip():
            story.append(Paragraph(line.strip(), mono_style))

    if truncated:
        story.append(Paragraph(
            "[Transcript continues — see the full .txt file in the transcripts/ folder]",
            body_style,
        ))

    # ── Footer note ──────────────────────────────────────────────────────────
    story.append(Spacer(1, 24))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CCC")))
    story.append(Paragraph(
        "Generated by Education Audit Transcription Tool · Confidential",
        subtitle_style,
    ))

    doc.build(story)
    log.info(f"    PDF report built: {output_path.name}")
