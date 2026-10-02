"""Tests for datascope.analyzers.format_check -- leading-zero and mixed-date detectors."""

from __future__ import annotations

import pandas as pd
import pytest

from datascope.analyzers.format_check import (
    analyze_leading_zeros,
    analyze_mixed_dates,
)
from datascope.models import FindingType, LoaderResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_loader_result(
    col_name: str,
    values: list,
    cell_types: list[type],
) -> LoaderResult:
    """Build a single-column LoaderResult for testing."""
    df = pd.DataFrame({col_name: values}, dtype=object)
    return LoaderResult(
        dataframe=df,
        cell_types={col_name: cell_types},
        source_metadata={"filename": "test_synthetic.xlsx"},
    )


def _make_multi_column_result(
    columns: dict[str, tuple[list, list[type]]],
) -> LoaderResult:
    """Build a multi-column LoaderResult for testing.

    ``columns`` maps column name to (values, cell_types) tuples.
    """
    data = {name: vals for name, (vals, _) in columns.items()}
    df = pd.DataFrame(data, dtype=object)
    cell_types = {name: types for name, (_, types) in columns.items()}
    return LoaderResult(
        dataframe=df,
        cell_types=cell_types,
        source_metadata={"filename": "test_synthetic.xlsx"},
    )


# ===========================================================================
# Leading-zero detector
# ===========================================================================


# ---------------------------------------------------------------------------
# AE2 scenario: 230 leading-zero values and 270 without
# ---------------------------------------------------------------------------

class TestAE2ScenarioLeadingZeros:
    """Product code column with 230 leading-zero values and 270 without."""

    @pytest.fixture()
    def ae2_result(self) -> LoaderResult:
        # 230 values like "007", "0042", etc. (leading zero + digits)
        with_zeros = [f"0{i:03d}" for i in range(230)]
        # 270 values like "1", "42", "999" (no leading zero)
        without_zeros = [str(i + 1) for i in range(270)]
        values = with_zeros + without_zeros
        cell_types = [str] * 500
        return _make_loader_result("product_code", values, cell_types)

    def test_produces_one_finding(self, ae2_result):
        findings = analyze_leading_zeros(ae2_result)
        assert len(findings) == 1

    def test_finding_field_name(self, ae2_result):
        finding = analyze_leading_zeros(ae2_result)[0]
        assert finding.field_name == "product_code"

    def test_finding_type(self, ae2_result):
        finding = analyze_leading_zeros(ae2_result)[0]
        assert finding.finding_type is FindingType.LEADING_ZEROS

    def test_severity_is_none(self, ae2_result):
        """Severity is assigned later by the classifier, not the detector."""
        finding = analyze_leading_zeros(ae2_result)[0]
        assert finding.severity is None

    def test_evidence_leading_zero_count(self, ae2_result):
        finding = analyze_leading_zeros(ae2_result)[0]
        assert finding.evidence["leading_zero_count"] == 230

    def test_evidence_no_leading_zero_count(self, ae2_result):
        finding = analyze_leading_zeros(ae2_result)[0]
        assert finding.evidence["no_leading_zero_count"] == 270

    def test_evidence_examples_with_zeros(self, ae2_result):
        finding = analyze_leading_zeros(ae2_result)[0]
        examples = finding.evidence["examples_with_zeros"]
        assert len(examples) <= 5
        assert all(e.startswith("0") for e in examples)

    def test_evidence_examples_without_zeros(self, ae2_result):
        finding = analyze_leading_zeros(ae2_result)[0]
        examples = finding.evidence["examples_without_zeros"]
        assert len(examples) <= 5
        assert all(not e.startswith("0") for e in examples)

    def test_evidence_total_checked(self, ae2_result):
        finding = analyze_leading_zeros(ae2_result)[0]
        assert finding.evidence["total_checked"] == 500


# ---------------------------------------------------------------------------
# Edge case: all leading zeros consistently -- no finding
# ---------------------------------------------------------------------------

class TestAllLeadingZerosConsistent:
    """If every string-digit value has a leading zero, there is no inconsistency
    (and no numeric cells to contrast with)."""

    def test_no_finding(self):
        values = ["007", "042", "099", "001", "088"]
        cell_types = [str] * 5
        result = _make_loader_result("code", values, cell_types)
        findings = analyze_leading_zeros(result)
        assert len(findings) == 0


# ---------------------------------------------------------------------------
# Edge case: numeric column (no string representation) -- skipped
# ---------------------------------------------------------------------------

class TestNumericColumnSkipped:
    """When cells are all numeric types, leading-zero check has nothing to do."""

    def test_no_finding(self):
        values = [7, 42, 99, 1, 88]
        cell_types = [int] * 5
        result = _make_loader_result("quantity", values, cell_types)
        findings = analyze_leading_zeros(result)
        assert len(findings) == 0


# ---------------------------------------------------------------------------
# Cross-type: string cells with leading zeros alongside numeric cells
# ---------------------------------------------------------------------------

class TestCrossTypeLeadingZeros:
    """String cells with leading zeros alongside numeric cells is a finding."""

    def test_produces_finding(self):
        values = ["007", "042", 99, 1, 88]
        cell_types = [str, str, int, int, int]
        result = _make_loader_result("product_id", values, cell_types)
        findings = analyze_leading_zeros(result)
        assert len(findings) == 1
        assert findings[0].evidence["leading_zero_count"] == 2


# ---------------------------------------------------------------------------
# Edge case: empty / all-null column
# ---------------------------------------------------------------------------

class TestEmptyColumnsLeadingZeros:

    def test_all_none_no_finding(self):
        values = [None, None, None]
        cell_types = [type(None)] * 3
        result = _make_loader_result("empty", values, cell_types)
        assert analyze_leading_zeros(result) == []

    def test_empty_cell_types(self):
        result = LoaderResult(dataframe=pd.DataFrame(), cell_types={})
        assert analyze_leading_zeros(result) == []


# ---------------------------------------------------------------------------
# Edge case: non-digit strings are ignored
# ---------------------------------------------------------------------------

class TestNonDigitStrings:
    """Strings that aren't purely digits (like 'abc', '12.3') are ignored."""

    def test_no_finding_for_alpha_strings(self):
        values = ["hello", "world", "foo", "bar"]
        cell_types = [str] * 4
        result = _make_loader_result("name", values, cell_types)
        assert analyze_leading_zeros(result) == []


# ===========================================================================
# Mixed-date-format detector
# ===========================================================================


# ---------------------------------------------------------------------------
# Happy path: mixed date formats produce a finding
# ---------------------------------------------------------------------------

class TestMixedDateFormats:
    """Column with '01/15/2026' and '2026-01-15' should produce a finding."""

    @pytest.fixture()
    def result(self) -> LoaderResult:
        values = ["01/15/2026", "2026-01-15", "03/20/2026", "2026-04-10"]
        cell_types = [str] * 4
        return _make_loader_result("date_col", values, cell_types)

    def test_produces_one_finding(self, result):
        findings = analyze_mixed_dates(result)
        assert len(findings) == 1

    def test_finding_field_name(self, result):
        finding = analyze_mixed_dates(result)[0]
        assert finding.field_name == "date_col"

    def test_finding_type(self, result):
        finding = analyze_mixed_dates(result)[0]
        assert finding.finding_type is FindingType.MIXED_DATES

    def test_severity_is_none(self, result):
        finding = analyze_mixed_dates(result)[0]
        assert finding.severity is None

    def test_evidence_formats_found(self, result):
        finding = analyze_mixed_dates(result)[0]
        formats = finding.evidence["formats_found"]
        assert len(formats) >= 2

    def test_evidence_examples_per_format(self, result):
        finding = analyze_mixed_dates(result)[0]
        examples = finding.evidence["examples_per_format"]
        assert isinstance(examples, dict)
        # Each format key maps to a list of example strings
        for fmt, ex_list in examples.items():
            assert isinstance(ex_list, list)
            assert len(ex_list) >= 1

    def test_evidence_total_date_values(self, result):
        finding = analyze_mixed_dates(result)[0]
        assert finding.evidence["total_date_values"] == 4


# ---------------------------------------------------------------------------
# Edge case: all dates in one format -- no finding
# ---------------------------------------------------------------------------

class TestUniformDateFormat:

    def test_no_finding(self):
        values = ["2026-01-15", "2026-03-20", "2026-04-10", "2026-12-25"]
        cell_types = [str] * 4
        result = _make_loader_result("date_col", values, cell_types)
        findings = analyze_mixed_dates(result)
        assert len(findings) == 0


# ---------------------------------------------------------------------------
# Ambiguous day/month values -- judged against the column, not alone
# ---------------------------------------------------------------------------

class TestAmbiguousDayMonth:
    """A value like 05/01/2026 parses as both %m/%d/%Y and %d/%m/%Y.

    It must not be pinned to whichever pattern is tried first: a clean
    DD/MM/YYYY column was reported as having 2 date formats.
    """

    def test_clean_dd_mm_yyyy_column_no_finding(self):
        values = ["15/01/2026", "05/01/2026", "28/02/2026", "03/04/2026"]
        result = _make_loader_result("order_date", values, [str] * 4)
        assert analyze_mixed_dates(result) == []

    def test_clean_dd_mm_yy_column_no_finding(self):
        values = ["15/01/26", "05/01/26", "28/02/26"]
        result = _make_loader_result("order_date", values, [str] * 3)
        assert analyze_mixed_dates(result) == []

    def test_all_ambiguous_column_no_finding(self):
        values = ["01/02/2026", "03/04/2026", "05/06/2026"]
        result = _make_loader_result("order_date", values, [str] * 3)
        assert analyze_mixed_dates(result) == []

    def test_real_mm_dd_vs_dd_mm_mix_still_found(self):
        values = ["01/15/2026", "15/01/2026", "05/01/2026"]
        result = _make_loader_result("order_date", values, [str] * 3)
        findings = analyze_mixed_dates(result)
        assert len(findings) == 1
        assert set(findings[0].evidence["formats_found"]) == {"%m/%d/%Y", "%d/%m/%Y"}
        assert findings[0].evidence["total_date_values"] == 3


# ---------------------------------------------------------------------------
# Edge case: unparseable date-like strings -- gracefully skip
# ---------------------------------------------------------------------------

class TestUnparseableDates:

    def test_no_finding_for_garbage(self):
        """Strings that look date-ish but don't parse should be silently skipped."""
        values = ["99/99/9999", "00/00/0000", "13/32/2026"]
        cell_types = [str] * 3
        result = _make_loader_result("bad_dates", values, cell_types)
        findings = analyze_mixed_dates(result)
        assert len(findings) == 0


# ---------------------------------------------------------------------------
# Edge case: no date-like strings at all
# ---------------------------------------------------------------------------

class TestNoDateStrings:

    def test_no_finding_for_non_dates(self):
        values = ["hello", "world", "foo", "bar"]
        cell_types = [str] * 4
        result = _make_loader_result("name", values, cell_types)
        assert analyze_mixed_dates(result) == []

    def test_no_finding_for_numeric_column(self):
        values = [1, 2, 3, 4]
        cell_types = [int] * 4
        result = _make_loader_result("qty", values, cell_types)
        assert analyze_mixed_dates(result) == []


# ---------------------------------------------------------------------------
# Edge case: empty column / empty input
# ---------------------------------------------------------------------------

class TestEmptyColumnsMixedDates:

    def test_all_none_no_finding(self):
        values = [None, None, None]
        cell_types = [type(None)] * 3
        result = _make_loader_result("empty", values, cell_types)
        assert analyze_mixed_dates(result) == []

    def test_empty_cell_types(self):
        result = LoaderResult(dataframe=pd.DataFrame(), cell_types={})
        assert analyze_mixed_dates(result) == []


# ---------------------------------------------------------------------------
# Package exports
# ---------------------------------------------------------------------------

class TestPackageExports:

    def test_analyze_leading_zeros_importable(self):
        from datascope.analyzers import analyze_leading_zeros as fn
        assert callable(fn)

    def test_analyze_mixed_dates_importable(self):
        from datascope.analyzers import analyze_mixed_dates as fn
        assert callable(fn)
