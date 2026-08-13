#!/bin/bash
# Shared helpers for storage-service integration test-scripts.
# Sourced by every test-*.sh. Reads config from env (never hardcodes secrets).
set -uo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8200}"
BUCKET="${BUCKET:-storybook-assets}"
# S2S key: must be one VALUE from STORAGE_API_KEYS. Dev default matches .env.example.
API_KEY="${STORAGE_TEST_API_KEY:-dev-image-api-key}"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURES="$DIR/fixtures"
KEYS_ENV="$FIXTURES/local-keys.env"
mkdir -p "$FIXTURES"

FAILED=0

# Mint a user JWT via the CLI script (HS256, SUPABASE_JWT_SECRET). Args passed through.
mint_user_jwt() {
  ( cd "$DIR/.." && uv run python scripts/mint_dev_user_token.py "$@" )
}

# USER_JWT: from env or minted fresh (1h). Lazy so scripts that don't need it skip mint.
user_jwt() {
  if [ -n "${USER_JWT:-}" ]; then echo "$USER_JWT"; else mint_user_jwt; fi
}

# req METHOD PATH  → emits body + trailing "\n<status>" (curl -w). Extra curl args after PATH.
req() {
  local method="$1" path="$2"; shift 2
  curl -s -X "$method" "$BASE_URL$path" -w $'\n%{http_code}' "$@"
}

# assert_status EXPECTED "RESPONSE" LABEL  (RESPONSE = body + trailing status line)
assert_status() {
  local expected="$1" resp="$2" label="$3"
  local actual; actual="$(printf '%s' "$resp" | tail -1)"
  if [ "$actual" = "$expected" ]; then
    echo "  ✅ $label (HTTP $actual)"
  else
    echo "  ❌ $label — expected $expected, got $actual"
    echo "     body: $(printf '%s' "$resp" | sed '$d' | head -c 400)"
    FAILED=1
  fi
}

# assert_error_code EXPECTED_CODE "RESPONSE" LABEL
assert_error_code() {
  local expected="$1" resp="$2" label="$3"
  if printf '%s' "$resp" | sed '$d' | grep -q "\"code\":\"$expected\""; then
    echo "  ✅ $label (code $expected)"
  else
    echo "  ❌ $label — expected code $expected"
    echo "     body: $(printf '%s' "$resp" | sed '$d' | head -c 400)"
    FAILED=1
  fi
}

# body_of "RESPONSE" → prints just the body (drops trailing status line)
body_of() { printf '%s' "$1" | sed '$d'; }

save_key() {  # save_key VARNAME value  → append to local-keys.env
  echo "export $1='$2'" >> "$KEYS_ENV"
}

finish() {
  if [ "$FAILED" = "0" ]; then echo "✅ PASSED"; exit 0; else echo "❌ FAILED"; exit 1; fi
}
