"""Malformed-row detector.

Reports CSV rows whose field count differs from the header. The CSV loader
still cuts or pads such rows to the header width; it records them in
``source_metadata["malformed_rows"]`` and this detector turns that record
into a :class:`~datascope.models.Finding` with
:attr:`~datascope.models.FindingType.MALFORMED_ROWS`.
"""

from __future__ import annotations

from datascope.models import Finding, FindingType, LoaderResult

# The finding covers whole rows, not one column.
ROW_STRUCTURE_FIELD = "(all columns)"


def analyze_malformed_rows(result: LoaderResult) -> list[Finding]:
    """Return one finding if the loader recorded malformed rows, else none."""
    malformed = result.source_metadata.get("malformed_rows")
    if not malformed:
        return []
    return [Finding(
        field_name=ROW_STRUCTURE_FIELD,
        finding_type=FindingType.MALFORMED_ROWS,
        evidence=dict(malformed),
    )]
