#!/bin/bash
# DELETE /api/storage/objects/{bucket}/{key:path} — best-effort, ALWAYS 200 (never 404).
#   first delete -> {deleted:true} ; second delete -> {deleted:false}.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
echo "── delete-object ──"

KEY="ai-logs/del-$(date +%s)-$RANDOM.png"; TMP="$(mktemp)"; printf 'D-%s' "$RANDOM" > "$TMP"
req PUT "/api/storage/objects/$BUCKET/$KEY" -H "X-API-Key: $API_KEY" -H "Content-Type: image/png" --data-binary "@$TMP" >/dev/null; rm -f "$TMP"

R="$(req DELETE "/api/storage/objects/$BUCKET/$KEY" -H "X-API-Key: $API_KEY")"
assert_status 200 "$R" "delete existing 200"
if body_of "$R" | grep -q '"deleted":true'; then echo "  ✅ deleted:true"; else echo "  ❌ expected deleted:true"; FAILED=1; fi

R="$(req DELETE "/api/storage/objects/$BUCKET/$KEY" -H "X-API-Key: $API_KEY")"
assert_status 200 "$R" "delete again 200 (best-effort)"
if body_of "$R" | grep -q '"deleted":false'; then echo "  ✅ deleted:false"; else echo "  ❌ expected deleted:false"; FAILED=1; fi
finish
