"""PDF report generator for datascope findings.

Renders a list of :class:`~datascope.models.Finding` objects into a
professional, client-ready PDF using reportlab.  The report is structured
for non-technical readers: no jargon, no unexplained statistical metrics.

Sections:
1. Title page with finding count summary
2. Executive summary -- overall health assessment and critical highlights
3. Findings by severity -- grouped and color-coded cards
4. Field inventory -- summary table of all analyzed columns
"""

from __future__ import annotations

import datetime
from collections import defaultdict
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from datascope.models import Finding, Severity
from datascope.reports._palette import (
    CHICAGO_20_HEX,
    CRITICAL_BG_HEX,
    CRITICAL_TINT_HEX,
    FINDING_TYPE_LABELS,
    HK_35_HEX,
    INFO_BG_HEX,
    INFO_TINT_HEX,
    LONDON_5_HEX,
    LONDON_20_HEX,
    LONDON_35_HEX,
    LONDON_85_HEX,
    LONDON_95_HEX,
    SEVERITY_LABELS,
    WARNING_BG_HEX,
    WARNING_TINT_HEX,
    health_assessment_text,
    incomplete_checks_text,
    severity_counts,
)

from .brand_fonts import SANS, SANS_BOLD, SERIF_BOLD, register_fonts

# ---------------------------------------------------------------------------
# reportlab color objects derived from the shared palette
# ---------------------------------------------------------------------------

CHICAGO_20 = colors.HexColor(CHICAGO_20_HEX)
LONDON_95 = colors.HexColor(LONDON_95_HEX)
LONDON_85 = colors.HexColor(LONDON_85_HEX)
LONDON_35 = colors.HexColor(LONDON_35_HEX)
LONDON_20 = colors.HexColor(LONDON_20_HEX)
LONDON_5 = colors.HexColor(LONDON_5_HEX)
WHITE = colors.white

CRITICAL_BG = colors.HexColor(CRITICAL_BG_HEX)
WARNING_BG = colors.HexColor(WARNING_BG_HEX)
INFO_BG = colors.HexColor(INFO_BG_HEX)

CRITICAL_TINT = colors.HexColor(CRITICAL_TINT_HEX)
WARNING_TINT = colors.HexColor(WARNING_TINT_HEX)
INFO_TINT = colors.HexColor(INFO_TINT_HEX)

HK_35 = colors.HexColor(HK_35_HEX)
GRID_COLOR = LONDON_85

_SEVERITY_COLORS: dict[Severity, colors.HexColor] = {
    Severity.CRITICAL: CRITICAL_BG,
    Severity.WARNING: WARNING_BG,
    Severity.INFO: INFO_BG,
}

_SEVERITY_TINTS: dict[Severity, colors.HexColor] = {
    Severity.CRITICAL: CRITICAL_TINT,
    Severity.WARNING: WARNING_TINT,
    Severity.INFO: INFO_TINT,
}

# Page geometry.
PAGE_W, PAGE_H = letter
CONTENT_W = PAGE_W - 1.0 * inch  # 0.5in margin each side


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

def _build_styles() -> dict[str, ParagraphStyle]:
    """Create the paragraph styles used throughout the report."""
    base = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "ds_title", parent=base["Title"],
            fontName=SERIF_BOLD,
            fontSize=24, textColor=LONDON_5, spaceAfter=6,
            alignment=TA_CENTER,
        ),
        "subtitle": ParagraphStyle(
            "ds_subtitle", parent=base["Normal"],
            fontName=SANS,
            fontSize=12, textColor=LONDON_35, spaceAfter=4,
            alignment=TA_CENTER,
        ),
        "h1": ParagraphStyle(
            "ds_h1", parent=base["Heading1"],
            fontName=SERIF_BOLD,
            fontSize=16, textColor=LONDON_5, spaceAfter=6,
        ),
        "h2": ParagraphStyle(
            "ds_h2", parent=base["Heading2"],
            fontName=SERIF_BOLD,
            fontSize=13, textColor=LONDON_5, spaceAfter=4,
        ),
        "h3": ParagraphStyle(
            "ds_h3", parent=base["Heading3"],
            fontName=SERIF_BOLD,
            fontSize=11, textColor=LONDON_5, spaceAfter=2,
        ),
        "body": ParagraphStyle(
            "ds_body", parent=base["Normal"],
            fontName=SANS,
            fontSize=9, textColor=LONDON_20, spaceAfter=4, leading=13,
        ),
        "body_bold": ParagraphStyle(
            "ds_body_bold", parent=base["Normal"],
            fontSize=9, textColor=LONDON_20, spaceAfter=4, leading=13,
            fontName=SANS_BOLD,
        ),
        "caption": ParagraphStyle(
            "ds_caption", parent=base["Normal"],
            fontName=SANS,
            fontSize=8, textColor=LONDON_35, spaceAfter=6,
        ),
        "badge": ParagraphStyle(
            "ds_badge", parent=base["Normal"],
            fontSize=9, textColor=WHITE, alignment=TA_CENTER,
            fontName=SANS_BOLD,
        ),
        "summary_number": ParagraphStyle(
            "ds_summary_number", parent=base["Normal"],
            fontName=SERIF_BOLD,
            fontSize=28, alignment=TA_CENTER,
            leading=34, spaceAfter=0,
        ),
        "summary_label": ParagraphStyle(
            "ds_summary_label", parent=base["Normal"],
            fontSize=10, alignment=TA_CENTER,
            fontName=SANS_BOLD, spaceAfter=0,
        ),
        "card_label": ParagraphStyle(
            "ds_card_label", parent=base["Normal"],
            fontSize=8, textColor=LONDON_35, spaceAfter=1,
            fontName=SANS_BOLD,
        ),
        "card_text": ParagraphStyle(
            "ds_card_text", parent=base["Normal"],
            fontName=SANS,
            fontSize=9, textColor=LONDON_20, spaceAfter=4, leading=12,
        ),
        "no_issues": ParagraphStyle(
            "ds_no_issues", parent=base["Normal"],
            fontName=SANS,
            fontSize=12, textColor=HK_35,
            alignment=TA_CENTER, spaceAfter=10,
        ),
    }


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _build_title_page(
    story: list,
    styles: dict[str, ParagraphStyle],
    source_metadata: dict[str, Any],
    counts: dict[Severity, int],
) -> None:
    """Append the title page flowables to *story*."""
    from datascope import __version__

    story.append(Spacer(1, 1.2 * inch))

    # Product branding
    brand_style = ParagraphStyle(
        "ds_brand", parent=styles["subtitle"],
        fontSize=11, textColor=CHICAGO_20, fontName=SANS_BOLD,
        spaceAfter=2,
    )
    story.append(Paragraph("datascope", brand_style))
    story.append(Spacer(1, 0.05 * inch))

    story.append(Paragraph("Data Quality Diagnostic Report", styles["title"]))
    story.append(Spacer(1, 0.1 * inch))

    filename = _safe(source_metadata.get("filename", "Unknown source"))
    story.append(Paragraph(f"Source: {filename}", styles["subtitle"]))

    date_str = datetime.date.today().strftime("%B %d, %Y")
    story.append(Paragraph(date_str, styles["subtitle"]))
    story.append(Paragraph(f"v{__version__}", styles["caption"]))
    story.append(Spacer(1, 0.25 * inch))

    story.append(HRFlowable(width="60%", thickness=2, color=CHICAGO_20))
    story.append(Spacer(1, 0.3 * inch))

    # Summary counts as a small centered table.
    total = sum(counts.values())
    summary_data = [[
        Paragraph(str(counts[Severity.CRITICAL]), styles["summary_number"]),
        Paragraph(str(counts[Severity.WARNING]), styles["summary_number"]),
        Paragraph(str(counts[Severity.INFO]), styles["summary_number"]),
    ], [
        Paragraph("Critical", styles["summary_label"]),
        Paragraph("Warning", styles["summary_label"]),
        Paragraph("Info", styles["summary_label"]),
    ]]
    summary_tbl = Table(
        summary_data,
        colWidths=[1.8 * inch] * 3,
        rowHeights=[0.5 * inch, 0.25 * inch],
    )
    summary_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), SANS),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, 0), "BOTTOM"),
        ("VALIGN", (0, 1), (-1, 1), "TOP"),
        ("TEXTCOLOR", (0, 0), (0, 0), CRITICAL_BG),
        ("TEXTCOLOR", (1, 0), (1, 0), WARNING_BG),
        ("TEXTCOLOR", (2, 0), (2, 0), INFO_BG),
        ("TEXTCOLOR", (0, 1), (0, 1), CRITICAL_BG),
        ("TEXTCOLOR", (1, 1), (1, 1), WARNING_BG),
        ("TEXTCOLOR", (2, 1), (2, 1), INFO_BG),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
        ("TOPPADDING", (0, 1), (-1, 1), 0),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
    ]))
    story.append(summary_tbl)

    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph(
        f"{total} finding{'s' if total != 1 else ''} across "
        f"{source_metadata.get('column_count', 'N/A')} columns and "
        f"{source_metadata.get('row_count', 'N/A')} rows",
        styles["subtitle"],
    ))
    incomplete = incomplete_checks_text(source_metadata)
    if incomplete:
        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph(
            _safe(incomplete),
            ParagraphStyle("incomplete", parent=styles["subtitle"], textColor=CRITICAL_BG,
                           fontName=SANS_BOLD),
        ))
    story.append(PageBreak())


def _health_assessment(counts: dict[Severity, int]) -> str:
    """Return a plain-English health assessment based on severity counts."""
    return health_assessment_text(counts)


def _build_executive_summary(
    story: list,
    styles: dict[str, ParagraphStyle],
    findings: list[Finding],
    counts: dict[Severity, int],
) -> None:
    """Append the executive summary section to *story*."""
    story.append(Paragraph("Executive Summary", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=CHICAGO_20))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph(_health_assessment(counts), styles["body"]))
    story.append(Spacer(1, 0.15 * inch))

    # Highlight critical findings (up to 3).
    critical = [f for f in findings if f.severity is Severity.CRITICAL]
    if critical:
        story.append(Paragraph("Top Critical Findings", styles["h2"]))
        for finding in critical[:3]:
            label = FINDING_TYPE_LABELS.get(finding.finding_type, "Issue")
            text = (
                f"<b>{_safe(finding.field_name)}</b> ({label}): "
                f"{_safe(finding.reality or '')}"
            )
            story.append(Paragraph(text, styles["body"]))
        if len(critical) > 3:
            story.append(Paragraph(
                f"... and {len(critical) - 3} more critical "
                f"finding{'s' if len(critical) - 3 != 1 else ''} below.",
                styles["caption"],
            ))
        story.append(Spacer(1, 0.1 * inch))

    story.append(PageBreak())


def _safe(text: str) -> str:
    """Escape XML-sensitive characters for Paragraph markup."""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _build_finding_card(
    finding: Finding,
    styles: dict[str, ParagraphStyle],
) -> list:
    """Build a list of flowables representing one finding card."""
    sev = finding.severity or Severity.INFO
    tint = _SEVERITY_TINTS.get(sev, INFO_TINT)
    badge_color = _SEVERITY_COLORS.get(sev, INFO_BG)
    badge_label = SEVERITY_LABELS.get(sev, "Info")
    type_label = FINDING_TYPE_LABELS.get(finding.finding_type, "Issue")

    # Card header row: badge | field name | finding type
    badge_style = ParagraphStyle(
        "badge_inline", parent=styles["badge"],
        backColor=badge_color,
        borderPadding=(2, 6, 2, 6),
    )
    badge_para = Paragraph(badge_label, badge_style)

    header_data = [[
        badge_para,
        Paragraph(
            f"<b>{_safe(finding.field_name)}</b>",
            styles["body_bold"],
        ),
        Paragraph(type_label, styles["caption"]),
    ]]
    header_tbl = Table(
        header_data,
        colWidths=[0.9 * inch, CONTENT_W - 2.5 * inch, 1.6 * inch],
    )
    header_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), SANS),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, -1), tint),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))

    # Card body: five narrative fields in labeled rows.
    fields = [
        ("Assumption", finding.assumption),
        ("Reality", finding.reality),
        ("Impact", finding.impact),
        ("Recommended Fix", finding.fix_recommendation),
        ("Prevention Rule", finding.prevention_rule),
    ]
    body_rows = []
    for label, text in fields:
        body_rows.append([
            Paragraph(label, styles["card_label"]),
            Paragraph(_safe(text or "(not available)"), styles["card_text"]),
        ])

    body_tbl = Table(
        body_rows,
        colWidths=[1.3 * inch, CONTENT_W - 1.3 * inch],
    )
    body_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), SANS),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, GRID_COLOR),
    ]))

    # Wrap card in a border.
    card_data = [
        [header_tbl],
        [body_tbl],
    ]
    card_tbl = Table(card_data, colWidths=[CONTENT_W])
    card_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), SANS),
        ("BOX", (0, 0), (-1, -1), 1, GRID_COLOR),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))

    return [KeepTogether([card_tbl, Spacer(1, 0.1 * inch)])]


def _build_findings_section(
    story: list,
    styles: dict[str, ParagraphStyle],
    findings: list[Finding],
) -> None:
    """Append the findings-by-severity section to *story*."""
    story.append(Paragraph("Detailed Findings", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=CHICAGO_20))
    story.append(Spacer(1, 0.1 * inch))

    if not findings:
        story.append(Paragraph(
            "No data quality issues were found.",
            styles["no_issues"],
        ))
        return

    # Group by severity, then by field_name within each tier.
    for severity in (Severity.CRITICAL, Severity.WARNING, Severity.INFO):
        tier_findings = [f for f in findings if f.severity is severity]
        if not tier_findings:
            continue

        label = SEVERITY_LABELS[severity]
        color = _SEVERITY_COLORS[severity]
        story.append(Paragraph(
            f"{label} ({len(tier_findings)})",
            ParagraphStyle(
                f"sev_header_{severity.name}",
                parent=styles["h2"],
                textColor=color,
            ),
        ))
        story.append(Spacer(1, 0.05 * inch))

        # Sub-group by field_name so related issues appear together.
        by_field: dict[str, list[Finding]] = defaultdict(list)
        for f in tier_findings:
            by_field[f.field_name].append(f)

        for field_name in sorted(by_field):
            for finding in by_field[field_name]:
                story.extend(_build_finding_card(finding, styles))

    story.append(PageBreak())


def _build_field_inventory(
    story: list,
    styles: dict[str, ParagraphStyle],
    findings: list[Finding],
    source_metadata: dict[str, Any],
) -> None:
    """Append the field inventory table to *story*."""
    story.append(Paragraph("Field Inventory", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=CHICAGO_20))
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(
        "Summary of all fields with detected issues.",
        styles["caption"],
    ))

    if not findings:
        story.append(Paragraph(
            "No fields with issues to display.",
            styles["body"],
        ))
        return

    # Collect per-field info.
    field_data: dict[str, dict] = defaultdict(lambda: {
        "types": set(),
        "severities": set(),
        "count": 0,
    })
    for f in findings:
        entry = field_data[f.field_name]
        entry["types"].add(FINDING_TYPE_LABELS.get(f.finding_type, "Other"))
        if f.severity is not None:
            entry["severities"].add(f.severity)
        entry["count"] += 1

    # Build table rows.
    header = ["Field Name", "Issue Types", "Highest Severity", "Finding Count"]
    rows = [header]
    for field_name in sorted(field_data):
        entry = field_data[field_name]
        types_str = ", ".join(sorted(entry["types"]))
        if entry["severities"]:
            max_sev = max(entry["severities"])
            sev_str = SEVERITY_LABELS.get(max_sev, "Unknown")
        else:
            sev_str = "Unknown"
        rows.append([field_name, types_str, sev_str, str(entry["count"])])

    col_widths = [2.0 * inch, 2.5 * inch, 1.5 * inch, 1.0 * inch]
    # Scale to fit content width.
    total_w = sum(col_widths)
    if total_w > CONTENT_W:
        scale = CONTENT_W / total_w
        col_widths = [w * scale for w in col_widths]

    tbl = Table(rows, colWidths=col_widths, repeatRows=1)

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), CHICAGO_20),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), SANS_BOLD),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 1), (-1, -1), SANS),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("ALIGN", (0, 1), (0, -1), "LEFT"),
        ("ALIGN", (1, 1), (1, -1), "LEFT"),
        ("ALIGN", (2, 1), (2, -1), "CENTER"),
        ("ALIGN", (3, 1), (3, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LONDON_95]),
        ("GRID", (0, 0), (-1, -1), 0.5, GRID_COLOR),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]

    # Colour-code the severity column per row.
    for row_idx in range(1, len(rows)):
        sev_text = rows[row_idx][2]
        for sev, label in SEVERITY_LABELS.items():
            if sev_text == label:
                style_cmds.append(
                    ("TEXTCOLOR", (2, row_idx), (2, row_idx), _SEVERITY_COLORS[sev])
                )
                style_cmds.append(
                    ("FONTNAME", (2, row_idx), (2, row_idx), SANS_BOLD)
                )
                break

    tbl.setStyle(TableStyle(style_cmds))
    story.append(tbl)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def write_pdf(
    findings: list[Finding],
    source_metadata: dict[str, Any],
    output_path: str | Path,
) -> Path:
    """Render findings into a professional PDF report.

    Parameters
    ----------
    findings:
        Sorted list of complete :class:`~datascope.models.Finding` objects
        (already processed by :func:`~datascope.findings.pipeline.process_findings`).
    source_metadata:
        Dict with keys like ``"filename"``, ``"row_count"``,
        ``"column_count"``.
    output_path:
        Filesystem path for the generated PDF.  Parent directories are
        created automatically if they do not exist.

    Returns
    -------
    Path
        The resolved path to the created PDF file.
    """
    register_fonts()

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output),
        pagesize=letter,
        rightMargin=0.5 * inch,
        leftMargin=0.5 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )

    filename = source_metadata.get("filename", "Unknown source")

    from datascope import __version__

    def _on_later_pages(canvas, doc):
        canvas.saveState()
        canvas.setFont(SANS, 8)
        canvas.setFillColor(LONDON_35)
        canvas.drawString(
            0.5 * inch, letter[1] - 0.4 * inch,
            f"datascope diagnostic — {filename}",
        )
        canvas.drawString(
            0.5 * inch, 0.35 * inch,
            f"datascope v{__version__} — pip install datascope-dq",
        )
        canvas.drawRightString(
            letter[0] - 0.5 * inch, 0.35 * inch,
            f"Page {canvas.getPageNumber()}",
        )
        canvas.restoreState()

    styles = _build_styles()
    counts = severity_counts(findings)
    story: list = []

    _build_title_page(story, styles, source_metadata, counts)
    _build_executive_summary(story, styles, findings, counts)
    _build_findings_section(story, styles, findings)
    _build_field_inventory(story, styles, findings, source_metadata)

    doc.build(story, onLaterPages=_on_later_pages)
    return output
