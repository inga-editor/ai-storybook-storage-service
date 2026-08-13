#!/bin/bash
# Auth matrix: 401 for missing/bad X-API-Key, missing/broken/expired Bearer JWT.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
echo "── auth-matrix ──"
TMP="$(mktemp)"; printf 'x' > "$TMP"; K="ai-logs/auth-$RANDOM.png"

# S2S: missing key → 401
R="$(req PUT "/api/storage/objects/$BUCKET/$K" -H "Content-Type: image/png" --data-binary "@$TMP")"
assert_error_code UNAUTHORIZED "$R" "PUT no X-API-Key 401"
# S2S: wrong key → 401
R="$(req PUT "/api/storage/objects/$BUCKET/$K" -H "X-API-Key: totally-wrong" -H "Content-Type: image/png" --data-binary "@$TMP")"
assert_error_code UNAUTHORIZED "$R" "PUT wrong X-API-Key 401"

# user: missing Bearer → 401
R="$(req POST "/api/storage/uploads" -F "file=@$FIXTURES/sample-image.png;type=image/png" -F "key=humans/x/y.png")"
assert_error_code UNAUTHORIZED "$R" "upload no Bearer 401"
# user: broken token → 401
R="$(req POST "/api/storage/uploads" -H "Authorization: Bearer not.a.jwt" -F "file=@$FIXTURES/sample-image.png;type=image/png" -F "key=humans/x/y.png")"
assert_error_code UNAUTHORIZED "$R" "upload broken JWT 401"
# user: expired token → 401
EXP="$(mint_user_jwt --exp-in -60)"
R="$(req POST "/api/storage/uploads" -H "Authorization: Bearer $EXP" -F "file=@$FIXTURES/sample-image.png;type=image/png" -F "key=humans/x/y.png")"
assert_error_code UNAUTHORIZED "$R" "upload expired JWT 401"
# user: wrong aud → 401
BADAUD="$(mint_user_jwt --aud wrong-audience)"
R="$(req POST "/api/storage/uploads" -H "Authorization: Bearer $BADAUD" -F "file=@$FIXTURES/sample-image.png;type=image/png" -F "key=humans/x/y.png")"
assert_error_code UNAUTHORIZED "$R" "upload wrong aud 401"
rm -f "$TMP"
finish
