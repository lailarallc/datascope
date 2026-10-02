"""datascope.analyzers -- detectors that produce Finding objects."""

from __future__ import annotations

from datascope.analyzers.cardinality import analyze_cardinality
from datascope.analyzers.format_check import analyze_leading_zeros, analyze_mixed_dates
from datascope.analyzers.missing_values import analyze_missing_values
from datascope.analyzers.row_structure import analyze_malformed_rows
from datascope.analyzers.sentinel import analyze_sentinels
from datascope.analyzers.type_consistency import analyze_type_consistency

__all__ = [
    "analyze_type_consistency",
    "analyze_sentinels",
    "analyze_leading_zeros",
    "analyze_mixed_dates",
    "analyze_cardinality",
    "analyze_missing_values",
    "analyze_malformed_rows",
]
