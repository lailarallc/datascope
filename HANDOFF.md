# HANDOFF

Session-to-session continuity. Newest entry on top.

## 2026-09-02 09:40

**Started from:** datascope CI red since before the org migration — recorded as a
known-red baseline in fleet-ops MIGRATION.md. Task: diagnose why, fix correctly,
get CI green, update the baseline note.

**Did:** Found local `main` was 7 commits behind `origin/main`; the real red state
was `origin/main @ 9b0b2cc` (font re-vendor). Fast-forwarded, reproduced the
`test_samples_fidelity` failure. Root cause: `9b0b2cc` swapped the embedded Source
Sans woff2 (mislabeled ExtraLight → correct weight-400) but never regenerated the
committed samples, which base64-embed that font. Proved sample-stale, not a code
regression — normalized diff confined to the single `@font-face src:url(data:...)`
line. Regenerated all font-embedding formats (HTML/PDF/xlsx) via
`scripts/regenerate_samples.sh`. Committed `5b20441`, pushed, CI green on
3.10/3.11/3.12. Updated fleet-ops MIGRATION.md (`164ce50`) to clear the datascope
baseline entry, cross-referenced.

**State:** `main` green on all three Python versions, clean tree, pushed. No open
datascope work. fleet-ops baseline now down to 1 pre-existing red (`lailara-intake`).

**Next:** datascope is clean — nothing pending here. If clearing the last fleet
baseline red: `lailara-intake` deploy fails on npm ERESOLVE (wrangler@3.90.0 wants
`@cloudflare/workers-types@^4`, project pins `^5`) — align versions, redeploy. That
work lives in the lailara-intake repo, not here.

## 2026-10-02 12:11

**What changed:** datascope Wave 3 critical fixed: (1) DD/MM/YYYY false mixed-date finding — cd10539; (2) ragged CSV rows now a CRITICAL MALFORMED_ROWS finding — 310ca25. 388 tests pass, ruff clean. Not released; proposed version 2.5.0.

**Why:** 2026-10-01 audit critical (.dev/PLAN.md). Clients were told clean DD/MM columns mixed formats, and an unquoted comma dropped values with no finding.

**State:** Both fixes test-first (new tests failed on old code). Samples unchanged (fidelity test passes). Loader still cuts/pads ragged rows; it now reports them. CHANGELOG not updated (done at release). PyPI still 2.4.2.

**Next:** Release 2.5.0 (new finding type = minor bump): CHANGELOG entry, bump pyproject, regenerate samples, tag.

---
