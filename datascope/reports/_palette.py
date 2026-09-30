"""Shared color tokens, severity labels, and finding-type labels.

Single source of truth for the Lailara Design System v2 palette used
across all report generators (PDF, HTML, annotated Excel).
"""

from __future__ import annotations

from collections.abc import Iterable

from datascope.models import Finding, FindingType, Severity

# ---------------------------------------------------------------------------
# Colour hex values — Lailara Design System v2 (city-named families)
# ---------------------------------------------------------------------------

CHICAGO_20_HEX = "#1f2e7a"
LONDON_95_HEX = "#f2f2f2"
LONDON_85_HEX = "#d9d9d9"
LONDON_35_HEX = "#595959"
LONDON_20_HEX = "#333333"
LONDON_5_HEX = "#0d0d0d"
HK_35_HEX = "#158f75"

# Badge fills — darker family steps; Red-42 is reserved for text/rules only.
CRITICAL_BG_HEX = "#a80d08"   # Red-30
WARNING_BG_HEX = "#a05a1a"    # Singapore-35
INFO_BG_HEX = "#3348a8"       # Chicago-40

CRITICAL_TINT_HEX = "#fce8e7"  # Red-95
WARNING_TINT_HEX = "#fdeee0"   # Singapore-95
INFO_TINT_HEX = "#e8eaf4"      # Chicago-95

CANVAS_HEX = "#f5f3ee"

# ---------------------------------------------------------------------------
# Severity / finding-type mappings
# ---------------------------------------------------------------------------

SEVERITY_ORDER = [Severity.CRITICAL, Severity.WARNING, Severity.INFO]

SEVERITY_LABELS: dict[Severity, str] = {
    Severity.CRITICAL: "Critical",
    Severity.WARNING: "Warning",
    Severity.INFO: "Info",
}

SEVERITY_COLORS: dict[Severity, tuple[str, str]] = {
    Severity.CRITICAL: (CRITICAL_BG_HEX, CRITICAL_TINT_HEX),
    Severity.WARNING: (WARNING_BG_HEX, WARNING_TINT_HEX),
    Severity.INFO: (INFO_BG_HEX, INFO_TINT_HEX),
}

FINDING_TYPE_LABELS: dict[FindingType, str] = {
    FindingType.TYPE_INCONSISTENCY: "Type Inconsistency",
    FindingType.SENTINEL_VALUE: "Sentinel Value",
    FindingType.LEADING_ZEROS: "Leading Zeros",
    FindingType.MIXED_DATES: "Mixed Date Formats",
    FindingType.NEAR_CONSTANT: "Near-Constant Column",
    FindingType.DUPLICATE_IDS: "Suspected Duplicate IDs",
    FindingType.MISSING_VALUE_PATTERN: "Missing Values",
}


# ---------------------------------------------------------------------------
# Shared severity tally
# ---------------------------------------------------------------------------


def severity_counts(findings: Iterable[Finding]) -> dict[Severity, int]:
    """Count findings per severity level.

    Every severity is present in the result (zero-filled). Findings whose
    severity has not been classified yet (``None``) are ignored. Single
    source of truth for the tally used by every report generator and the
    CLI summary.
    """
    counts: dict[Severity, int] = {s: 0 for s in Severity}
    for f in findings:
        if f.severity is not None:
            counts[f.severity] += 1
    return counts


# ---------------------------------------------------------------------------
# Shared health assessment text
# ---------------------------------------------------------------------------


def incomplete_checks_text(source_metadata: dict) -> str | None:
    """Warning for a report built with some checks missing, else None.

    The CLI records analyzers that raised in ``source_metadata["failed_checks"]``.
    Without this, zero findings from a failed check reads as a clean result.
    """
    failed = source_metadata.get("failed_checks") or []
    if not failed:
        return None
    noun = "check" if len(failed) == 1 else "checks"
    return (
        f"Incomplete report: {len(failed)} {noun} failed to run "
        f"({', '.join(failed)}). Issues those checks look for are not reported "
        f"here, so their absence does not mean the data is clean."
    )


def health_assessment_text(counts: dict[Severity, int]) -> str:
    """Return a plain-English health assessment from severity counts."""
    total = sum(counts.values())
    crit = counts.get(Severity.CRITICAL, 0)
    warn = counts.get(Severity.WARNING, 0)
    info = counts.get(Severity.INFO, 0)

    if total == 0:
        return (
            "No data quality issues were detected. The dataset appears clean "
            "and ready for analysis."
        )
    if crit == 0 and warn == 0:
        return (
            f"{info} informational observation{'s were' if info != 1 else ' was'} "
            f"found. The dataset is in good shape overall, with "
            f"{'a few' if info <= 3 else 'some'} minor items worth noting."
        )
    if crit == 0:
        return (
            f"No critical issues were found, but {warn} "
            f"warning{'s' if warn != 1 else ''} and {info} informational "
            f"observation{'s were' if info != 1 else ' was'} detected. "
            f"Warnings at this level typically skew joins and aggregations "
            f"quietly — address them before this data feeds reporting."
        )
    if crit <= 2:
        return (
            f"This dataset has {crit} critical issue{'s' if crit != 1 else ''} "
            f"that could cause silent data loss or incorrect calculations. "
            f"These should be resolved before the data is used for reporting "
            f"or analysis."
        )
    return (
        f"This dataset has {crit} critical issues that require immediate "
        f"attention. Data used in its current state is likely to produce "
        f"incorrect results. A thorough review and cleanup is recommended "
        f"before proceeding."
    )
