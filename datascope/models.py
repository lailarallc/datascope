"""Core data structures for datascope.

Every detector produces :class:`Finding` instances.  Downstream consumers
(severity classifier, NL composer, report writer) read and enrich them.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, TypedDict

import pandas as pd

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Severity(enum.IntEnum):
    """Finding severity, ordered so that ``CRITICAL > WARNING > INFO``.

    Using IntEnum gives free comparison operators and sort support (R12).
    Higher numeric value == higher severity.
    """

    INFO = 1
    WARNING = 2
    CRITICAL = 3


class FindingType(enum.Enum):
    """The category of data-quality issue a detector found."""

    TYPE_INCONSISTENCY = "type_inconsistency"
    SENTINEL_VALUE = "sentinel_value"
    LEADING_ZEROS = "leading_zeros"
    MIXED_DATES = "mixed_dates"
    NEAR_CONSTANT = "near_constant"
    DUPLICATE_IDS = "duplicate_ids"
    MISSING_VALUE_PATTERN = "missing_value_pattern"
    MALFORMED_ROWS = "malformed_rows"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    """A single data-quality finding produced by a detector.

    Detectors fill ``field_name``, ``finding_type``, and ``evidence``.
    Later pipeline stages fill the remaining fields:

    * **severity classifier** sets ``severity``.
    * **NL composer** sets ``assumption``, ``reality``, ``impact``,
      ``fix_recommendation``, and ``prevention_rule``.
    """

    field_name: str
    finding_type: FindingType
    evidence: dict[str, Any] = field(default_factory=dict)

    # Filled by severity classifier
    severity: Severity | None = None

    # Filled by NL composer
    assumption: str | None = None
    reality: str | None = None
    impact: str | None = None
    fix_recommendation: str | None = None
    prevention_rule: str | None = None


class SourceMetadata(TypedDict, total=False):
    """Typed metadata about the data source."""

    filename: str
    sheet: str | int
    row_count: int
    column_count: int


@dataclass
class LoaderResult:
    """What the loader hands to the profiler and detectors.

    ``cell_types`` carries per-cell Python types *separate* from the DataFrame
    so that detectors can reason about mixed-type columns without re-scanning.
    """

    dataframe: pd.DataFrame
    cell_types: dict[str, list[type]] = field(default_factory=dict)
    source_metadata: SourceMetadata = field(default_factory=dict)  # type: ignore[assignment]
