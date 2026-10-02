"""Tests for datascope.models — the core data structures."""

import pandas as pd

from datascope.models import (
    Finding,
    FindingType,
    LoaderResult,
    Severity,
)

# ---------------------------------------------------------------------------
# Severity enum
# ---------------------------------------------------------------------------

class TestSeverity:

    def test_ordering_critical_gt_warning(self):
        assert Severity.CRITICAL > Severity.WARNING

    def test_ordering_warning_gt_info(self):
        assert Severity.WARNING > Severity.INFO

    def test_ordering_critical_gt_info(self):
        assert Severity.CRITICAL > Severity.INFO

    def test_sort_produces_critical_first(self):
        severities = [Severity.INFO, Severity.CRITICAL, Severity.WARNING]
        assert sorted(severities, reverse=True) == [
            Severity.CRITICAL,
            Severity.WARNING,
            Severity.INFO,
        ]


# ---------------------------------------------------------------------------
# FindingType enum
# ---------------------------------------------------------------------------

class TestFindingType:

    def test_contains_all_types(self):
        expected = {
            "TYPE_INCONSISTENCY",
            "SENTINEL_VALUE",
            "LEADING_ZEROS",
            "MIXED_DATES",
            "NEAR_CONSTANT",
            "DUPLICATE_IDS",
            "MISSING_VALUE_PATTERN",
            "MALFORMED_ROWS",
        }
        assert {ft.name for ft in FindingType} == expected


# ---------------------------------------------------------------------------
# Finding dataclass
# ---------------------------------------------------------------------------

class TestFinding:

    def test_happy_path_all_fields(self):
        f = Finding(
            field_name="age",
            finding_type=FindingType.TYPE_INCONSISTENCY,
            evidence={"string_count": 5, "numeric_count": 95},
            severity=Severity.WARNING,
            assumption="age is always numeric",
            reality="5% of values are strings like 'N/A'",
            impact="numeric aggregations silently drop 5% of rows",
            fix_recommendation="replace sentinel strings with NaN",
            prevention_rule="validate age is numeric at ingestion",
        )
        assert f.field_name == "age"
        assert f.finding_type is FindingType.TYPE_INCONSISTENCY
        assert f.severity is Severity.WARNING
        assert f.assumption == "age is always numeric"
        assert f.reality == "5% of values are strings like 'N/A'"
        assert f.impact == "numeric aggregations silently drop 5% of rows"
        assert f.fix_recommendation == "replace sentinel strings with NaN"
        assert f.prevention_rule == "validate age is numeric at ingestion"
        assert f.evidence["string_count"] == 5

    def test_pre_composition_state_has_none_text_fields(self):
        """Before NL composer runs, text fields are None — that is valid."""
        f = Finding(
            field_name="status",
            finding_type=FindingType.SENTINEL_VALUE,
            evidence={"sentinel": "N/A", "count": 12},
        )
        assert f.severity is None
        assert f.assumption is None
        assert f.reality is None
        assert f.impact is None
        assert f.fix_recommendation is None
        assert f.prevention_rule is None

    def test_evidence_defaults_to_empty_dict(self):
        f = Finding(field_name="x", finding_type=FindingType.NEAR_CONSTANT)
        assert f.evidence == {}

    def test_sort_findings_by_severity(self):
        """R12: findings must be sortable by severity, critical first."""
        findings = [
            Finding(
                field_name="a",
                finding_type=FindingType.TYPE_INCONSISTENCY,
                severity=Severity.INFO,
            ),
            Finding(
                field_name="b",
                finding_type=FindingType.SENTINEL_VALUE,
                severity=Severity.CRITICAL,
            ),
            Finding(
                field_name="c",
                finding_type=FindingType.LEADING_ZEROS,
                severity=Severity.WARNING,
            ),
        ]
        by_sev = sorted(findings, key=lambda f: f.severity, reverse=True)
        assert [f.field_name for f in by_sev] == ["b", "c", "a"]


# ---------------------------------------------------------------------------
# LoaderResult dataclass
# ---------------------------------------------------------------------------

class TestLoaderResult:

    def test_happy_path(self):
        df = pd.DataFrame({"col": [1, 2, 3]})
        lr = LoaderResult(
            dataframe=df,
            cell_types={"col": [int, int, int]},
            source_metadata={"filename": "test.xlsx", "row_count": 3},
        )
        assert len(lr.dataframe) == 3
        assert lr.cell_types["col"] == [int, int, int]
        assert lr.source_metadata["filename"] == "test.xlsx"

    def test_empty_dataframe_is_valid(self):
        lr = LoaderResult(dataframe=pd.DataFrame())
        assert len(lr.dataframe) == 0
        assert lr.cell_types == {}
        assert lr.source_metadata == {}

    def test_cell_types_separate_from_dataframe(self):
        """cell_types is independent storage, not derived from the DataFrame."""
        df = pd.DataFrame({"mixed": [1, "two", 3.0]})
        lr = LoaderResult(
            dataframe=df,
            cell_types={"mixed": [int, str, float]},
        )
        assert lr.cell_types["mixed"] == [int, str, float]
