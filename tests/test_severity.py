"""Tests for datascope.findings.severity -- the severity classifier."""

from __future__ import annotations

from datascope.findings.severity import classify_severity
from datascope.models import Finding, FindingType, Severity

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_finding(
    finding_type: FindingType,
    evidence: dict,
    field_name: str = "test_col",
) -> Finding:
    """Build a Finding with the given type and evidence."""
    return Finding(
        field_name=field_name,
        finding_type=finding_type,
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# TYPE_INCONSISTENCY severity
# ---------------------------------------------------------------------------

class TestTypeInconsistency:

    def test_numeric_majority_is_critical(self):
        """Mixed types where majority is numeric -> CRITICAL."""
        finding = _make_finding(
            FindingType.TYPE_INCONSISTENCY,
            {
                "majority_type": "numeric",
                "majority_count": 485,
                "minority_types": [
                    {"type_name": "str", "count": 15, "examples": ["N/A"]},
                ],
                "total_non_null": 500,
                "majority_pct": 97.0,
            },
        )
        assert classify_severity(finding) is Severity.CRITICAL

    def test_string_majority_is_warning(self):
        """Mixed types where majority is str -> WARNING."""
        finding = _make_finding(
            FindingType.TYPE_INCONSISTENCY,
            {
                "majority_type": "str",
                "majority_count": 90,
                "minority_types": [
                    {"type_name": "numeric", "count": 10, "examples": [42]},
                ],
                "total_non_null": 100,
                "majority_pct": 90.0,
            },
        )
        assert classify_severity(finding) is Severity.WARNING

    def test_bool_majority_is_warning(self):
        """Mixed types where majority is bool -> WARNING."""
        finding = _make_finding(
            FindingType.TYPE_INCONSISTENCY,
            {
                "majority_type": "bool",
                "majority_count": 8,
                "minority_types": [
                    {"type_name": "str", "count": 2, "examples": ["yes"]},
                ],
                "total_non_null": 10,
                "majority_pct": 80.0,
            },
        )
        assert classify_severity(finding) is Severity.WARNING

    def test_int_majority_is_critical(self):
        """Majority type 'int' (if it appears literally) -> CRITICAL."""
        finding = _make_finding(
            FindingType.TYPE_INCONSISTENCY,
            {
                "majority_type": "int",
                "majority_count": 95,
                "minority_types": [],
                "total_non_null": 100,
                "majority_pct": 95.0,
            },
        )
        assert classify_severity(finding) is Severity.CRITICAL

    def test_float_majority_is_critical(self):
        """Majority type 'float' (if it appears literally) -> CRITICAL."""
        finding = _make_finding(
            FindingType.TYPE_INCONSISTENCY,
            {
                "majority_type": "float",
                "majority_count": 95,
                "minority_types": [],
                "total_non_null": 100,
                "majority_pct": 95.0,
            },
        )
        assert classify_severity(finding) is Severity.CRITICAL


# ---------------------------------------------------------------------------
# SENTINEL_VALUE severity
# ---------------------------------------------------------------------------

class TestSentinelValue:

    def test_sentinel_is_always_critical(self):
        """Sentinel values are always CRITICAL."""
        finding = _make_finding(
            FindingType.SENTINEL_VALUE,
            {
                "sentinels_found": [
                    {"value": "N/A", "count": 3, "normalized": "n/a"},
                ],
                "column_majority_type": "numeric",
                "total_non_null": 100,
                "sentinel_pct": 3.0,
            },
        )
        assert classify_severity(finding) is Severity.CRITICAL

    def test_sentinel_in_bool_column_still_critical(self):
        """Even in a non-numeric column (unlikely), sentinel is CRITICAL."""
        finding = _make_finding(
            FindingType.SENTINEL_VALUE,
            {
                "sentinels_found": [
                    {"value": "TBD", "count": 1, "normalized": "tbd"},
                ],
                "column_majority_type": "bool",
                "total_non_null": 50,
                "sentinel_pct": 2.0,
            },
        )
        assert classify_severity(finding) is Severity.CRITICAL


# ---------------------------------------------------------------------------
# LEADING_ZEROS / MIXED_DATES severity
# ---------------------------------------------------------------------------

class TestFormatInconsistency:

    def test_leading_zeros_is_warning(self):
        """Leading-zero inconsistency -> WARNING."""
        finding = _make_finding(
            FindingType.LEADING_ZEROS,
            {
                "leading_zero_count": 10,
                "no_leading_zero_count": 40,
                "examples_with_zeros": ["00123"],
                "examples_without_zeros": ["456"],
                "total_checked": 50,
            },
        )
        assert classify_severity(finding) is Severity.WARNING

    def test_mixed_dates_is_warning(self):
        """Mixed date formats -> WARNING."""
        finding = _make_finding(
            FindingType.MIXED_DATES,
            {
                "formats_found": ["%Y-%m-%d", "%m/%d/%Y"],
                "examples_per_format": {
                    "%Y-%m-%d": ["2026-01-15"],
                    "%m/%d/%Y": ["01/15/2026"],
                },
                "total_date_values": 100,
            },
        )
        assert classify_severity(finding) is Severity.WARNING


# ---------------------------------------------------------------------------
# NEAR_CONSTANT / DUPLICATE_IDS severity
# ---------------------------------------------------------------------------

class TestCardinalityAnomaly:

    def test_near_constant_is_info(self):
        """Near-constant column -> INFO."""
        finding = _make_finding(
            FindingType.NEAR_CONSTANT,
            {
                "unique_count": 1,
                "total_count": 1000,
                "uniqueness_ratio": 0.001,
                "top_values": [{"value": "USA", "count": 1000}],
            },
        )
        assert classify_severity(finding) is Severity.INFO

    def test_suspected_duplicate_ids_is_warning(self):
        """Suspected duplicate IDs -> WARNING."""
        finding = _make_finding(
            FindingType.DUPLICATE_IDS,
            {
                "unique_count": 980,
                "total_count": 1000,
                "uniqueness_ratio": 0.98,
                "duplicate_values": ["ID-001", "ID-002"],
            },
        )
        assert classify_severity(finding) is Severity.WARNING


class TestMalformedRows:

    def test_malformed_rows_is_critical(self):
        """Rows cut or padded to the header width lose data silently -> CRITICAL."""
        finding = _make_finding(
            FindingType.MALFORMED_ROWS,
            {"expected_fields": 3, "count": 1, "too_many": 1, "too_few": 0, "examples": []},
            field_name="(all columns)",
        )
        assert classify_severity(finding) is Severity.CRITICAL


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_missing_majority_type_defaults_to_warning(self):
        """TYPE_INCONSISTENCY with missing majority_type -> WARNING (not numeric)."""
        finding = _make_finding(
            FindingType.TYPE_INCONSISTENCY,
            {
                "majority_count": 0,
                "minority_types": [],
                "total_non_null": 0,
                "majority_pct": 0,
            },
        )
        # majority_type key absent -> ev.get returns "" -> not numeric -> WARNING
        assert classify_severity(finding) is Severity.WARNING

    def test_empty_evidence_type_inconsistency(self):
        """TYPE_INCONSISTENCY with empty evidence -> WARNING."""
        finding = _make_finding(FindingType.TYPE_INCONSISTENCY, {})
        assert classify_severity(finding) is Severity.WARNING

    def test_empty_evidence_sentinel(self):
        """SENTINEL_VALUE with empty evidence -> CRITICAL."""
        finding = _make_finding(FindingType.SENTINEL_VALUE, {})
        assert classify_severity(finding) is Severity.CRITICAL

    def test_empty_evidence_leading_zeros(self):
        """LEADING_ZEROS with empty evidence -> WARNING."""
        finding = _make_finding(FindingType.LEADING_ZEROS, {})
        assert classify_severity(finding) is Severity.WARNING

    def test_empty_evidence_mixed_dates(self):
        """MIXED_DATES with empty evidence -> WARNING."""
        finding = _make_finding(FindingType.MIXED_DATES, {})
        assert classify_severity(finding) is Severity.WARNING

    def test_near_constant_empty_evidence_defaults_to_info(self):
        """NEAR_CONSTANT with no distinguishing keys -> INFO."""
        finding = _make_finding(FindingType.NEAR_CONSTANT, {})
        assert classify_severity(finding) is Severity.INFO

    def test_duplicate_ids_empty_evidence_defaults_to_warning(self):
        """DUPLICATE_IDS with empty evidence -> WARNING."""
        finding = _make_finding(FindingType.DUPLICATE_IDS, {})
        assert classify_severity(finding) is Severity.WARNING

    def test_very_long_field_name(self):
        """Very long field name does not crash the classifier."""
        long_name = "a" * 1000
        finding = _make_finding(
            FindingType.TYPE_INCONSISTENCY,
            {"majority_type": "numeric"},
            field_name=long_name,
        )
        result = classify_severity(finding)
        assert result is Severity.CRITICAL
