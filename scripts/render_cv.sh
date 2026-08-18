#!/usr/bin/env bash
# Render a role directory's cv.html to PDF and verify it is one page.
#
#   scripts/render_cv.sh people/hanna/created_data/acme-backend-engineer
#   scripts/render_cv.sh people/hanna/created_data/acme-backend-engineer --cover
#
# Runs preflight first and refuses to render a CV that fails it. Prints the page
# count as `pages [b'1']`. Anything other than [b'1'] is a failure for a CV that
# is meant to fit on one page — reflow and re-run, at most twice.
set -euo pipefail

DIR="${1:-}"
MODE="${2:-}"
[ -n "$DIR" ] || { echo "usage: $0 <role-dir> [--cover]" >&2; exit 2; }
[ -d "$DIR" ] || { echo "render_cv: not a directory: $DIR" >&2; exit 2; }

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIR="$(cd "$DIR" && pwd)"

if [ "$MODE" = "--cover" ]; then
  SRC="$DIR/cover-letter.html"; SUFFIX="Cover_Letter"
else
  SRC="$DIR/cv.html"; SUFFIX="CV"
fi
[ -f "$SRC" ] || { echo "render_cv: missing $SRC" >&2; exit 2; }

# Person name for the output filename — the recruiter sees this string.
PERSON_DIR="$(dirname "$(dirname "$DIR")")"
if [ -f "$PERSON_DIR/.person" ]; then
  NAME="$(tr -d '\r' < "$PERSON_DIR/.person" | head -1)"
else
  NAME="$(basename "$PERSON_DIR")"
fi
SAFE_NAME="$(printf '%s' "$NAME" | tr ' ' '_' | tr -cd 'A-Za-z0-9_-')"
OUT="$DIR/${SAFE_NAME}_${SUFFIX}.pdf"

echo "preflight $DIR"
python3 "$HERE/preflight.py" "$DIR"

CHROME=""
for c in google-chrome-stable google-chrome chromium chromium-browser; do
  command -v "$c" >/dev/null 2>&1 && { CHROME="$c"; break; }
done
[ -n "$CHROME" ] || { echo "render_cv: no Chrome/Chromium found on PATH" >&2; exit 3; }

"$CHROME" --headless=new --no-sandbox --disable-gpu --no-pdf-header-footer \
  --print-to-pdf="$OUT" "file://$SRC" >/dev/null 2>&1

[ -s "$OUT" ] || { echo "render_cv: produced no output at $OUT" >&2; exit 3; }

# pdfinfo/qpdf are absent on many build hosts. Read /Count out of the PDF bytes.
PAGES="$(python3 -c "import re,sys;d=open(sys.argv[1],'rb').read();print(re.findall(rb'/Count\s+(\d+)',d))" "$OUT")"
echo "pages $PAGES"
echo "wrote $OUT"

# Second opinion when poppler is available: proves the text is extractable, which is
# what an ATS actually reads, and catches a page 2 the byte count missed.
if command -v pdftotext >/dev/null 2>&1; then
  # pdftotext exits 99 when asked for a page that does not exist, which is the
  # answer we want for page 2. Both calls are tolerated failures.
  WORDS="$(pdftotext -f 1 -l 1 "$OUT" - 2>/dev/null | wc -w || true)"
  OVERFLOW="$(pdftotext -f 2 -l 2 "$OUT" - 2>/dev/null | tr -d '[:space:]' | wc -c || true)"
  echo "page 1 extractable words: ${WORDS:-0}"
  if [ "${OVERFLOW:-0}" -gt 0 ]; then
    echo "WARNING: page 2 carries $OVERFLOW characters — this is not a one-page CV"
  fi
fi

if [ "$MODE" != "--cover" ] && [ "$PAGES" != "[b'1']" ]; then
  echo "render_cv: NOT one page. Cut the least-relevant filler — never the protected evidence — and re-run." >&2
  exit 1
fi
