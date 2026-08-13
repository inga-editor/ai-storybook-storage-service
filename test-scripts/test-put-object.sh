#!/bin/bash
# PUT /api/storage/objects/{bucket}/{key:path} — S2S write.
#   201 new · upsert=true 200 · streaming big file · 413 by-prefix cap.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
echo "── put-object ──"

KEY="ai-logs/test-$(date +%s)-$RANDOM.png"
TMP="$(mktemp)"; printf 'PNGDATA-%s' "$RANDOM" > "$TMP"

# 1) new object -> 201, data.url matches /files/{bucket}/{key}, etag 64-hex, deduped=false
R="$(req PUT "/api/storage/objects/$BUCKET/$KEY" -H "X-API-Key: $API_KEY" -H "Content-Type: image/png" --data-binary "@$TMP")"
assert_status 201 "$R" "new object 201"
if body_of "$R" | grep -q "\"key\":\"$KEY\""; then echo "  ✅ echoes key"; else echo "  ❌ key missing"; FAILED=1; fi
if body_of "$R" | grep -qE '"etag":"[0-9a-f]{64}"'; then echo "  ✅ etag sha256"; else echo "  ❌ etag not 64-hex"; FAILED=1; fi
if body_of "$R" | grep -q "/files/$BUCKET/$KEY"; then echo "  ✅ url built"; else echo "  ❌ url wrong"; FAILED=1; fi
save_key PUT_KEY "$KEY"

# 2) same key with upsert=true -> 200
R="$(req PUT "/api/storage/objects/$BUCKET/$KEY?upsert=true" -H "X-API-Key: $API_KEY" -H "Content-Type: image/png" --data-binary "@$TMP")"
assert_status 200 "$R" "upsert overwrite 200"

# 3) missing Content-Type -> 400  (curl's --data-binary defaults a CT header; "-H 'Content-Type:'" strips it)
R="$(req PUT "/api/storage/objects/$BUCKET/ai-logs/no-ct-$RANDOM.png" -H "X-API-Key: $API_KEY" -H "Content-Type:" --data-binary "@$TMP")"
assert_error_code VALIDATION_ERROR "$R" "missing Content-Type 400"

# 4) streaming: 60MB into videos/ (cap 3GB) -> 201 ; same size into ai-logs/ (cap 50MB) -> 413
BIG="$(mktemp)"; dd if=/dev/zero of="$BIG" bs=1m count=60 2>/dev/null
VKEY="videos/test-$(date +%s)-$RANDOM.mp4"
R="$(req PUT "/api/storage/objects/$BUCKET/$VKEY" -H "X-API-Key: $API_KEY" -H "Content-Type: video/mp4" --data-binary "@$BIG")"
assert_status 201 "$R" "60MB into videos/ 201"
R="$(req PUT "/api/storage/objects/$BUCKET/ai-logs/big-$RANDOM.png" -H "X-API-Key: $API_KEY" -H "Content-Type: image/png" --data-binary "@$BIG")"
assert_error_code PAYLOAD_TOO_LARGE "$R" "60MB into ai-logs/ 413"

# 5) OPTIONAL huge file (RUN_BIG=1): ~1GB into videos/ -> 201 (verify streaming, no OOM)
if [ "${RUN_BIG:-0}" = "1" ]; then
  HUGE="$(mktemp)"; dd if=/dev/zero of="$HUGE" bs=1m count=1024 2>/dev/null
  R="$(req PUT "/api/storage/objects/$BUCKET/videos/huge-$RANDOM.mp4" -H "X-API-Key: $API_KEY" -H "Content-Type: video/mp4" --data-binary "@$HUGE")"
  assert_status 201 "$R" "1GB into videos/ 201 (streaming)"
  rm -f "$HUGE"
fi

rm -f "$TMP" "$BIG"
finish
