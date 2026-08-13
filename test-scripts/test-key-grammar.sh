#!/bin/bash
# Key grammar (design 04 §3): all bad keys → 400 VALIDATION_ERROR; bad bucket → 400.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
echo "── key-grammar ──"
TMP="$(mktemp)"; printf 'x' > "$TMP"

# --path-as-is: stop curl from normalizing `..`/`//` before the request reaches the
# server (clients/proxies normalize by default — that is exactly why the server still
# validates grammar as defense-in-depth).
put() { curl -s --path-as-is -X PUT "$BASE_URL/api/storage/objects/$1" -w $'\n%{http_code}' -H "X-API-Key: $API_KEY" -H "Content-Type: image/png" --data-binary "@$TMP"; }

# traversal & bad segments
assert_error_code VALIDATION_ERROR "$(put "$BUCKET/a/../b.png")"     "dotdot traversal"
assert_error_code VALIDATION_ERROR "$(put "$BUCKET/a//b.png")"       "empty segment //"
assert_error_code VALIDATION_ERROR "$(put "$BUCKET//a.png")"         "leading slash"
# encoded traversal (%2e%2e -> ".." after ASGI decode) MUST still be caught as ".." segment.
# (A lone %2e decodes to a harmless literal dot; the real threat is encoded "..".)
assert_error_code VALIDATION_ERROR "$(put "$BUCKET/a/%2e%2e/b.png")"  "encoded traversal %2e%2e"
assert_error_code VALIDATION_ERROR "$(put "$BUCKET/a%2525.png")"      "literal percent survives decode"
assert_error_code VALIDATION_ERROR "$(put "$BUCKET/noext")"          "missing extension"
# long key (>1024)
LONG="$(python3 -c 'print("a"*1100)')"
assert_error_code VALIDATION_ERROR "$(put "$BUCKET/$LONG.png")"      "key > 1024"
# bad bucket
assert_error_code VALIDATION_ERROR "$(put "wrong-bucket/a.png")"     "bucket not in allowlist"

# NOTE: backslash key `a\b.png` is shell-fragile; covered by pytest test_key_grammar instead.
rm -f "$TMP"
finish
