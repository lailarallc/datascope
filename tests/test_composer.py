"""Tests for datascope.findings.composer and the process_findings pipeline."""

from __future__ import annotations

import pytest

from datascope.findings.composer import compose_finding
from datascope.findings.pipeline import process_findings
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


_TEXT_FIELDS = ("assumption", "reality", "impact", "fix_recommendation", "prevention_rule")


def _assert_all_text_fields_populated(finding: Finding) -> None:
    """Assert that all five text fields are non-None, non-empty strings."""
    for attr in _TEXT_FIELDS:
        value = getattr(finding, attr)
        assert value is not None, f"{attr} should not be None"
        assert isinstance(value, str), f"{attr} should be a string"
        assert len(value) > 0, f"{attr} should not be empty"


# ---------------------------------------------------------------------------
# TYPE_INCONSISTENCY in numeric column
# ---------------------------------------------------------------------------

class TestComposeTypeInconsistencyNumeric:
    """Scenario 1: TYPE_INCONSISTENCY in numeric column -> all text fields populated."""

    @pytest.fixture()
    def finding(self) -> Finding:
        f = _make_finding(
            FindingType.TYPE_INCONSISTENCY,
            {
                "majority_type": "numeric",
                "majority_count": 485,
                "minority_types": [
                    {"type_name": "str", "count": 15, "examples": ["N/A", "pending", "TBD"]},
                ],
                "total_non_null": 500,
                "majority_pct": 97.0,
            },
            field_name="revenue",
        )
        return compose_finding(f)

    def test_all_text_fields_populated(self, finding):
        _assert_all_text_fields_populated(finding)

    def test_assumption_mentions_field(self, finding):
        assert "revenue" in finding.assumption

    def test_reality_mentions_count(self, finding):
        assert "15" in finding.reality

    def test_impact_mentions_silent(self, finding):
        assert "silent" in finding.impact.lower()

    def test_fix_mentions_field(self, finding):
        assert "revenue" in finding.fix_recommendation

    def test_prevention_mentions_type_check(self, finding):
        assert "type" in finding.prevention_rule.lower()


# ---------------------------------------------------------------------------
# Leading-zero inconsistency
# ---------------------------------------------------------------------------

class TestComposeLeadingZeros:
    """Scenario 2: Leading-zero inconsistency -> WARNING + all text fields."""

    @pytest.fixture()
    def finding(self) -> Finding:
        f = _make_finding(
            FindingType.LEADING_ZEROS,
            {
                "leading_zero_count": 10,
                "no_leading_zero_count": 40,
                "examples_with_zeros": ["00123", "00456", "00789"],
                "examples_without_zeros": ["123", "456"],
                "total_checked": 50,
            },
            field_name="zip_code",
        )
        f.severity = classify_severity(f)
        return compose_finding(f)

    def test_severity_is_warning(self, finding):
        assert finding.severity is Severity.WARNING

    def test_all_text_fields_populated(self, finding):
        _assert_all_text_fields_populated(finding)

    def test_prevention_rule_populated(self, finding):
        assert len(finding.prevention_rule) > 10

    def test_reality_mentions_leading_zeros(self, finding):
        assert "leading" in finding.reality.lower() or "zero" in finding.reality.lower()


# ---------------------------------------------------------------------------
# Sorting: CRITICAL first, then WARNING, then INFO
# ---------------------------------------------------------------------------

class TestProcessFindingsSorting:
    """Scenario 3: 3 critical + 5 warning + 2 info findings -> sorted."""

    @pytest.fixture()
    def processed(self) -> list[Finding]:
        findings = []

        # 3 CRITICAL (type inconsistency in numeric columns)
        for i in range(3):
            findings.append(_make_finding(
                FindingType.TYPE_INCONSISTENCY,
                {
                    "majority_type": "numeric",
                    "majority_count": 90,
                    "minority_types": [
                        {"type_name": "str", "count": 10, "examples": ["x"]},
                    ],
                    "total_non_null": 100,
                    "majority_pct": 90.0,
                },
                field_name=f"critical_{i:02d}",
            ))

        # 5 WARNING (leading zeros)
        for i in range(5):
            findings.append(_make_finding(
                FindingType.LEADING_ZEROS,
                {
                    "leading_zero_count": 5,
                    "no_leading_zero_count": 15,
                    "examples_with_zeros": ["001"],
                    "examples_without_zeros": ["1"],
                    "total_checked": 20,
                },
                field_name=f"warning_{i:02d}",
            ))

        # 2 INFO (near-constant)
        for i in range(2):
            findings.append(_make_finding(
                FindingType.NEAR_CONSTANT,
                {
                    "unique_count": 1,
                    "total_count": 1000,
                    "uniqueness_ratio": 0.001,
                    "top_values": [{"value": "A", "count": 1000}],
                },
                field_name=f"info_{i:02d}",
            ))

        return process_findings(findings)

    def test_total_count(self, processed):
        assert len(processed) == 10

    def test_critical_first(self, processed):
        severities = [f.severity for f in processed]
        assert severities[:3] == [Severity.CRITICAL] * 3

    def test_warning_middle(self, processed):
        severities = [f.severity for f in processed]
        assert severities[3:8] == [Severity.WARNING] * 5

    def test_info_last(self, processed):
        severities = [f.severity for f in processed]
        assert severities[8:] == [Severity.INFO] * 2

    def test_alphabetical_within_tier(self, processed):
        # Critical tier
        critical_names = [f.field_name for f in processed[:3]]
        assert critical_names == sorted(critical_names)

        # Warning tier
        warning_names = [f.field_name for f in processed[3:8]]
        assert warning_names == sorted(warning_names)

        # Info tier
        info_names = [f.field_name for f in processed[8:]]
        assert info_names == sorted(info_names)

    def test_all_findings_fully_populated(self, processed):
        for finding in processed:
            assert finding.severity is not None
            _assert_all_text_fields_populated(finding)


# ---------------------------------------------------------------------------
# Sentinel in numeric column -> CRITICAL
# ---------------------------------------------------------------------------

class TestComposeSentinelNumeric:
    """Scenario 4: Sentinel in numeric column -> CRITICAL severity."""

    def test_sentinel_critical_with_text(self):
        f = _make_finding(
            FindingType.SENTINEL_VALUE,
            {
                "sentinels_found": [
                    {"value": "N/A", "count": 5, "normalized": "n/a"},
                    {"value": "TBD", "count": 2, "normalized": "tbd"},
                ],
                "column_majority_type": "numeric",
                "total_non_null": 200,
                "sentinel_pct": 3.5,
            },
            field_name="amount",
        )
        f.severity = classify_severity(f)
        compose_finding(f)
        assert f.severity is Severity.CRITICAL
        _assert_all_text_fields_populated(f)
        assert "amount" in f.assumption


# ---------------------------------------------------------------------------
# Near-constant column -> INFO
# ---------------------------------------------------------------------------

class TestComposeNearConstant:
    """Scenario 5: Near-constant column -> INFO severity."""

    def test_near_constant_info_with_text(self):
        f = _make_finding(
            FindingType.NEAR_CONSTANT,
            {
                "unique_count": 2,
                "total_count": 5000,
                "uniqueness_ratio": 0.0004,
                "top_values": [
                    {"value": "Active", "count": 4990},
                    {"value": "Inactive", "count": 10},
                ],
            },
            field_name="status",
        )
        f.severity = classify_severity(f)
        compose_finding(f)
        assert f.severity is Severity.INFO
        _assert_all_text_fields_populated(f)
        assert "status" in f.assumption


# ---------------------------------------------------------------------------
# Suspected duplicate IDs -> WARNING
# ---------------------------------------------------------------------------

class TestComposeSuspectedDuplicates:
    """Scenario 6: Suspected duplicate IDs -> WARNING severity."""

    def test_duplicates_warning_with_text(self):
        f = _make_finding(
            FindingType.DUPLICATE_IDS,
            {
                "unique_count": 980,
                "total_count": 1000,
                "uniqueness_ratio": 0.98,
                "duplicate_values": ["ID-001", "ID-002", "ID-003"],
            },
            field_name="order_id",
        )
        f.severity = classify_severity(f)
        compose_finding(f)
        assert f.severity is Severity.WARNING
        _assert_all_text_fields_populated(f)
        assert "order_id" in f.assumption


# ---------------------------------------------------------------------------
# Mixed dates -> WARNING
# ---------------------------------------------------------------------------

class TestComposeMixedDates:
    """Scenario 7: Mixed dates -> WARNING severity."""

    def test_mixed_dates_warning_with_text(self):
        f = _make_finding(
            FindingType.MIXED_DATES,
            {
                "formats_found": ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"],
                "examples_per_format": {
                    "%Y-%m-%d": ["2026-01-15"],
                    "%m/%d/%Y": ["01/15/2026"],
                    "%d/%m/%Y": ["15/01/2026"],
                },
                "total_date_values": 300,
            },
            field_name="invoice_date",
        )
        f.severity = classify_severity(f)
        compose_finding(f)
        assert f.severity is Severity.WARNING
        _assert_all_text_fields_populated(f)
        assert "invoice_date" in f.assumption


# ---------------------------------------------------------------------------
# TYPE_INCONSISTENCY where majority is str -> WARNING
# ---------------------------------------------------------------------------

class TestComposeTypeInconsistencyStr:
    """Scenario 8: TYPE_INCONSISTENCY where majority is str -> WARNING."""

    def test_str_majority_warning_with_text(self):
        f = _make_finding(
            FindingType.TYPE_INCONSISTENCY,
            {
                "majority_type": "str",
                "majority_count": 80,
                "minority_types": [
                    {"type_name": "numeric", "count": 20, "examples": [1, 2, 3]},
                ],
                "total_non_null": 100,
                "majority_pct": 80.0,
            },
            field_name="product_name",
        )
        f.severity = classify_severity(f)
        compose_finding(f)
        assert f.severity is Severity.WARNING
        _assert_all_text_fields_populated(f)


# ---------------------------------------------------------------------------
# Edge case: minimal / zero evidence values
# ---------------------------------------------------------------------------

class TestEdgeCaseMinimalEvidence:
    """Scenario 9: Edge case with minimal/zero evidence values."""

    def test_type_inconsistency_empty_evidence(self):
        """Template handles empty evidence without crashing."""
        f = _make_finding(FindingType.TYPE_INCONSISTENCY, {})
        compose_finding(f)
        _assert_all_text_fields_populated(f)

    def test_sentinel_empty_evidence(self):
        f = _make_finding(FindingType.SENTINEL_VALUE, {})
        compose_finding(f)
        _assert_all_text_fields_populated(f)

    def test_leading_zeros_empty_evidence(self):
        f = _make_finding(
            FindingType.LEADING_ZEROS,
            {"leading_zero_count": 0},
        )
        compose_finding(f)
        _assert_all_text_fields_populated(f)

    def test_mixed_dates_empty_evidence(self):
        f = _make_finding(
            FindingType.MIXED_DATES,
            {"formats_found": []},
        )
        compose_finding(f)
        _assert_all_text_fields_populated(f)

    def test_near_constant_empty_evidence(self):
        f = _make_finding(
            FindingType.NEAR_CONSTANT,
            {"top_values": []},
        )
        compose_finding(f)
        _assert_all_text_fields_populated(f)

    def test_duplicate_ids_empty_evidence(self):
        f = _make_finding(
            FindingType.DUPLICATE_IDS,
            {"duplicate_values": []},
        )
        compose_finding(f)
        _assert_all_text_fields_populated(f)

    def test_zero_total_non_null_no_division_error(self):
        """Zero total_non_null should not cause division by zero."""
        f = _make_finding(
            FindingType.TYPE_INCONSISTENCY,
            {
                "majority_type": "numeric",
                "majority_count": 0,
                "minority_types": [],
                "total_non_null": 0,
                "majority_pct": 0,
            },
        )
        compose_finding(f)
        _assert_all_text_fields_populated(f)


# ---------------------------------------------------------------------------
# Edge case: very long field names
# ---------------------------------------------------------------------------

class TestEdgeCaseLongFieldName:
    """Scenario 10: Very long field names produce valid strings."""

    @pytest.fixture()
    def long_name(self) -> str:
        return "x" * 500

    def test_type_inconsistency_long_name(self, long_name):
        f = _make_finding(
            FindingType.TYPE_INCONSISTENCY,
            {"majority_type": "numeric", "total_non_null": 10},
            field_name=long_name,
        )
        compose_finding(f)
        _assert_all_text_fields_populated(f)
        assert long_name in f.assumption

    def test_sentinel_long_name(self, long_name):
        f = _make_finding(
            FindingType.SENTINEL_VALUE,
            {"sentinels_found": [], "column_majority_type": "numeric"},
            field_name=long_name,
        )
        compose_finding(f)
        _assert_all_text_fields_populated(f)
        assert long_name in f.assumption

    def test_leading_zeros_long_name(self, long_name):
        f = _make_finding(
            FindingType.LEADING_ZEROS,
            {"leading_zero_count": 1, "total_checked": 10},
            field_name=long_name,
        )
        compose_finding(f)
        _assert_all_text_fields_populated(f)
        assert long_name in f.assumption

    def test_near_constant_long_name(self, long_name):
        f = _make_finding(
            FindingType.NEAR_CONSTANT,
            {"top_values": [{"value": "A", "count": 100}], "total_count": 100},
            field_name=long_name,
        )
        compose_finding(f)
        _assert_all_text_fields_populated(f)
        assert long_name in f.assumption


# ---------------------------------------------------------------------------
# Integration: classify + compose pipeline
# ---------------------------------------------------------------------------

class TestIntegrationPipeline:
    """Scenario 11: Full pipeline produces complete Finding objects."""

    def test_process_findings_all_fields_non_none(self):
        """Every finding produced by process_findings has all fields set."""
        findings = [
            _make_finding(
                FindingType.TYPE_INCONSISTENCY,
                {
                    "majority_type": "numeric",
                    "majority_count": 90,
                    "minority_types": [
                        {"type_name": "str", "count": 10, "examples": ["x"]},
                    ],
                    "total_non_null": 100,
                    "majority_pct": 90.0,
                },
                field_name="revenue",
            ),
            _make_finding(
                FindingType.SENTINEL_VALUE,
                {
                    "sentinels_found": [
                        {"value": "N/A", "count": 3, "normalized": "n/a"},
                    ],
                    "column_majority_type": "numeric",
                    "total_non_null": 100,
                    "sentinel_pct": 3.0,
                },
                field_name="cost",
            ),
            _make_finding(
                FindingType.LEADING_ZEROS,
                {
                    "leading_zero_count": 5,
                    "no_leading_zero_count": 15,
                    "examples_with_zeros": ["001"],
                    "examples_without_zeros": ["1"],
                    "total_checked": 20,
                },
                field_name="zip",
            ),
            _make_finding(
                FindingType.NEAR_CONSTANT,
                {
                    "unique_count": 1,
                    "total_count": 500,
                    "uniqueness_ratio": 0.002,
                    "top_values": [{"value": "US", "count": 500}],
                },
                field_name="country",
            ),
        ]

        result = process_findings(findings)

        assert len(result) == 4
        for f in result:
            assert f.severity is not None
            _assert_all_text_fields_populated(f)

    def test_process_findings_sort_order(self):
        """Pipeline sorts CRITICAL before WARNING before INFO."""
        findings = [
            # INFO (near-constant) -- will sort last
            _make_finding(
                FindingType.NEAR_CONSTANT,
                {
                    "unique_count": 1,
                    "total_count": 100,
                    "uniqueness_ratio": 0.01,
                    "top_values": [{"value": "X", "count": 100}],
                },
                field_name="z_info",
            ),
            # WARNING (leading zeros) -- will sort middle
            _make_finding(
                FindingType.LEADING_ZEROS,
                {
                    "leading_zero_count": 2,
                    "no_leading_zero_count": 8,
                    "examples_with_zeros": ["01"],
                    "examples_without_zeros": ["1"],
                    "total_checked": 10,
                },
                field_name="m_warning",
            ),
            # CRITICAL (type inconsistency numeric) -- will sort first
            _make_finding(
                FindingType.TYPE_INCONSISTENCY,
                {
                    "majority_type": "numeric",
                    "majority_count": 95,
                    "minority_types": [
                        {"type_name": "str", "count": 5, "examples": ["?"]},
                    ],
                    "total_non_null": 100,
                    "majority_pct": 95.0,
                },
                field_name="a_critical",
            ),
        ]

        result = process_findings(findings)

        assert result[0].severity is Severity.CRITICAL
        assert result[0].field_name == "a_critical"
        assert result[1].severity is Severity.WARNING
        assert result[1].field_name == "m_warning"
        assert result[2].severity is Severity.INFO
        assert result[2].field_name == "z_info"

    def test_empty_list_returns_empty(self):
        """process_findings on an empty list returns an empty list."""
        assert process_findings([]) == []


# ---------------------------------------------------------------------------
# MALFORMED_ROWS
# ---------------------------------------------------------------------------

class TestComposeMalformedRows:

    @pytest.fixture()
    def finding(self) -> Finding:
        f = _make_finding(
            FindingType.MALFORMED_ROWS,
            {
                "expected_fields": 3,
                "count": 2,
                "too_many": 1,
                "too_few": 1,
                "examples": [
                    {"line": 3, "field_count": 4, "dropped_values": ["EXTRA"]},
                    {"line": 4, "field_count": 2},
                ],
            },
            field_name="(all columns)",
        )
        return compose_finding(f)

    def test_all_text_fields_populated(self, finding):
        _assert_all_text_fields_populated(finding)

    def test_reality_names_lines_and_dropped_values(self, finding):
        assert "line 3 has 4 fields (dropped: 'EXTRA')" in finding.reality
        assert "line 4 has 2 fields" in finding.reality


# ---------------------------------------------------------------------------
# Package exports
# ---------------------------------------------------------------------------

class TestPackageExports:

    def test_classify_severity_importable(self):
        from datascope.findings import classify_severity as fn
        assert callable(fn)

    def test_compose_finding_importable(self):
        from datascope.findings import compose_finding as fn
        assert callable(fn)

    def test_process_findings_importable(self):
        from datascope.findings import process_findings as fn
        assert callable(fn)
