"""Tests for datascope.loaders -- Excel, CSV, and dispatch."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from datascope.loaders import load, load_csv, load_excel
from datascope.models import LoaderResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples" / "input"
SAMPLE_XLSX = SAMPLES_DIR / "sample_mixed_types.xlsx"


def _write_csv(tmp_path: Path, text: str, name: str = "test.csv") -> Path:
    """Write a CSV string to a temp file and return the path."""
    p = tmp_path / name
    p.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")
    return p


def _write_csv_bytes(tmp_path: Path, data: bytes, name: str = "test.csv") -> Path:
    """Write raw bytes (e.g. BOM-prefixed) to a temp file."""
    p = tmp_path / name
    p.write_bytes(data)
    return p


# ===================================================================
# Excel loader
# ===================================================================

class TestLoadExcel:

    def test_happy_path_returns_loader_result(self):
        result = load_excel(SAMPLE_XLSX)
        assert isinstance(result, LoaderResult)

    def test_dataframe_is_dtype_object(self):
        result = load_excel(SAMPLE_XLSX)
        for col in result.dataframe.columns:
            assert result.dataframe[col].dtype == object, (
                f"Column '{col}' should be dtype=object"
            )

    def test_cell_types_match_openpyxl_native_detection(self):
        """cell_types for 'revenue' should be all float (openpyxl native)."""
        result = load_excel(SAMPLE_XLSX)
        revenue_types = result.cell_types["revenue"]
        assert all(t is float for t in revenue_types)

    def test_mixed_column_detects_both_types(self):
        """AE1: revenue_mixed has float cells and str cells ('N/A')."""
        result = load_excel(SAMPLE_XLSX)
        types_set = set(result.cell_types["revenue_mixed"])
        assert float in types_set
        assert str in types_set

    def test_source_metadata_populated(self):
        result = load_excel(SAMPLE_XLSX)
        meta = result.source_metadata
        assert meta["filename"] == "sample_mixed_types.xlsx"
        assert meta["sheet"] == "Sales"
        assert meta["row_count"] == 200
        assert meta["column_count"] == 4

    def test_cell_types_length_matches_dataframe_rows(self):
        result = load_excel(SAMPLE_XLSX)
        for col in result.dataframe.columns:
            assert len(result.cell_types[col]) == len(result.dataframe)

    def test_sheet_by_name(self):
        result = load_excel(SAMPLE_XLSX, sheet="Sales")
        assert result.source_metadata["sheet"] == "Sales"
        assert len(result.dataframe) == 200

    def test_formula_cells_return_computed_values(self):
        """data_only=True means formula cells return computed values, not formulas.

        The sample file uses literal values, so we just verify no cell
        starts with '=' -- confirming data_only mode is active.
        """
        result = load_excel(SAMPLE_XLSX)
        for col in result.dataframe.columns:
            for val in result.dataframe[col]:
                if isinstance(val, str):
                    assert not val.startswith("="), (
                        f"Formula leaked through: {val}"
                    )


# ===================================================================
# CSV loader
# ===================================================================

class TestLoadCsv:

    def test_happy_path_clean_numeric(self, tmp_path):
        csv_path = _write_csv(tmp_path, """\
            id,value
            1,10.5
            2,20.0
            3,30.75
        """)
        result = load_csv(csv_path)
        assert isinstance(result, LoaderResult)
        assert list(result.dataframe.columns) == ["id", "value"]
        # 'id' cells should infer as int
        assert all(t is int for t in result.cell_types["id"])
        # 'value' cells should infer as float
        assert all(t is float for t in result.cell_types["value"])

    def test_dataframe_is_dtype_object(self, tmp_path):
        csv_path = _write_csv(tmp_path, """\
            a,b
            1,hello
        """)
        result = load_csv(csv_path)
        for col in result.dataframe.columns:
            assert result.dataframe[col].dtype == object

    def test_mixed_numeric_string_column(self, tmp_path):
        """AE1: CSV with mixed numeric/string column detects both types."""
        csv_path = _write_csv(tmp_path, """\
            name,score
            Alice,95
            Bob,N/A
            Carol,88
        """)
        result = load_csv(csv_path)
        types_set = set(result.cell_types["score"])
        assert int in types_set
        assert str in types_set

    def test_empty_cells_recorded_as_nonetype(self, tmp_path):
        csv_path = _write_csv(tmp_path, """\
            a,b,c
            1,,hello
            2,5,
        """)
        result = load_csv(csv_path)
        # b column row 0 is empty -> NoneType
        assert result.cell_types["b"][0] is type(None)
        # c column row 1 is empty -> NoneType
        assert result.cell_types["c"][1] is type(None)
        # The DataFrame should contain None for those cells
        assert result.dataframe.at[0, "b"] is None
        assert result.dataframe.at[1, "c"] is None

    def test_quoted_numbers_infer_as_numeric(self, tmp_path):
        """CSV quoting is stripped by csv.reader, so '123' -> int 123."""
        csv_path = _write_csv(tmp_path, '''\
            val
            "123"
            "45.6"
        ''')
        result = load_csv(csv_path)
        assert result.cell_types["val"][0] is int
        assert result.cell_types["val"][1] is float

    def test_boolean_inference(self, tmp_path):
        csv_path = _write_csv(tmp_path, """\
            flag
            true
            FALSE
            Yes
            no
        """)
        result = load_csv(csv_path)
        assert all(t is bool for t in result.cell_types["flag"])
        vals = list(result.dataframe["flag"])
        assert vals == [True, False, True, False]

    def test_dates_stay_strings_so_mixed_formats_can_surface(self, tmp_path):
        # P1 (RE-AUDIT): the CSV loader must NOT coerce date-like strings to
        # datetime — that erased the format evidence and hid mixed-format columns
        # (the silent coercion datascope exists to catch). Date-like CSV cells
        # stay as strings; the mixed-date analyzer then sees the raw formats.
        from datascope.analyzers.format_check import analyze_mixed_dates

        csv_path = _write_csv(tmp_path, """\
            ts
            2024-01-15
            01/15/2024
            2024/06/30
        """)
        result = load_csv(csv_path)
        assert all(t is str for t in result.cell_types["ts"])
        assert result.dataframe.at[0, "ts"] == "2024-01-15"   # not coerced
        findings = analyze_mixed_dates(result)
        assert len(findings) == 1                              # mixed formats now fire on CSV
        assert set(findings[0].evidence["formats_found"]) == {"%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"}

    def test_bom_handled_transparently(self, tmp_path):
        """UTF-8 BOM should not corrupt the first header."""
        content = "name,value\nAlice,1\n"
        bom_path = _write_csv_bytes(
            tmp_path,
            content.encode("utf-8-sig"),
            name="bom.csv",
        )
        result = load_csv(bom_path)
        assert "name" in result.dataframe.columns
        assert result.dataframe.at[0, "name"] == "Alice"

    def test_source_metadata(self, tmp_path):
        csv_path = _write_csv(tmp_path, """\
            x,y
            1,2
            3,4
            5,6
        """)
        result = load_csv(csv_path)
        assert result.source_metadata["filename"] == "test.csv"
        assert result.source_metadata["row_count"] == 3
        assert result.source_metadata["column_count"] == 2

    def test_rows_with_wrong_field_count_are_recorded(self, tmp_path):
        # An unquoted comma adds a field; a short row drops one. Both used to be
        # cut or padded to the header width with no trace.
        csv_path = _write_csv(tmp_path, """\
            sku,qty,price
            A1,5,9.99
            A2,3,4.50,EXTRA
            A3,7
            A4,1,2.00
        """)
        malformed = load_csv(csv_path).source_metadata["malformed_rows"]
        assert malformed["expected_fields"] == 3
        assert malformed["count"] == 2
        assert malformed["too_many"] == 1
        assert malformed["too_few"] == 1
        assert malformed["examples"] == [
            {"line": 3, "field_count": 4, "dropped_values": ["EXTRA"]},
            {"line": 4, "field_count": 2},
        ]

    def test_well_formed_csv_records_no_malformed_rows(self, tmp_path):
        # A blank line (e.g. a trailing newline) is not a malformed row.
        csv_path = _write_csv(tmp_path, "a,b\n1,2\n\n3,4\n")
        assert "malformed_rows" not in load_csv(csv_path).source_metadata

    def test_empty_file_returns_empty_result(self, tmp_path):
        csv_path = tmp_path / "empty.csv"
        csv_path.write_text("", encoding="utf-8")
        result = load_csv(csv_path)
        assert len(result.dataframe) == 0
        assert result.cell_types == {}
        assert result.source_metadata["row_count"] == 0

    def test_header_only_returns_empty_dataframe(self, tmp_path):
        csv_path = _write_csv(tmp_path, """\
            a,b,c
        """)
        result = load_csv(csv_path)
        assert len(result.dataframe) == 0
        assert list(result.dataframe.columns) == ["a", "b", "c"]
        assert result.cell_types == {"a": [], "b": [], "c": []}

    def test_auto_names_blank_headers(self, tmp_path):
        csv_path = _write_csv(tmp_path, """\
            name,,value
            Alice,X,1
        """)
        result = load_csv(csv_path)
        assert result.dataframe.columns[1] == "col_1"

    def test_short_rows_padded(self, tmp_path):
        """Rows shorter than the header get padded with None."""
        csv_path = _write_csv(tmp_path, """\
            a,b,c
            1
            2,3
        """)
        result = load_csv(csv_path)
        assert result.dataframe.at[0, "b"] is None
        assert result.dataframe.at[0, "c"] is None
        assert result.dataframe.at[1, "c"] is None

    def test_duplicate_headers_disambiguated(self, tmp_path):
        """Repeated headers get numeric suffixes so DataFrame columns and
        cell_types keys stay 1:1 (otherwise per-column analyzers crash)."""
        csv_path = _write_csv(tmp_path, """\
            amount,region,amount
            100,west,10
            200,east,20
        """)
        result = load_csv(csv_path)
        assert list(result.dataframe.columns) == ["amount", "region", "amount.1"]
        # The load contract: cell_types keys align 1:1 with DataFrame columns.
        assert list(result.cell_types.keys()) == list(result.dataframe.columns)


# ===================================================================
# Cell inference: reject Python-only numeric spellings
# ===================================================================

class TestNumericSpellingGuards:
    """int()/float() accept forms that aren't real data numbers. A cell
    literally spelling one of these must stay a string so the type and
    sentinel analyzers can see it."""

    def test_non_finite_floats_stay_strings(self, tmp_path):
        csv_path = _write_csv(tmp_path, """\
            label,amount
            a,inf
            b,-inf
            c,nan
            d,infinity
        """)
        result = load_csv(csv_path)
        # Every value in the amount column is text, not a float.
        assert set(result.cell_types["amount"]) == {str}
        assert result.dataframe["amount"].tolist() == ["inf", "-inf", "nan", "infinity"]

    def test_underscore_grouped_number_stays_string(self, tmp_path):
        csv_path = _write_csv(tmp_path, """\
            label,amount
            a,1_000
        """)
        result = load_csv(csv_path)
        assert result.cell_types["amount"] == [str]
        assert result.dataframe.at[0, "amount"] == "1_000"

    def test_real_numbers_still_parse(self, tmp_path):
        csv_path = _write_csv(tmp_path, """\
            label,amount
            a,42
            b,3.14
            c,-5
            d,1e3
        """)
        result = load_csv(csv_path)
        assert result.dataframe["amount"].tolist() == [42, 3.14, -5, 1000.0]


# ===================================================================
# dedupe_headers helper
# ===================================================================

class TestDedupeHeaders:

    def test_no_duplicates_unchanged(self):
        from datascope.loaders.base import dedupe_headers
        assert dedupe_headers(["a", "b", "c"]) == ["a", "b", "c"]

    def test_duplicates_suffixed(self):
        from datascope.loaders.base import dedupe_headers
        assert dedupe_headers(["a", "a", "a"]) == ["a", "a.1", "a.2"]

    def test_suffix_collision_skipped(self):
        """A generated suffix must not collide with a real existing header."""
        from datascope.loaders.base import dedupe_headers
        # "a.1" already exists, so the second "a" must skip past it.
        assert dedupe_headers(["a", "a.1", "a"]) == ["a", "a.1", "a.2"]


# ===================================================================
# Error paths
# ===================================================================

class TestErrorPaths:

    def test_file_not_found_csv(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="CSV file not found"):
            load_csv(tmp_path / "nonexistent.csv")

    def test_file_not_found_dispatch(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="File not found"):
            load(tmp_path / "nonexistent.xlsx")

    def test_unsupported_extension(self, tmp_path):
        json_file = tmp_path / "data.json"
        json_file.write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError, match="Unsupported file extension"):
            load(json_file)


# ===================================================================
# Dispatch (base.load)
# ===================================================================

class TestDispatch:

    def test_routes_xlsx(self):
        result = load(SAMPLE_XLSX)
        assert isinstance(result, LoaderResult)
        assert result.source_metadata["filename"] == "sample_mixed_types.xlsx"

    def test_routes_csv(self, tmp_path):
        csv_path = _write_csv(tmp_path, """\
            a,b
            1,2
        """)
        result = load(csv_path)
        assert isinstance(result, LoaderResult)
        assert result.source_metadata["filename"] == "test.csv"

    def test_xlsx_and_csv_produce_same_structure(self, tmp_path):
        """Both loaders fill the same LoaderResult fields."""
        xlsx_result = load(SAMPLE_XLSX)
        csv_path = _write_csv(tmp_path, """\
            x,y
            1,hello
        """)
        csv_result = load(csv_path)

        # Same fields populated
        assert set(xlsx_result.__dataclass_fields__) == set(csv_result.__dataclass_fields__)

        # Both have non-empty cell_types
        assert len(xlsx_result.cell_types) > 0
        assert len(csv_result.cell_types) > 0

        # Both have source_metadata with expected keys
        for key in ("filename", "row_count", "column_count"):
            assert key in xlsx_result.source_metadata
            assert key in csv_result.source_metadata


# ===================================================================
# Integration: cell_types populated correctly
# ===================================================================

class TestCellTypesIntegration:

    def test_excel_all_columns_have_cell_types(self):
        result = load_excel(SAMPLE_XLSX)
        for col in result.dataframe.columns:
            assert col in result.cell_types
            assert len(result.cell_types[col]) == len(result.dataframe)

    def test_csv_all_columns_have_cell_types(self, tmp_path):
        csv_path = _write_csv(tmp_path, """\
            name,age,active
            Alice,30,true
            Bob,25,false
        """)
        result = load_csv(csv_path)
        for col in result.dataframe.columns:
            assert col in result.cell_types
            assert len(result.cell_types[col]) == len(result.dataframe)

    def test_csv_inferred_values_stored_not_raw_strings(self, tmp_path):
        """The DataFrame stores inferred Python values, not raw CSV strings."""
        csv_path = _write_csv(tmp_path, """\
            num,flag
            42,true
        """)
        result = load_csv(csv_path)
        assert result.dataframe.at[0, "num"] == 42
        assert isinstance(result.dataframe.at[0, "num"], int)
        assert result.dataframe.at[0, "flag"] is True
