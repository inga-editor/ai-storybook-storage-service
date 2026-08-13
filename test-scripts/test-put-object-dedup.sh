#!/bin/bash
# 409-benign dedup: PUT upsert=false onto an existing key -> 409 ALREADY_EXISTS.
# The MOST important parity with content_store — client maps 409 -> deduped=true.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
[ -f "$KEYS_ENV" ] && source "$KEYS_ENV"
echo "── put-object dedup (409-benign) ──"

KEY="${PUT_KEY:-}"
if [ -z "$KEY" ]; then
  # standalone: seed a key first
  KEY="ai-logs/dedup-$(date +%s)-$RANDOM.png"
  TMP="$(mktemp)"; printf 'SEED-%s' "$RANDOM" > "$TMP"
  req PUT "/api/storage/objects/$BUCKET/$KEY" -H "X-API-Key: $API_KEY" -H "Content-Type: image/png" --data-binary "@$TMP" >/dev/null
  rm -f "$TMP"
fi

TMP="$(mktemp)"; printf 'AGAIN-%s' "$RANDOM" > "$TMP"
R="$(req PUT "/api/storage/objects/$BUCKET/$KEY" -H "X-API-Key: $API_KEY" -H "Content-Type: image/png" --data-binary "@$TMP")"
assert_status 409 "$R" "upsert=false existing key 409"
assert_error_code ALREADY_EXISTS "$R" "code ALREADY_EXISTS"
rm -f "$TMP"
finish
