#!/bin/bash
# Aggregate runner — runs each test-*.sh as an isolated subprocess, tallies PASS/FAIL.
# Order matters: put-object seeds fixtures/local-keys.env consumed by dedup/head.
#
# Precondition (image-api-python-workflow Step N-1): `uv run pytest tests/` GREEN
# before running this integration suite against a live server.
#   NGINX=1   → sign-and-fetch checks real bytes through nginx.
#   RUN_BIG=1 → put-object also streams a ~1GB file (videos/, cap 3GB).
#   507 disk-full is MANUAL-ONLY (needs a tiny tmpfs) — not automated here.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SCRIPTS=(
  test-healthz.sh
  test-put-object.sh          # seeds local-keys.env
  test-put-object-dedup.sh    # consumes PUT_KEY
  test-head-object.sh
  test-sign-and-fetch.sh
  test-upload-user.sh
  test-auth-matrix.sh
  test-key-grammar.sh
  test-delete-object.sh       # last (destructive)
)

# fresh keys file each run
rm -f "$DIR/fixtures/local-keys.env"

PASS=0; FAIL=0; FAILED_NAMES=""
echo "════════════════════════════════════════════════════════"
for s in "${SCRIPTS[@]}"; do
  echo "▶ $s"
  if bash "$DIR/$s"; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); FAILED_NAMES="$FAILED_NAMES $s"; fi
  echo "────────────────────────────────────────────────────────"
done
echo "SUMMARY: passed $PASS / $((PASS+FAIL))"
if [ "$FAIL" != "0" ]; then echo "FAILED:$FAILED_NAMES"; echo "❌ ALL NOT PASSED"; exit 1; fi
echo "✅ ALL PASSED"
