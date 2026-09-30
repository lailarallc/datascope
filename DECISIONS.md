# DECISIONS

Durable choices with rationale. Newest on top.

## 2026-09-30 — Output never alters client values, even to neutralize them

- **Why:** datascope reports on the data it received. Prepending `'` or a space to
  defuse a formula changes the value, so the deliverable no longer matches the source.
- **Scope:** Every output format (annotated Excel, HTML, PDF, JSON). Formula-like text
  is made safe through cell type or escaping (`data_type="s"` + `quotePrefix`, `_e`,
  `_safe`), never by editing the string.
- **Do not:** prepend, strip or rewrite client text in any output. Do not "fix"
  `_write_cell` to the OWASP apostrophe pattern.

## 2026-09-02 — A font/asset change is not done until all sample formats are regenerated

- **Why:** Vendored fonts (`datascope/reports/fonts/*.woff2`) are base64-embedded
  directly into every generated report — HTML, PDF, and annotated-Excel alike.
  Replacing a font file therefore changes the *bytes* of every committed sample in
  `samples/output/`, even though report text/structure/colors are untouched. In
  2026-08 a font re-vendor (`9b0b2cc`) shipped the font but not the regenerated
  samples, leaving CI red on `test_samples_fidelity`.
- **Scope:** Any change to files under `datascope/reports/fonts/` or anything else
  embedded into report output. After such a change, run
  `scripts/regenerate_samples.sh` (pins `SOURCE_DATE_EPOCH` for byte-reproducibility)
  and commit the refreshed `samples/output/` in the **same** change.
- **Do not:** Do not assume "fonts can't change report text" means the samples are
  unaffected — the font lives *inside* the report bytes. Do not rely on
  `test_samples_fidelity` to catch a stale PDF or xlsx: it only guards the two HTML
  samples. Regenerate all three formats, not just HTML.
