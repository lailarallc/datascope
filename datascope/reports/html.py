"""HTML report generator for datascope findings.

Renders findings into a self-contained HTML file with inline CSS.
Mirrors the PDF report structure: title, executive summary, findings
by severity, and field inventory.
"""

from __future__ import annotations

import base64
import datetime
import html
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from datascope.models import Finding, Severity
from datascope.reports._palette import (
    CANVAS_HEX,
    CHICAGO_20_HEX,
    FINDING_TYPE_LABELS,
    LONDON_95_HEX,
    SEVERITY_COLORS,
    SEVERITY_LABELS,
    SEVERITY_ORDER,
    health_assessment_text,
    incomplete_checks_text,
    severity_counts,
)

_FONTS_DIR = Path(__file__).parent / "fonts"


def _font_face_css() -> str:
    """Return @font-face rules with base64-embedded woff2 fonts.

    Playfair Display is a variable font, so one file covers 400-700. The Source
    Sans 3 files are static, one weight each, so each is declared at its real
    weight: a 400-700 range on the static Regular file makes 600/700 text
    render at 400 with no bolding. Requests for 700 resolve to SemiBold.
    """
    blocks: list[str] = []
    for name, css_family, weight in [
        ("playfair-display-latin.woff2", "Playfair Display", "400 700"),
        ("source-sans-3-latin.woff2", "Source Sans 3", "400"),
        ("source-sans-3-semibold-latin.woff2", "Source Sans 3", "600"),
    ]:
        path = _FONTS_DIR / name
        if not path.exists():
            continue
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        blocks.append(
            f"@font-face {{\n"
            f"  font-family: '{css_family}';\n"
            f"  font-style: normal;\n"
            f"  font-weight: {weight};\n"
            f"  font-display: swap;\n"
            f"  src: url('data:font/woff2;base64,{b64}') format('woff2');\n"
            f"}}"
        )
    return "\n".join(blocks)


def _e(text: str | None) -> str:
    """HTML-escape a string."""
    if text is None:
        return ""
    return html.escape(str(text))


def _health_assessment(findings: list[Finding]) -> str:
    return health_assessment_text(severity_counts(findings))


def _render_finding_card(finding: Finding) -> str:
    sev = finding.severity or Severity.INFO
    accent, tint = SEVERITY_COLORS[sev]
    label = SEVERITY_LABELS[sev]
    type_label = FINDING_TYPE_LABELS.get(finding.finding_type, finding.finding_type.value)

    sections = []
    if finding.assumption:
        sections.append(f'<p><strong>Assumption:</strong> {_e(finding.assumption)}</p>')
    if finding.reality:
        sections.append(f'<p><strong>Reality:</strong> {_e(finding.reality)}</p>')
    if finding.impact:
        sections.append(f'<p><strong>Impact:</strong> {_e(finding.impact)}</p>')
    if finding.fix_recommendation:
        sections.append(f'<p><strong>Recommended Fix:</strong> {_e(finding.fix_recommendation)}</p>')
    if finding.prevention_rule:
        sections.append(f'<p><strong>Prevention Rule:</strong> {_e(finding.prevention_rule)}</p>')

    body = "\n".join(sections)

    return f"""
    <div class="finding-card" style="border-left: 4px solid {accent}; background: {tint};">
      <div class="finding-header">
        <span class="badge" style="background: {accent};">{label}</span>
        <span class="field-name">{_e(finding.field_name)}</span>
        <span class="finding-type">{_e(type_label)}</span>
      </div>
      <div class="finding-body">
        {body}
      </div>
    </div>
    """


def write_html(
    findings: list[Finding],
    source_metadata: dict[str, Any],
    output_path: Path,
) -> None:
    """Write findings as a self-contained HTML report."""
    filename = source_metadata.get("filename", "unknown")
    rows = source_metadata.get("row_count", "?")
    cols = source_metadata.get("column_count", "?")
    # Honor SOURCE_DATE_EPOCH (reproducible-builds standard) so regenerated
    # sample reports are byte-identical; a bare datetime.now() here makes the
    # generator tag change every run and defeats any byte-lock on the output.
    _sde = os.environ.get("SOURCE_DATE_EPOCH")
    _dt = (
        datetime.datetime.fromtimestamp(int(_sde), tz=datetime.timezone.utc)
        if _sde
        else datetime.datetime.now()
    )
    now = _dt.strftime("%Y-%m-%d %H:%M")

    counts = severity_counts(findings)
    total = sum(counts.values())

    grouped: dict[Severity, list[Finding]] = defaultdict(list)
    for f in findings:
        grouped[f.severity or Severity.INFO].append(f)

    health = _health_assessment(findings)

    incomplete = incomplete_checks_text(source_metadata)
    crit_accent, crit_tint = SEVERITY_COLORS[Severity.CRITICAL]
    incomplete_banner = (
        f'\n\n  <div class="incomplete" role="alert" style="background: {crit_tint}; '
        f'border-left: 4px solid {crit_accent}; padding: 16px 20px; margin: 16px 0;">'
        f'<p style="font-size: 14px; color: #0d0d0d;">{_e(incomplete)}</p></div>'
        if incomplete
        else ""
    )

    summary_cards = ""
    for sev in SEVERITY_ORDER:
        accent, _ = SEVERITY_COLORS[sev]
        label = SEVERITY_LABELS[sev]
        c = counts[sev]
        summary_cards += f"""
        <div class="summary-card" style="border-top: 3px solid {accent};">
          <div class="summary-number">{c}</div>
          <div class="summary-label">{label}</div>
        </div>
        """

    finding_sections = ""
    for sev in SEVERITY_ORDER:
        if sev not in grouped:
            continue
        label = SEVERITY_LABELS[sev]
        cards = "\n".join(_render_finding_card(f) for f in grouped[sev])
        finding_sections += f"""
        <h2>{label} Findings</h2>
        {cards}
        """

    field_rows = ""
    for f in findings:
        sev = f.severity or Severity.INFO
        accent, _ = SEVERITY_COLORS[sev]
        label = SEVERITY_LABELS[sev]
        type_label = FINDING_TYPE_LABELS.get(f.finding_type, f.finding_type.value)
        field_rows += f"""
        <tr>
          <td>{_e(f.field_name)}</td>
          <td>{_e(type_label)}</td>
          <td><span class="badge-sm" style="background: {accent};">{label}</span></td>
        </tr>
        """

    from datascope import __version__

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Data quality diagnostic report for {_e(filename)} — generated by datascope v{__version__}">
<meta name="generator" content="datascope v{__version__}">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><circle cx='50' cy='50' r='40' fill='%231f2e7a'/><text x='50' y='62' font-size='40' text-anchor='middle' fill='white' font-family='sans-serif' font-weight='bold'>d</text></svg>">
<title>datascope diagnostic — {_e(filename)}</title>
<style>
  {_font_face_css()}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Source Sans 3', 'Source Sans Pro', 'Helvetica Neue', Helvetica, Arial, sans-serif;
         color: #333333; background: {CANVAS_HEX}; line-height: 1.6; }}
  .container {{ max-width: 900px; margin: 0 auto; padding: 48px 24px; }}
  .title-section {{ text-align: center; padding: 40px 0 20px; }}
  .title-section h1 {{ font-family: 'Playfair Display', Georgia, 'Times New Roman', serif;
                        color: #0d0d0d; font-size: 28px; font-weight: 700; margin-bottom: 4px; }}
  .title-section .subtitle {{ color: #595959; font-size: 14px; }}
  .summary-row {{ display: flex; gap: 16px; margin: 24px 0; justify-content: center; }}
  .summary-card {{ background: {LONDON_95_HEX}; border: 1px solid #d9d9d9; border-radius: 2px;
                   padding: 20px 32px; text-align: center; }}
  .summary-number {{ font-family: 'Playfair Display', Georgia, 'Times New Roman', serif;
                     font-size: 32px; font-weight: 700; color: #0d0d0d; }}
  .summary-label {{ font-size: 13px; color: #595959; font-weight: 600; }}
  .health {{ background: {LONDON_95_HEX}; border: 1px solid #d9d9d9; border-radius: 2px;
             padding: 16px 20px; margin: 16px 0 24px; }}
  .health p {{ font-size: 14px; color: #333333; }}
  h2 {{ font-family: 'Playfair Display', Georgia, 'Times New Roman', serif;
        color: #0d0d0d; font-size: 18px; font-weight: 700; margin: 28px 0 12px; }}
  hr {{ border: none; border-top: 1px solid #d9d9d9; margin: 0 0 12px; }}
  .finding-card {{ background: {LONDON_95_HEX}; border: 1px solid #d9d9d9; border-radius: 2px;
                   padding: 16px 20px; margin-bottom: 12px; }}
  .finding-header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }}
  .badge {{ color: white; font-size: 11px; font-weight: 600; padding: 2px 10px;
            border-radius: 2px; text-transform: uppercase; }}
  .badge-sm {{ color: white; font-size: 10px; font-weight: 600; padding: 1px 8px;
               border-radius: 2px; }}
  .field-name {{ font-weight: 600; font-size: 15px; color: #0d0d0d; }}
  .finding-type {{ font-size: 12px; color: #595959; }}
  .finding-body p {{ font-size: 13px; margin-bottom: 6px; color: #333333; }}
  .finding-body strong {{ color: #0d0d0d; }}
  /* DS interactive-table rows: canvas / London-95 alternating. The base is the
     odd row, so it takes canvas — setting it to London-95 too would flatten the
     zebra against the even-row rule below. */
  table {{ width: 100%; border-collapse: collapse; background: {CANVAS_HEX};
           border: 1px solid #d9d9d9; border-radius: 2px; overflow: hidden; }}
  th {{ background: {CHICAGO_20_HEX}; color: white; padding: 10px 14px; text-align: left;
        font-size: 13px; font-weight: 600; }}
  td {{ padding: 8px 14px; font-size: 13px; border-bottom: 1px solid #e0e0e0; color: #333333; }}
  tr:nth-child(even) {{ background: {LONDON_95_HEX}; }}
  .footer {{ text-align: center; padding: 24px 0; color: #595959; font-size: 11px;
             font-style: italic; }}
  .table-wrap {{ overflow-x: auto; }}

  /* ---- Responsive: narrow viewports ---- */
  @media (max-width: 640px) {{
    .container {{ padding: 24px 12px; }}
    .title-section h1 {{ font-size: 22px; }}
    .summary-row {{ flex-direction: column; align-items: stretch; gap: 8px; }}
    .summary-card {{ padding: 12px 16px; }}
    .summary-number {{ font-size: 24px; }}
    .finding-header {{ flex-wrap: wrap; }}
    table {{ font-size: 12px; }}
    th, td {{ padding: 6px 8px; }}
  }}

  /* ---- Print ---- */
  @media print {{
    body {{ background: white; color: #0d0d0d; font-size: 11pt; }}
    .container {{ max-width: 100%; padding: 0; }}
    .summary-card {{ border: 1px solid #d9d9d9; }}
    .finding-card {{ break-inside: avoid; }}
    .footer {{ font-size: 9pt; }}
  }}
</style>
</head>
<body>
<div class="container">
  <div class="title-section">
    <h1>Data Quality Diagnostic</h1>
    <div class="subtitle">{_e(filename)} &middot; {rows} rows &times; {cols} columns &middot; {now}</div>
  </div>{incomplete_banner}

  <div class="summary-row">
    {summary_cards}
  </div>

  <div class="health">
    <p><strong>Health Assessment:</strong> {_e(health)}</p>
  </div>

  {finding_sections}

  <h2>Field Inventory</h2>
  <div class="table-wrap">
  <table>
    <thead><tr><th>Field</th><th>Issue Type</th><th>Severity</th></tr></thead>
    <tbody>{field_rows}</tbody>
  </table>
  </div>

  <div class="footer">
    Generated by datascope v{__version__} &middot; {now} &middot; {total} finding{'s' if total != 1 else ''}
    <br>pip install datascope-dq
  </div>
</div>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(page, encoding="utf-8")
