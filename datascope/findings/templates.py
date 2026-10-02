"""Natural-language templates for datascope findings.

Each finding sub-type has a template function that accepts the finding's
``field_name`` and ``evidence`` dict and returns the five narrative fields:

* ``assumption`` -- what the data appears to be
* ``reality`` -- what it actually is
* ``impact`` -- what breaks downstream
* ``fix_recommendation`` -- what to do now
* ``prevention_rule`` -- what right looks like going forward

Text is plain English, readable by non-technical people (R14).
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _quote(value: object) -> str:
    """Wrap a value in single quotes for readability."""
    return f"'{value}'"


def _join_examples(examples: list, limit: int = 3) -> str:
    """Format a list of example values as a readable comma-separated string."""
    if not examples:
        return "(no examples available)"
    shown = [str(e) for e in examples[:limit]]
    remaining = len(examples) - limit
    result = ", ".join(_quote(v) for v in shown)
    if remaining > 0:
        result += f", and {remaining} more"
    return result


def _pct(value: float | int) -> str:
    """Format a percentage value to one decimal place."""
    return f"{float(value):.1f}%"


# ---------------------------------------------------------------------------
# TYPE_INCONSISTENCY
# ---------------------------------------------------------------------------

def type_inconsistency(field_name: str, evidence: dict[str, Any]) -> dict[str, str]:
    """Template for mixed-type findings."""
    majority = evidence.get("majority_type", "unknown")
    majority_pct = evidence.get("majority_pct", 0)
    total = evidence.get("total_non_null", 0)
    minority_types = evidence.get("minority_types", [])

    # Build minority description
    minority_parts = []
    all_examples: list = []
    for mt in minority_types:
        type_name = mt.get("type_name", "unknown")
        count = mt.get("count", 0)
        examples = mt.get("examples", [])
        all_examples.extend(examples)
        minority_parts.append(
            f"{count} {type_name} value{'s' if count != 1 else ''}"
        )

    minority_desc = " and ".join(minority_parts) if minority_parts else "other types"
    example_str = _join_examples(all_examples)
    total_minority = sum(mt.get("count", 0) for mt in minority_types)
    verb = "was" if total_minority == 1 else "were"

    assumption = (
        f"Column '{field_name}' appears to be purely {majority}."
    )
    reality = (
        f"However, {minority_desc} {verb} found among {total} non-null values "
        f"(the majority type covers {_pct(majority_pct)}). "
        f"Examples of unexpected values: {example_str}."
    )

    if majority.lower() in ("numeric", "int", "float"):
        impact = (
            f"Rows with non-numeric values in '{field_name}' will be silently "
            f"dropped or converted to NaN during sums, averages, and other "
            f"calculations, producing incorrect results without any error message."
        )
    else:
        impact = (
            f"Downstream systems expecting a uniform {majority} type in "
            f"'{field_name}' may misinterpret or reject the unexpected values, "
            f"leading to key-lookup failures or broken transformations."
        )

    fix_recommendation = (
        f"Review the non-{majority} values in '{field_name}' and decide "
        f"whether they should be converted to {majority}, replaced with a "
        f"proper null, or moved to a separate column."
    )
    prevention_rule = (
        f"Every value in '{field_name}' should be the same type ({majority}). "
        f"Add a type-check validation rule at data entry or ingestion time."
    )

    return {
        "assumption": assumption,
        "reality": reality,
        "impact": impact,
        "fix_recommendation": fix_recommendation,
        "prevention_rule": prevention_rule,
    }


# ---------------------------------------------------------------------------
# SENTINEL_VALUE
# ---------------------------------------------------------------------------

def sentinel_value(field_name: str, evidence: dict[str, Any]) -> dict[str, str]:
    """Template for sentinel-value findings."""
    sentinels = evidence.get("sentinels_found", [])
    majority_type = evidence.get("column_majority_type", "unknown")
    sentinel_pct = evidence.get("sentinel_pct", 0)

    sentinel_examples = [s.get("value", "?") for s in sentinels]
    sentinel_counts = [
        f"{_quote(s.get('value', '?'))} ({s.get('count', 0)} {'time' if s.get('count', 0) == 1 else 'times'})"
        for s in sentinels
    ]
    sentinel_desc = ", ".join(sentinel_counts) if sentinel_counts else "unknown sentinel values"

    assumption = (
        f"Column '{field_name}' appears to be a clean {majority_type} column."
    )
    reality = (
        f"However, {_pct(sentinel_pct)} of values ({len(sentinels)} distinct sentinel "
        f"string{'s' if len(sentinels) != 1 else ''}) are placeholder text rather "
        f"than real data: {sentinel_desc}."
    )
    impact = (
        f"Tools like pandas and Excel silently drop sentinel strings when "
        f"computing sums or averages on '{field_name}', making totals lower "
        f"than expected. No error is raised, so the data loss goes unnoticed."
    )
    fix_recommendation = (
        f"Replace sentinel values in '{field_name}' with proper null/blank "
        f"cells so that downstream tools handle missing data correctly and "
        f"row counts reflect reality."
    )
    prevention_rule = (
        f"Never use placeholder text like {_join_examples(sentinel_examples)} "
        f"in a {majority_type} column. Use blank cells or a dedicated status "
        f"column instead."
    )

    return {
        "assumption": assumption,
        "reality": reality,
        "impact": impact,
        "fix_recommendation": fix_recommendation,
        "prevention_rule": prevention_rule,
    }


# ---------------------------------------------------------------------------
# LEADING_ZEROS
# ---------------------------------------------------------------------------

def leading_zeros(field_name: str, evidence: dict[str, Any]) -> dict[str, str]:
    """Template for leading-zero inconsistency findings."""
    lz_count = evidence.get("leading_zero_count", 0)
    no_lz_count = evidence.get("no_leading_zero_count", 0)
    total = evidence.get("total_checked", 0)
    examples_with = evidence.get("examples_with_zeros", [])
    examples_without = evidence.get("examples_without_zeros", [])

    assumption = (
        f"Column '{field_name}' appears to use a single, consistent "
        f"numeric-string format."
    )
    reality = (
        f"However, {lz_count} of {total} digit-only values have leading "
        f"zeros (e.g. {_join_examples(examples_with)}) while {no_lz_count} "
        f"do not (e.g. {_join_examples(examples_without)})."
    )
    impact = (
        f"Leading zeros in '{field_name}' will be stripped when values are "
        f"treated as numbers. This causes join or lookup failures because "
        f"'00123' no longer matches '123' as a key."
    )
    fix_recommendation = (
        f"Standardize all values in '{field_name}' to the same format. If "
        f"leading zeros are meaningful (e.g. zip codes, product codes), store "
        f"them as text with consistent padding."
    )
    prevention_rule = (
        f"Decide whether '{field_name}' is a number or a code. Numbers "
        f"should never have leading zeros; codes should always be stored "
        f"as text with a fixed width."
    )

    return {
        "assumption": assumption,
        "reality": reality,
        "impact": impact,
        "fix_recommendation": fix_recommendation,
        "prevention_rule": prevention_rule,
    }


# ---------------------------------------------------------------------------
# MIXED_DATES
# ---------------------------------------------------------------------------

def mixed_dates(field_name: str, evidence: dict[str, Any]) -> dict[str, str]:
    """Template for mixed-date-format findings."""
    formats = evidence.get("formats_found", [])
    total = evidence.get("total_date_values", 0)
    examples_per = evidence.get("examples_per_format", {})

    format_parts = []
    for fmt in formats:
        examples = examples_per.get(fmt, [])
        example_str = _join_examples(examples, limit=2)
        format_parts.append(f"{fmt} (e.g. {example_str})")
    format_desc = "; ".join(format_parts) if format_parts else "(no formats detected)"

    assumption = (
        f"Column '{field_name}' appears to use a single date format."
    )
    reality = (
        f"However, {len(formats)} different date formats were found across "
        f"{total} date values: {format_desc}."
    )
    impact = (
        f"Mixed date formats in '{field_name}' cause parsing ambiguity. "
        f"For example, '01/02/2026' could be January 2 or February 1 "
        f"depending on the format. Tools may silently parse dates "
        f"incorrectly, producing wrong results."
    )
    fix_recommendation = (
        f"Pick one date format for '{field_name}' (ISO 8601 YYYY-MM-DD is "
        f"recommended) and convert all existing values to that format."
    )
    prevention_rule = (
        f"All dates in '{field_name}' should use the same format. Add "
        f"format validation at data entry time and reject values that "
        f"do not match."
    )

    return {
        "assumption": assumption,
        "reality": reality,
        "impact": impact,
        "fix_recommendation": fix_recommendation,
        "prevention_rule": prevention_rule,
    }


# ---------------------------------------------------------------------------
# NEAR_CONSTANT
# ---------------------------------------------------------------------------

def near_constant(field_name: str, evidence: dict[str, Any]) -> dict[str, str]:
    """Template for near-constant cardinality findings."""
    unique = evidence.get("unique_count", 0)
    total = evidence.get("total_count", 0)
    ratio = evidence.get("uniqueness_ratio", 0)
    top_values = evidence.get("top_values", [])

    top_parts = [
        f"{_quote(tv.get('value', '?'))} ({tv.get('count', 0)} {'time' if tv.get('count', 0) == 1 else 'times'})"
        for tv in top_values[:3]
    ]
    top_desc = ", ".join(top_parts) if top_parts else "(no values)"

    assumption = (
        f"Column '{field_name}' is expected to carry meaningful, "
        f"varying data."
    )
    reality = (
        f"However, only {unique} distinct value{'s' if unique != 1 else ''} "
        f"{'were' if unique != 1 else 'was'} found across {total} rows "
        f"(uniqueness ratio: {_pct(ratio * 100)}). "
        f"Most common: {top_desc}."
    )
    impact = (
        f"A near-constant column like '{field_name}' adds no analytical "
        f"value. Including it in models or reports may mislead readers "
        f"into thinking the field varies when it does not."
    )
    fix_recommendation = (
        f"Verify whether '{field_name}' should actually vary. If not, "
        f"document it as a constant and consider removing it from analysis. "
        f"If it should vary, investigate why the data is uniform."
    )
    prevention_rule = (
        f"If '{field_name}' is supposed to carry diverse values, add a "
        f"data-quality check that flags columns with fewer than 1% unique "
        f"values."
    )

    return {
        "assumption": assumption,
        "reality": reality,
        "impact": impact,
        "fix_recommendation": fix_recommendation,
        "prevention_rule": prevention_rule,
    }


# ---------------------------------------------------------------------------
# DUPLICATE_IDS
# ---------------------------------------------------------------------------

def suspected_duplicate_ids(field_name: str, evidence: dict[str, Any]) -> dict[str, str]:
    """Template for suspected-duplicate-ID findings."""
    unique = evidence.get("unique_count", 0)
    total = evidence.get("total_count", 0)
    ratio = evidence.get("uniqueness_ratio", 0)
    duplicates = evidence.get("duplicate_values", [])

    dup_str = _join_examples(duplicates, limit=5)

    assumption = (
        f"Column '{field_name}' appears to be a unique identifier "
        f"(ID column)."
    )
    reality = (
        f"However, {unique} of {total} values are unique (uniqueness ratio: "
        f"{_pct(ratio * 100)}), meaning some IDs appear more than once. "
        f"Duplicate values include: {dup_str}."
    )
    impact = (
        f"Duplicate IDs in '{field_name}' cause row-level joins to fan out, "
        f"producing unexpected extra rows in merged datasets. Aggregations "
        f"that assume one row per ID will double-count affected records."
    )
    fix_recommendation = (
        f"Investigate the duplicate values in '{field_name}' to determine "
        f"whether they are true duplicates (same record entered twice) or "
        f"legitimate repeats (one-to-many relationship). De-duplicate or "
        f"re-model accordingly."
    )
    prevention_rule = (
        f"If '{field_name}' is meant to be a primary key, enforce a "
        f"uniqueness constraint at the database or validation layer."
    )

    return {
        "assumption": assumption,
        "reality": reality,
        "impact": impact,
        "fix_recommendation": fix_recommendation,
        "prevention_rule": prevention_rule,
    }


# ---------------------------------------------------------------------------
# MISSING_VALUE_PATTERN
# ---------------------------------------------------------------------------

def missing_value_pattern(field_name: str, evidence: dict[str, Any]) -> dict[str, str]:
    """Template for missing-value pattern findings."""
    null_count = evidence.get("null_count", 0)
    total_rows = evidence.get("total_rows", 0)
    null_pct = evidence.get("null_pct", 0)
    distribution = evidence.get("distribution", "scattered")

    assumption = (
        f"Column '{field_name}' is expected to be fully populated."
    )
    reality = (
        f"However, {null_count} of {total_rows} rows "
        f"({_pct(null_pct)}) are null or blank. "
        f"The missing values are {distribution} across the dataset."
    )

    if null_pct >= 50:
        impact = (
            f"With more than half its values missing, '{field_name}' is "
            f"unreliable for analysis. Aggregations will silently exclude "
            f"the missing rows, and any model trained on this column will "
            f"learn from a biased sample."
        )
    else:
        impact = (
            f"Missing values in '{field_name}' will be silently excluded "
            f"from calculations. If the missingness is not random, "
            f"aggregations and models will be biased toward the "
            f"non-missing subset."
        )

    fix_recommendation = (
        f"Investigate why '{field_name}' has missing values. If the "
        f"blanks represent a known condition, consider a default value "
        f"or a separate status column. If they are data-entry gaps, "
        f"backfill from the source system."
    )
    prevention_rule = (
        f"Add a NOT NULL or completeness check for '{field_name}' "
        f"at ingestion time. Flag any batch where null rate exceeds "
        f"the historical baseline."
    )

    return {
        "assumption": assumption,
        "reality": reality,
        "impact": impact,
        "fix_recommendation": fix_recommendation,
        "prevention_rule": prevention_rule,
    }


# ---------------------------------------------------------------------------
# MALFORMED_ROWS
# ---------------------------------------------------------------------------

def malformed_rows(field_name: str, evidence: dict[str, Any]) -> dict[str, str]:
    """Template for CSV rows whose field count differs from the header."""
    expected = evidence.get("expected_fields", 0)
    count = evidence.get("count", 0)
    too_many = evidence.get("too_many", 0)
    too_few = evidence.get("too_few", 0)
    examples = evidence.get("examples", [])

    row_word = "row has" if count == 1 else "rows have"
    parts = []
    if too_many:
        parts.append(f"{too_many} with more fields")
    if too_few:
        parts.append(f"{too_few} with fewer fields")
    example_parts = []
    for ex in examples[:3]:
        text = f"line {ex.get('line')} has {ex.get('field_count')} fields"
        dropped = ex.get("dropped_values")
        if dropped:
            text += f" (dropped: {_join_examples(dropped)})"
        example_parts.append(text)

    assumption = (
        f"Every row in the file has the same {expected} fields as the header."
    )
    reality = (
        f"However, {count} {row_word} a different number of fields "
        f"({' and '.join(parts)}). For example: {'; '.join(example_parts)}."
    )
    impact = (
        "Extra fields are dropped and missing fields are left blank, so "
        "these rows lose values without any error. An unquoted comma inside "
        "a value also shifts the rest of its row into the wrong columns, "
        "so totals and joins on those columns are wrong."
    )
    fix_recommendation = (
        "Open the listed lines in a text editor. Quote any value that "
        "contains a comma, add the missing fields, and re-export the file."
    )
    prevention_rule = (
        "Export CSVs with every text field quoted, and reject any file "
        "whose rows do not all have the header's field count."
    )

    return {
        "assumption": assumption,
        "reality": reality,
        "impact": impact,
        "fix_recommendation": fix_recommendation,
        "prevention_rule": prevention_rule,
    }
