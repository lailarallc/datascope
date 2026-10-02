"""Severity classifier for datascope findings.

Maps each finding to a :class:`~datascope.models.Severity` level based on
the finding type.  The rules are impact-based:

* **CRITICAL** -- silent data loss or incorrect calculations downstream.
* **WARNING** -- key mismatches or misinterpretation likely.
* **INFO** -- data quality concern without direct downstream breakage.

Severity is *not* assigned by detectors; this module is the single source
of truth for severity classification (U7).
"""

from __future__ import annotations

from datascope.models import Finding, FindingType, Severity

_NUMERIC_TYPES: frozenset[str] = frozenset({"numeric", "int", "float"})


def classify_severity(finding: Finding) -> Severity:
    """Determine the severity of *finding* based on its type and evidence."""
    ft = finding.finding_type
    ev = finding.evidence

    if ft is FindingType.TYPE_INCONSISTENCY:
        majority = ev.get("majority_type", "")
        if majority.lower() in _NUMERIC_TYPES:
            return Severity.CRITICAL
        return Severity.WARNING

    if ft is FindingType.SENTINEL_VALUE:
        return Severity.CRITICAL

    if ft is FindingType.LEADING_ZEROS:
        return Severity.WARNING

    if ft is FindingType.MIXED_DATES:
        return Severity.WARNING

    if ft is FindingType.NEAR_CONSTANT:
        return Severity.INFO

    if ft is FindingType.DUPLICATE_IDS:
        return Severity.WARNING

    if ft is FindingType.MISSING_VALUE_PATTERN:
        null_pct = ev.get("null_pct", 0)
        if null_pct >= 50:
            return Severity.WARNING
        return Severity.INFO

    if ft is FindingType.MALFORMED_ROWS:
        # Extra fields are dropped and short rows shift into the wrong columns.
        return Severity.CRITICAL

    return Severity.INFO
