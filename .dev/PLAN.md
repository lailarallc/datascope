# datascope — Improvement Plan

Derived from project audits (2026-05-15, 2026-05-16). See AUDIT.md for rationale.

Tier: Medium
Current focus: Move 1 DEMO-PROOF — fix demo-killers before sharing with prospects.

---

## Decomposition: Move 1 DEMO-PROOF

Goal: A prospect can run `datascope` on any file during a live call without encountering crashes, grammar errors, or stale documentation.

### Steps

- [x] A1: Catch invalid `--sheet` with friendly error messages
    - Depends on: none
    - Change: Wrap the sheet lookup in `loaders/excel.py` with try/except for `IndexError` (numeric) and `KeyError` (named). Raise `ValueError` with a message listing available sheets.
    - Done when: `datascope samples/input/sample_mixed_types.xlsx --sheet 99` and `--sheet NonExistent` both print "Error: Sheet not found..." to stderr and exit 1 (no traceback).

- [x] A2: Fix singular/plural grammar in narrative templates
    - Depends on: none
    - Change: In `findings/templates.py`, fix `type_inconsistency()` — "X value were" → conditional "was"/"were"; in `sentinel_value()` — "(N times)" → conditional "(1 time)"/"(N times)". Audit all 7 template functions for similar issues.
    - Done when: `datascope` on a file with exactly 1 minority-type value outputs "1 str value was found"; sentinel with count=1 outputs "(1 time)"; `python -m pytest tests/` still passes.

- [x] A3: Update argparse description to include Parquet
    - Depends on: none
    - Change: In `cli.py` line 30-33, update description from ".xlsx or .csv" to ".xlsx, .csv, or .parquet".
    - Done when: `datascope --help` output mentions all three formats.

- [x] A4: Fix numpy dependency in `generate_sample.py`
    - Depends on: none
    - Change: Add `numpy>=1.24.0` to `[project.optional-dependencies] dev` in `pyproject.toml` (it's already a dev-time tool, not needed at runtime). Update `requirements-dev.txt` if it exists.
    - Done when: `pip install -e ".[dev]" && python generate_sample.py` succeeds; numpy is NOT in `[project.dependencies]`.

- [x] A5: Warn when `--sheet` is passed for non-Excel files
    - Depends on: A1 (sheet error handling should be in place first)
    - Change: In `cli.py`, after resolving `ext`, if `ext != ".xlsx"` and `args.sheet is not None`, print a warning to stderr: "Warning: --sheet is ignored for {ext} files."
    - Done when: `datascope somefile.csv --sheet Revenue` prints the warning to stderr but still runs successfully.

- [x] A6: Integration verification
    - Depends on: A1-A5 all complete
    - Run full test suite, run all 5 output formats on both sample files, test the error paths manually.
    - Done when: `python -m pytest tests/` passes (283+ tests); all manual edge cases produce friendly output (no tracebacks).

---

## Move 1: CLEAN — Ship-ready baseline

Goal: A stranger who finds the repo can install, run, and trust what they see.

### 1A: Fix README install URL ✓
- Depends on: none
- Change `field-story-scorer.git` → `datascope.git` and `cd field-story-scorer` → `cd datascope` in README.md:27-28
- Done when: `grep -c "field-story-scorer" README.md` returns 0

### 1B: Add defusedxml, drop numpy from dependencies ✓
- Depends on: none
- Add `defusedxml>=0.7.0` to pyproject.toml `[project.dependencies]` and requirements.txt
- Remove `numpy>=1.24.0` from both files (v2 code never imports numpy)
- Done when: `pip install -e .` succeeds; `python -c "import defusedxml"` succeeds; `grep numpy pyproject.toml` returns nothing

### 1C: Delete scorer.py and update its dependents ✓
- Depends on: none
- Delete `scorer.py` from repo root
- Update `tools/render_strict_mode_comparison.py`: either delete it (if stale) or port the `from scorer import analyze, load_strict` to v2 APIs (`from datascope.loaders import load_file` + v2 analyzer pipeline)
- Done when: `grep -r "from scorer" .` returns nothing; `python -m pytest` still passes

### 1D: Update generate_sample.py for v2 ✓
- Depends on: 1C (scorer.py must be gone so old instructions don't work)
- Change print statements at lines 87-88 from `python scorer.py --input ...` to `datascope <file> --output-dir ...`
- Move to `tools/` directory for consistency (optional, confirm with user)
- Done when: `python generate_sample.py` prints v2 CLI commands; no reference to `scorer.py` in file

### 1E: Rewrite samples/README.md for v2 ✓
- Depends on: 1C, 1D (need v1 artifacts gone before rewriting the guide)
- Replace entire file: describe v2 diagnostic reports, reference `datascope` CLI, update output file names, remove scoring numbers and --strict-types references
- Done when: `grep -c "scorer\|strict-types\|field-story-scorer\|field_report" samples/README.md` returns 0; file describes v2 outputs and commands

### 1F: Integration verify ✓
- Depends on: 1A-1E all complete
- Run full test suite: `python -m pytest`
- Run tool end-to-end: `datascope samples/input/sample_mixed_types.xlsx --output-dir /tmp/test`
- Verify PDF is produced and stdout summary prints correctly
- Done when: all tests pass; PDF exists and opens; no stderr warnings about missing imports

---

## Move 2: POLISH — The report is the product

Goal: Every PDF datascope produces is genuinely professional and correct.

### 2A: Fix backtick literals in templates ✓
- Depends on: none
- In `datascope/findings/templates.py`, replace backtick-wrapped field names (e.g., `` f"Column `{field_name}`" ``) with either bare names or bold tags reportlab understands (`<b>{field_name}</b>`)
- ~30 occurrences across 6 template functions
- Done when: `grep -c '`' datascope/findings/templates.py` returns 0 (for backtick-wrapped names); generate a test PDF and visually confirm field names render without literal backtick characters

### 2B: Fix newline collapse in mixed-dates template ✓
- Depends on: none
- In `datascope/findings/templates.py:224-225`, replace `"\n".join(format_parts)` with `"<br/>".join(format_parts)` so reportlab Paragraph renders line breaks
- Verify _safe() in pdf.py doesn't escape `<br/>` tags (it escapes `<` and `>` — need to handle this)
- Done when: generate a PDF from sample_mixed_types.xlsx; the date format breakdown in the mixed-dates finding renders as a vertical list, not run-on text

### 2C: Add page numbers and running header to PDF ✓
- Depends on: none
- In `datascope/reports/pdf.py`, add an `onLaterPages` callback to `SimpleDocTemplate` that renders "datascope diagnostic — {filename}" as a header and "Page N" as a footer
- Done when: generate a multi-page PDF; every page after the title has a header and page number

### 2D: Fix health assessment total count ✓
- Depends on: none
- In `datascope/reports/pdf.py:244-278`, update health assessment text branches to include total finding count (e.g., "25 informational observations were found" instead of "Only informational observations were found")
- Done when: test with a dataset that produces only info findings; health assessment text includes the count

### 2E: Regenerate v2 sample outputs ✓
- Depends on: 2A, 2B, 2C, 2D (want polished PDF before committing samples)
- Run `datascope samples/input/sample_mixed_types.xlsx --output-dir samples/output/` and `datascope samples/input/sample_sales.xlsx --output-dir samples/output/`
- Delete old v1 output files (`*_field_report.*`, `*_field_report_strict.*`)
- Update screenshots if applicable
- Done when: `samples/output/` contains only v2 diagnostic PDFs; no v1 artifacts remain

---

## Move 3: BRIDGE — Serve both audiences

Goal: Engineers can integrate datascope into pipelines; consultants still get their PDF.

### 3A: Promote FindingType sub-types to first-class enums ✓
- Depends on: none
- Add `LEADING_ZEROS`, `MIXED_DATES`, `NEAR_CONSTANT`, `DUPLICATE_IDS` to `FindingType` enum in models.py
- Update analyzers to emit the specific type (format_check.py, cardinality.py)
- Remove evidence-key sniffing in severity.py (~4 helper functions + 2 branches) and composer.py (~2 branches)
- Update test assertions that reference the old generic types
- Done when: `grep -c "leading_zero_count.*in.*evidence\|date_formats.*in.*evidence\|near_constant\|suspected.*duplicate" datascope/findings/severity.py datascope/findings/composer.py` returns 0; all tests pass

### 3B: Type source_metadata as TypedDict ✓
- Depends on: none
- Add `SourceMetadata = TypedDict(...)` in models.py with keys: filename, sheet, row_count, column_count
- Update `LoaderResult.source_metadata` type annotation from `dict[str, Any]` to `SourceMetadata`
- Update loaders and pdf.py to use typed access
- Done when: `mypy datascope/models.py` passes (or `pyright` equivalent); no `dict[str, Any]` for source_metadata

### 3C: Add `--format json` output flag ✓
- Depends on: 3A (clean enum makes JSON serialization straightforward)
- Add `--format {pdf,json,both}` argument to cli.py (default: pdf for backward compat)
- JSON schema: `{"source": {...metadata}, "findings": [{severity, finding_type, field_name, assumption, reality, impact, fix, prevention, evidence}], "summary": {critical, warning, info, total}}`
- When format=json, write to `<stem>_diagnostic.json` alongside or instead of PDF
- Done when: `datascope samples/input/sample_mixed_types.xlsx --format json | python -m json.tool` produces valid JSON with all finding fields populated

### 3D: Add `--verbose` / `--quiet` flags ✓
- Depends on: none
- `--quiet`: suppress stdout summary, exit code only (0 = no critical, 1 = has critical findings)
- `--verbose`: print full traceback on analyzer failures instead of one-line warning
- Done when: `datascope file.xlsx --quiet` produces no stdout; `datascope file.xlsx --verbose` with a patched-to-fail analyzer shows full traceback

### 3E: Add GitHub Actions CI workflow ✓
- Depends on: none
- Create `.github/workflows/ci.yml`: pytest + ruff check on push/PR, Python 3.10-3.12 matrix
- Done when: push to a branch triggers CI; green check on passing tests

### 3F: Complete pyproject.toml metadata ✓
- Depends on: none
- Add `authors`, `urls` (homepage, repository, issues), `readme = "README.md"` fields
- Done when: `python -m build` produces a wheel whose metadata includes author, homepage URL, and rendered README

### 3G: Publish to PyPI ✓
- Depends on: 3E, 3F (CI must be green; metadata must be complete)
- Register `datascope` on PyPI (check name availability first — may need `datascope-dq` or similar)
- Add GitHub Actions publish workflow (on tag push)
- Done when: `pip install datascope` (or chosen name) from a fresh venv installs and runs successfully

---

## Move 4: GROW — Expand the moat (future)

Goal: Deepen the technical moat and expand the addressable audience.

### 4A: Add `--max-rows` / file size guard ✓
- Depends on: none
- After loading, check `row_count * column_count`; warn if > 500K cells; abort if > 5M cells (configurable via `--max-rows`)
- Done when: `datascope huge_file.csv` prints a warning at 500K cells and aborts at 5M with a clear message

### 4B: Regex pre-filter for CSV datetime inference ✓
- Depends on: none
- Port `_DATE_LIKE_RE` from format_check.py:139 to csv_loader.py's `_infer_cell`; skip strptime loop if regex doesn't match
- Done when: benchmark on a 100K-row CSV of text strings shows >5x speedup vs. current; all existing tests pass

### 4C: Add HTML report option ✓
- Depends on: 3A (clean enum types), 3C (JSON output as data source for HTML)
- New `datascope/reports/html.py` — Jinja2 template rendering the same finding data as the PDF
- Wire to `--format html` in cli.py
- Done when: `datascope file.xlsx --format html` produces a self-contained HTML file that opens in browser with styled finding cards

### 4D: Add missing-value pattern analyzer ✓
- Depends on: 3A (new FindingType enum value: `MISSING_VALUE_PATTERN`)
- New analyzer in `datascope/analyzers/missing_values.py`
- Detects: columns with >N% nulls, row-level patterns (all nulls in a row = likely empty row), correlated missingness
- Template in templates.py, severity rule in severity.py
- Done when: running on a dataset with a 40%-null column produces a finding with assumption/reality/impact text

### 4E: Add annotated Excel output ✓
- Depends on: none (but benefits from 3A for clean finding types)
- New `datascope/reports/annotated_excel.py` — copies input file, highlights problem cells with conditional formatting, adds a "Findings" sheet
- Wire to `--format annotated-excel` in cli.py
- Done when: `datascope file.xlsx --format annotated-excel` produces a copy of the input with problem cells highlighted in red/amber/blue

### 4F: Add Parquet input support ✓
- Depends on: none
- New `datascope/loaders/parquet.py` — reads via pyarrow, maps Arrow types to Python types for cell_types
- Add `pyarrow` as optional dependency (`pip install datascope[parquet]`)
- Done when: `datascope data.parquet` produces a diagnostic report; cell_types correctly maps Arrow schema types

### 4G: Stream-process CSV loader ✓
- Depends on: 4A (size guard provides fallback for unsupported streaming cases)
- Refactor excel.py and csv_loader.py to build DataFrame + cell_types in a single streaming pass without intermediate `list()` materialization
- Done when: benchmark on a 500K-row file shows <500MB peak memory (vs. current ~1.5GB); all existing tests pass

### 4H: pip audit in CI ✓
- Depends on: 3E (CI must exist)
- Generate `requirements.lock` via `pip-compile` or `uv pip compile`
- Add `pip audit` step to CI workflow
- Done when: `pip install -r requirements.lock` produces identical installs; CI fails on known-vulnerable dependencies

---

## Improvement History

### 2026-10-01 — Audit (health check only)
- **Findings:** 1 critical, 6 important, 5 nice-to-have
- **Top concerns:** Clean DD/MM/YYYY date columns are reported to clients as having 2 different date formats, because each value takes the first strptime pattern that fits (%m/%d/%Y is tried before %d/%m/%Y, format_check.py:123-124, :157). CSV rows with extra or missing fields are silently truncated or padded and never reported (csv_loader.py:148-149), so an unquoted comma drops a value without a finding.
- **Other items:** cp1252 (Excel on Windows) CSVs with accented characters fail with a raw codec error; --quiet exits 0 even when an analyzer crashed; annotated-excel crashes on control characters (IllegalCharacterError); publish.yml uploads to PyPI without waiting for CI; workflow files split between root and .dev/ and drifted (root CLAUDE.md is a typography note, root HANDOFF stops at 2026-09-02, .dev/PLAN.md focus line stale). Nice-to-have: client report text polish (ungrammatical missing-value sentence, raw strptime codes, repeated examples); Parquet list columns and missing pyarrow fail badly; stale MsShawnP URLs in pyproject/README and a dead design-system path in .dev/CLAUDE.md; 4H requirements.lock and A4 numpy-in-requirements-dev checked but not done; missing_values docstring overclaims, 6 stale remote branches, sample fidelity test covers HTML only. No critical was refuted or downgraded in verification.
- **Verified OK:** pytest 378 passed (DATABASE_URL/POSTGRES_PASSWORD unset, temp dirs in session scratchpad, no untracked files left); ruff clean; gitleaks clean over 105 commits; no listener on 5432-5434/15432-15433. HTML/PDF escaping, the 2.4.1 formula-injection fix, .gitignore coverage and the gitleaks pre-commit hook all present. PyPI serves 2.4.2 matching pyproject; CI green on last 3 runs; all Wave 2 criticals fixed. pip-audit skipped (writes outside repo, needs network; CI runs it). Security, code-quality and data-correctness reviews done by hand with 7 in-process probes; /security-review, /ce:review and data-science-reviewer skills not invoked.
- **Action taken:** Audit only — no fixes this session
- **Next review:** 2026-10-29 (supersedes the 2026-12-22 date in the 2026-09-23 entry; project is active)

### 2026-09-30 — Audit findings fixed and released (2.4.0 → 2.4.2)
- **2.4.0:** tagged and published the CSV mixed-date fix; PyPI and the GitHub README now agree.
- **2.4.1:** annotated Excel writes formula-like client text (`= + - @` tab CR) as text cells with `quotePrefix`; values unchanged.
- **2.4.2:** corrupt `.xlsx` exits 1 with a one-line error; a crashed analyzer is disclosed in every report (HTML/PDF/Excel/JSON/stdout).
- **Housekeeping:** gitleaks pre-commit hook carried over from the stale clone (`published/datascope`, now `archived/datascope-stale-2026-09`); this clone is the only live one.

### 2026-09-23 — Audit (health check only)
- **Findings:** 2 critical, 5 important, 4 nice-to-have
- **Top concerns:** v2.4.0 (CSV mixed-date fix) was never tagged or published — PyPI still serves 2.3.4, which silently reconciles mixed date formats in CSVs, while the GitHub README already says CSV mixed dates are detected. Annotated-Excel output writes any input text starting with `=` as a live formula (confirmed with a probe CSV), so a client file can carry formula/CSV injection into the deliverable. A corrupt `.xlsx` crashes the CLI with a raw `BadZipFile` traceback, and a failed analyzer still produces a report that reads as complete.
- **Action taken:** Audit only — no fixes this session. Local tree diverged from origin/main (1 local gitleaks-hook commit vs 2 origin commits from 2026-09-02); judged against origin/main. Tests: 364 pass, 2 `test_samples_fidelity` failures locally are the stale pre-5b20441 samples — origin/main's samples match current code output. Ruff clean. Automated /security-review, /ce:review, data-science-reviewer not available; manual pass done instead.
- **Next review:** 2026-12-22

### 2026-07-31 — Verification pass (post-Claude-Code-issues) + code review
- **Trigger:** User-initiated — verify the recent London-95 visual pass landed correctly.
- **What was reviewed:** 3 reviewer agents (correctness, project-standards, maintainability)
  against the unreleased visual pass; sample regeneration fidelity.
- **What was fixed:**
  1. `html.py` drift trap — body background + zebra even-row were literals equal to
     the just-introduced tokens; pointed both at `CANVAS_HEX` / `LONDON_95_HEX`.
  2. Tightened `test_lailara_design_tokens` — pins each surface selector to its token
     and checks the zebra pair is present and distinct (old test asserted a value that
     predated the change, so it passed even if surfaces reverted to white).
  3. Added `tests/test_samples_fidelity.py` — regenerates HTML samples via `cli.main()`
     and diffs committed copies; caught v2.3.3's stale samples on first run.
  4. Regenerated all 5 sample artifacts (2 HTML, 2 PDF, 1 annotated Excel) that the
     concurrent v2.3.3 release had left stale.
- **Deferred/tracked:** remaining `html.py` text/border literals (`LONDON_5`/`35`/`20`/`85`)
  left hardcoded (pre-existing, flagged by standards agent); PDF/Excel samples have no
  automated staleness guard.
- **Test count:** 364 → 366.
- **Next review:** 2026-08-24 (unchanged — active project).

### 2026-07-27 — Improvement pass (+ code review + UI review)
- **Trigger:** User-initiated (`/improve` + code review + UI review)
- **What was reviewed:** Full source audit; parallel correctness + maintainability
  reviewer agents; automated UI review of the generated HTML reports (new
  `review.yaml`); baseline tests + ruff.
- **What was fixed:**
  1. **[Critical bug]** cardinality.py rounded `uniqueness_ratio` then gated on
     `< 1.0`, so ID columns ≥ ~99.995% unique (e.g. 19,999/20,000) rounded to
     1.0 and duplicate IDs were silently missed. Now gates on the integer test
     `unique_count < total_count`. + regression test. (commit 1d82a68)
  2. **[Bug]** Duplicate column headers collapsed `cell_types` while the
     DataFrame kept both columns → per-column analyzers crashed and the CLI
     swallowed it. Added shared `dedupe_headers()` in loaders/base.py, applied
     in CSV + Excel loaders. + tests. (commit fa73f37)
  3. Extracted `severity_counts()` to reports/_palette.py (was copy-pasted 4×).
  4. cli.py now imports SEVERITY_ORDER/SEVERITY_LABELS instead of redefining.
  5. Deleted dead datascope/analyzers/base.py (unused alias, stale docstring).
  6. Added .parquet to loader docstring + exported load_parquet. (commit fc046ab)
- **UI review:** 25 pass / 0 fail / 3 warnings — all warnings false positives
  (heading-font measured the wrapper div; staleness N/A). Reports on-brand.
- **Test count:** 353 → 359 (6 new). Ruff clean.
- **Deferred:** None. The two residual risks from the correctness pass were
  both confirmed and fixed the same day:
  7. missing_values reported null positions by index *label*, not row
     position — wrong on a non-default index and a crash on a datetime index
     (parquet can restore either). Now resets to a 0-based RangeIndex. (0cbe393)
  8. CSV inference coerced `inf`/`-inf`/`infinity`/`nan` and underscore-grouped
     numbers (`1_000`) to numeric; now kept as strings so the type/sentinel
     analyzers can flag them. (696a2f9)
- **Test count (final):** 353 → 364 (11 new across the whole pass).
- **Next review:** 2026-08-24 (active project)

### 2026-05-22 — Improvement pass
- **Trigger:** Scheduled review (first `/improve` pass)
- **What was reviewed:** Full codebase audit — code quality, tests, dependencies, workflow files, security, git hygiene, linter, pip-audit
- **What was fixed:**
  1. Ruff lint errors (3): unsorted imports in pdf.py, unused Severity imports in 2 test files
  2. pip upgraded to 26.1.1 (2 CVEs fixed)
  3. CLAUDE.md fleshed out with project description, stack, architecture, key conventions
  4. Removed dead `defusedxml` dependency (listed but never imported)
  5. Moved `_WARN_CELLS`/`_ABORT_CELLS` to module-level constants in cli.py
  6. Fixed `input_file` help text to mention .parquet
  7. Extracted shared `health_assessment_text()` to `_palette.py` — PDF and HTML now use identical health assessment logic
  8. Removed dead `if header in field_to_severity: pass` in annotated_excel.py
  9. Extracted shared `DATE_LIKE_RE` regex — csv_loader now imports from format_check.py instead of maintaining a duplicate
- **Deferred:** None
- **Next review:** 2026-06-22
