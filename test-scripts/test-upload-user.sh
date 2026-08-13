#!/bin/bash
# POST /api/storage/uploads — browser multipart upload, Bearer user JWT.
#   happy 201 ; 403 prefix ; 415 mime ; 413 size.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
echo "── upload-user (multipart) ──"

JWT="$(user_jwt)"
IMG="$FIXTURES/sample-image.png"
AUD="$FIXTURES/sample-audio.mp3"

UUID="$(uuidgen 2>/dev/null || python3 -c 'import uuid;print(uuid.uuid4())')"
KEY="humans/$UUID/$UUID.png"

# happy path → 201 into FE-writable prefix humans/
R="$(req POST "/api/storage/uploads" -H "Authorization: Bearer $JWT" -F "file=@$IMG;type=image/png" -F "key=$KEY")"
assert_status 201 "$R" "user upload humans/ 201"
if body_of "$R" | grep -q "/files/$BUCKET/"; then echo "  ✅ data.url"; else echo "  ❌ no data.url"; FAILED=1; fi

# 403: system prefix ai-logs/ not FE-writable
R="$(req POST "/api/storage/uploads" -H "Authorization: Bearer $JWT" -F "file=@$IMG;type=image/png" -F "key=ai-logs/$UUID.png")"
assert_error_code PREFIX_NOT_ALLOWED "$R" "ai-logs/ 403"

# 415: audio mime into humans/ (image class)
R="$(req POST "/api/storage/uploads" -H "Authorization: Bearer $JWT" -F "file=@$AUD;type=audio/mpeg" -F "key=humans/$UUID/$UUID.mp3")"
assert_error_code UNSUPPORTED_MEDIA_TYPE "$R" "mp3 into humans/ 415"

# 413: >10MB image into humans/
BIG="$(mktemp)"; dd if=/dev/zero of="$BIG" bs=1m count=11 2>/dev/null
R="$(req POST "/api/storage/uploads" -H "Authorization: Bearer $JWT" -F "file=@$BIG;type=image/png" -F "key=humans/$UUID/big.png")"
assert_error_code PAYLOAD_TOO_LARGE "$R" "11MB into humans/ 413"
rm -f "$BIG"
finish
