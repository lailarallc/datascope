#!/usr/bin/env bash
# Regenerate the committed samples/output/ deliverables reproducibly.
#
# SOURCE_DATE_EPOCH pins the report generator timestamp (datascope/reports/html.py)
# so the .html and .pdf outputs are byte-identical run-to-run. The value below is
# 2026-09-30 00:00:00 UTC (the 2.4.1 release date); keep it stable so anyone
# regenerating gets the same bytes, and bump it only on a release.
#
# Note: the annotated .xlsx is content-reproducible but NOT byte-lockable —
# openpyxl stamps wall-clock times into the workbook envelope.
set -euo pipefail
cd "$(dirname "$0")/.."

export SOURCE_DATE_EPOCH=1790726400  # 2026-09-30 00:00:00 UTC (2.4.1)

for fmt in html pdf; do
  python -m datascope samples/input/sample_mixed_types.xlsx --output-dir samples/output/ --format "$fmt"
  python -m datascope samples/input/sample_sales.xlsx        --output-dir samples/output/ --format "$fmt"
done
python -m datascope samples/input/sample_mixed_types.xlsx --output-dir samples/output/ --format annotated-excel

echo "Regenerated samples/output/ with SOURCE_DATE_EPOCH=$SOURCE_DATE_EPOCH"
