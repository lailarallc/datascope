"""CSV loader -- cell-level type inference from raw text.

CSV has no native type metadata, so each cell is parsed through an
inference pipeline that is *functionally equivalent* to what openpyxl
provides for Excel files.  The int-vs-float distinction may differ
because CSV cannot distinguish ``1`` from ``1.0`` at the format level.

Returns a :class:`~datascope.models.LoaderResult` identical in shape to
the Excel loader.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from datascope.loaders.base import dedupe_headers
from datascope.models import LoaderResult

# Canonical boolean strings (case-insensitive).
_BOOL_TRUE = frozenset({"true", "yes"})
_BOOL_FALSE = frozenset({"false", "no"})

# Non-finite float spellings that ``float()`` accepts. A cell literally
# spelling one of these is real data (often a sentinel), not a number, so
# it must stay a string rather than becoming ``inf``/``NaN``.
_NON_FINITE_STRS = frozenset({"inf", "infinity", "nan"})


def _infer_cell(raw: str) -> object:
    """Infer a single cell's Python value from its raw CSV string.

    Inference order:
    1. Empty / whitespace -> ``None``
    2. Integer
    3. Float
    4. Boolean (true/false/yes/no, case-insensitive)
    5. String fallback

    Date-like cells are DELIBERATELY left as strings. A CSV has no type
    metadata, so a date is text; coercing it to ``datetime`` here would erase the
    very format evidence the mixed-date analyzer needs, silently hiding a
    mixed-format column ("2026-01-01" vs "01/02/2026") — exactly the silent
    coercion datascope exists to surface. (Excel dates arrive already typed from
    openpyxl, so the Excel loader keeps its datetime cells.)
    """
    stripped = raw.strip()
    if not stripped:
        return None

    # Preserve leading-zero digit strings (e.g. "00123") as strings
    # so the leading-zero analyzer can detect the inconsistency.
    if len(stripped) > 1 and stripped[0] == "0" and stripped.isdigit():
        return stripped

    # int()/float() accept Python-specific spellings that are not real data
    # numbers: underscore digit grouping ("1_000") and non-finite floats
    # ("inf", "-inf", "infinity", "nan"). Coercing those would silently turn
    # a genuine text/sentinel cell into a number -- and "nan" would even
    # vanish as a null. Skip numeric parsing for them so they stay strings.
    _numeric_candidate = (
        "_" not in stripped
        and stripped.lstrip("+-").lower() not in _NON_FINITE_STRS
    )

    if _numeric_candidate:
        # --- int ------------------------------------------------------
        try:
            return int(stripped)
        except ValueError:
            pass

        # --- float ----------------------------------------------------
        try:
            return float(stripped)
        except ValueError:
            pass

    # --- bool ---------------------------------------------------------
    lower = stripped.lower()
    if lower in _BOOL_TRUE:
        return True
    if lower in _BOOL_FALSE:
        return False

    # --- string fallback ----------------------------------------------
    # Date-like strings intentionally fall through to here (see docstring):
    # kept as text so analyze_mixed_dates can see the raw format and flag a
    # mixed-format column instead of it being silently coerced away.
    return stripped


def load_csv(path: Path) -> LoaderResult:
    """Read a CSV file with per-cell type inference.

    Parameters
    ----------
    path:
        Path to the ``.csv`` file.  UTF-8-BOM is handled transparently
        via ``encoding="utf-8-sig"``.

    Returns
    -------
    LoaderResult
        DataFrame with ``dtype=object`` (values are inferred Python types),
        per-column ``cell_types``, and source metadata.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If the file is empty (no header row) or malformed.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    try:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            reader = csv.reader(fh)
            first_row = next(reader, None)

            if first_row is None:
                return LoaderResult(
                    dataframe=pd.DataFrame(),
                    cell_types={},
                    source_metadata={
                        "filename": path.name,
                        "row_count": 0,
                        "column_count": 0,
                    },
                )

            headers = dedupe_headers([
                h.strip() if h.strip() else f"col_{i}"
                for i, h in enumerate(first_row)
            ])
            n_cols = len(headers)

            # Single-pass: infer types and build column-major type lists
            col_types: list[list[type]] = [[] for _ in range(n_cols)]
            inferred_rows: list[list[object]] = []
            # Rows wider or narrower than the header are still cut or padded
            # to fit, but recorded so the report can say so.
            too_many = too_few = 0
            malformed_examples: list[dict[str, object]] = []

            for raw_row in reader:
                if raw_row and len(raw_row) != n_cols:
                    example: dict[str, object] = {
                        "line": reader.line_num,
                        "field_count": len(raw_row),
                    }
                    if len(raw_row) > n_cols:
                        too_many += 1
                        example["dropped_values"] = raw_row[n_cols:]
                    else:
                        too_few += 1
                    if len(malformed_examples) < 5:
                        malformed_examples.append(example)
                padded = raw_row + [""] * max(0, n_cols - len(raw_row))
                row = [_infer_cell(padded[i]) for i in range(n_cols)]
                inferred_rows.append(row)
                for i in range(n_cols):
                    col_types[i].append(type(row[i]))

    except csv.Error as exc:
        raise ValueError(f"Malformed CSV: {exc}") from exc

    if not inferred_rows:
        return LoaderResult(
            dataframe=pd.DataFrame(columns=headers),
            cell_types={col: [] for col in headers},
            source_metadata={
                "filename": path.name,
                "row_count": 0,
                "column_count": n_cols,
            },
        )

    df = pd.DataFrame(inferred_rows, columns=headers, dtype=object)
    cell_types = {headers[i]: col_types[i] for i in range(n_cols)}

    source_metadata = {
        "filename": path.name,
        "row_count": len(inferred_rows),
        "column_count": n_cols,
    }
    if too_many or too_few:
        source_metadata["malformed_rows"] = {
            "expected_fields": n_cols,
            "count": too_many + too_few,
            "too_many": too_many,
            "too_few": too_few,
            "examples": malformed_examples,
        }

    return LoaderResult(
        dataframe=df,
        cell_types=cell_types,
        source_metadata=source_metadata,
    )
