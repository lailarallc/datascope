"""Format-inconsistency detectors: leading zeros and mixed date formats.

Produces :class:`~datascope.models.Finding` instances with
:attr:`~datascope.models.FindingType.LEADING_ZEROS` or
:attr:`~datascope.models.FindingType.MIXED_DATES`.

Severity is *not* assigned here -- that is the severity classifier's job (U7).
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime

from datascope.analyzers.type_consistency import normalize_type
from datascope.models import Finding, FindingType, LoaderResult

# ---------------------------------------------------------------------------
# Leading-zero detector
# ---------------------------------------------------------------------------

# Matches strings that are purely digits (at least two chars) and start with 0.
_LEADING_ZERO_RE = re.compile(r"^0\d+$")


def analyze_leading_zeros(result: LoaderResult) -> list[Finding]:
    """Detect leading-zero inconsistencies within string-typed cell values.

    For each column, examines cells whose Python type is ``str``.
    Among those that consist entirely of digits, checks whether some
    have leading zeros and others do not.  Also checks for the
    cross-type case: a column with mostly numeric cells but some
    string cells that carry leading zeros (e.g. ``"00123"`` alongside
    ``123``).

    Leading-zero detection is limited to string-typed cells because
    Excel returns numeric cells as Python numbers with no original
    string representation (openpyxl limitation).

    Parameters
    ----------
    result:
        A :class:`~datascope.models.LoaderResult`.

    Returns
    -------
    list[Finding]
        One finding per column that exhibits leading-zero
        inconsistency.
    """
    findings: list[Finding] = []

    for col_name, types_list in result.cell_types.items():
        col_values = list(result.dataframe[col_name])

        # Collect string-typed values that are purely digits
        with_leading_zero: list[str] = []
        without_leading_zero: list[str] = []

        for val, ct in zip(col_values, types_list):
            if ct is not str:
                continue
            if val is None:
                continue
            val_str = str(val)
            # Must be purely digits and at least one char
            if not val_str.isdigit() or len(val_str) == 0:
                continue
            if _LEADING_ZERO_RE.match(val_str):
                with_leading_zero.append(val_str)
            else:
                without_leading_zero.append(val_str)

        leading_zero_count = len(with_leading_zero)
        no_leading_zero_count = len(without_leading_zero)

        if leading_zero_count == 0:
            # No leading zeros found at all -- nothing to report
            continue

        # Case 1: mixed within string-typed cells (some have zeros, some don't)
        has_string_inconsistency = (
            leading_zero_count > 0 and no_leading_zero_count > 0
        )

        # Case 2: cross-type -- string cells with leading zeros alongside
        # numeric cells (the numeric cells implicitly lack leading zeros)
        non_null_types = [ct for ct in types_list if ct is not type(None)]
        normalized = [normalize_type(ct) for ct in non_null_types]
        numeric_count = sum(1 for n in normalized if n == "numeric")
        has_cross_type = leading_zero_count > 0 and numeric_count > 0

        if not has_string_inconsistency and not has_cross_type:
            # All string-digit values consistently have leading zeros,
            # and no numeric cells exist -- no inconsistency.
            continue

        evidence = {
            "leading_zero_count": leading_zero_count,
            "no_leading_zero_count": no_leading_zero_count,
            "examples_with_zeros": with_leading_zero[:5],
            "examples_without_zeros": without_leading_zero[:5],
            "total_checked": leading_zero_count + no_leading_zero_count,
        }

        findings.append(Finding(
            field_name=col_name,
            finding_type=FindingType.LEADING_ZEROS,
            evidence=evidence,
        ))

    return findings


# ---------------------------------------------------------------------------
# Mixed-date-format detector
# ---------------------------------------------------------------------------

# Common date format patterns to try, ordered from most specific to least.
_DATE_FORMATS: list[str] = [
    "%Y-%m-%d",      # 2026-01-15
    "%Y/%m/%d",      # 2026/01/15
    "%m/%d/%Y",      # 01/15/2026
    "%d/%m/%Y",      # 15/01/2026
    "%m-%d-%Y",      # 01-15-2026
    "%d-%m-%Y",      # 15-01-2026
    "%m/%d/%y",      # 01/15/26
    "%d/%m/%y",      # 15/01/26
    "%Y.%m.%d",      # 2026.01.15
    "%d.%m.%Y",      # 15.01.2026
    "%b %d, %Y",     # Jan 15, 2026
    "%B %d, %Y",     # January 15, 2026
    "%d %b %Y",      # 15 Jan 2026
    "%d %B %Y",      # 15 January 2026
]

# Quick pre-filter: a date-like string has at least one digit and a
# separator or is in month-name form.
DATE_LIKE_RE = re.compile(
    r"^\d{1,4}[\-/\.]\d{1,2}[\-/\.]\d{1,4}"
    r"(?:[T ]\d{1,2}:\d{2}(?::\d{2})?)?$"
    r"|^\w+ \d{1,2},? \d{2,4}$"
    r"|^\d{1,2} \w+ \d{2,4}$"
)


def _matching_date_formats(value: str) -> list[str]:
    """Return every known format that parses *value*, in ``_DATE_FORMATS`` order.

    A value such as ``05/01/2026`` fits both ``%m/%d/%Y`` and ``%d/%m/%Y``;
    an empty list means no format matched.
    """
    value = value.strip()
    matches: list[str] = []
    for fmt in _DATE_FORMATS:
        try:
            datetime.strptime(value, fmt)
        except ValueError:
            continue
        matches.append(fmt)
    return matches


def analyze_mixed_dates(result: LoaderResult) -> list[Finding]:
    """Detect columns where date-like strings use multiple date formats.

    Only inspects string-typed cell values that look date-like.
    If all parseable dates within a column match a single format,
    no finding is produced.

    Parameters
    ----------
    result:
        A :class:`~datascope.models.LoaderResult`.

    Returns
    -------
    list[Finding]
        One finding per column that contains mixed date formats.
    """
    findings: list[Finding] = []

    for col_name, types_list in result.cell_types.items():
        col_values = list(result.dataframe[col_name])

        # Every format each date-like string fits
        candidates: list[tuple[str, list[str]]] = []

        for val, ct in zip(col_values, types_list):
            if ct is not str:
                continue
            if val is None:
                continue
            val_str = str(val).strip()
            if not val_str:
                continue

            # Quick pre-filter before expensive strptime calls
            if not DATE_LIKE_RE.match(val_str):
                continue

            fmts = _matching_date_formats(val_str)
            if not fmts:
                # Unparseable -- skip gracefully
                continue
            candidates.append((val_str, fmts))

        # An ambiguous value (05/01/2026) follows the format with the most
        # support in the column, not the first pattern tried, so a clean
        # DD/MM/YYYY column reads as one format. Ties keep _DATE_FORMATS order.
        support = Counter(fmt for _, fmts in candidates for fmt in fmts)
        format_to_examples: dict[str, list[str]] = {}
        total_date_values = len(candidates)
        for val_str, fmts in candidates:
            fmt = max(fmts, key=lambda f: support[f])
            if fmt not in format_to_examples:
                format_to_examples[fmt] = []
            if len(format_to_examples[fmt]) < 5:
                format_to_examples[fmt].append(val_str)

        if len(format_to_examples) <= 1:
            # Zero or one format -- no inconsistency
            continue

        evidence = {
            "formats_found": list(format_to_examples.keys()),
            "examples_per_format": {
                fmt: examples
                for fmt, examples in format_to_examples.items()
            },
            "total_date_values": total_date_values,
        }

        findings.append(Finding(
            field_name=col_name,
            finding_type=FindingType.MIXED_DATES,
            evidence=evidence,
        ))

    return findings
