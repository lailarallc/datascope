"""Template engine that populates the narrative text fields on a Finding.

Chooses the correct template function for each finding type and writes the
five text fields onto the Finding in place.
"""

from __future__ import annotations

from datascope.findings import templates
from datascope.models import Finding, FindingType

_TEMPLATE_MAP = {
    FindingType.TYPE_INCONSISTENCY: templates.type_inconsistency,
    FindingType.SENTINEL_VALUE: templates.sentinel_value,
    FindingType.LEADING_ZEROS: templates.leading_zeros,
    FindingType.MIXED_DATES: templates.mixed_dates,
    FindingType.NEAR_CONSTANT: templates.near_constant,
    FindingType.DUPLICATE_IDS: templates.suspected_duplicate_ids,
    FindingType.MISSING_VALUE_PATTERN: templates.missing_value_pattern,
    FindingType.MALFORMED_ROWS: templates.malformed_rows,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compose_finding(finding: Finding) -> Finding:
    """Populate the narrative text fields on *finding* and return it.

    Selects the appropriate template based on the finding's type and
    evidence, then writes the five text fields (``assumption``,
    ``reality``, ``impact``, ``fix_recommendation``,
    ``prevention_rule``) onto the finding.

    Parameters
    ----------
    finding:
        A :class:`~datascope.models.Finding` with ``field_name``,
        ``finding_type``, and ``evidence`` populated.

    Returns
    -------
    Finding
        The same finding instance, now with all five text fields set.
    """
    template_fn = _TEMPLATE_MAP.get(
        finding.finding_type, templates.type_inconsistency,
    )
    texts = template_fn(finding.field_name, finding.evidence)

    finding.assumption = texts["assumption"]
    finding.reality = texts["reality"]
    finding.impact = texts["impact"]
    finding.fix_recommendation = texts["fix_recommendation"]
    finding.prevention_rule = texts["prevention_rule"]

    return finding
