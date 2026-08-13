#!/bin/bash
# POST /api/storage/sign → GET /files-signed/...  (verify HMAC → X-Accel-Redirect).
#   NGINX=1 : expect real bytes (200). default : expect X-Accel-Redirect header.
#   negative: tampered sig → 403 ; expired exp → 403.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
echo "── sign-and-fetch ──"

KEY="exports/test-$(date +%s)-$RANDOM.pdf"; TMP="$(mktemp)"; printf '%%PDF-1.4 %s' "$RANDOM" > "$TMP"
req PUT "/api/storage/objects/$BUCKET/$KEY" -H "X-API-Key: $API_KEY" -H "Content-Type: application/pdf" --data-binary "@$TMP" >/dev/null; rm -f "$TMP"

# sign
R="$(req POST "/api/storage/sign" -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" -d "{\"bucket\":\"$BUCKET\",\"key\":\"$KEY\",\"expires_in\":3600}")"
assert_status 200 "$R" "sign 200"
SIGNED="$(body_of "$R" | grep -oE 'https?://[^"]*files-signed[^"]*' | head -1)"
if [ -z "$SIGNED" ]; then echo "  ❌ no signed_url"; FAILED=1; finish; fi
echo "  signed: $SIGNED"

# fetch signed
PATHQ="${SIGNED#*/files-signed/}"
if [ "${NGINX:-0}" = "1" ]; then
  C="$(curl -s -o /dev/null -w '%{http_code}' "$SIGNED")"
  if [ "$C" = "200" ]; then echo "  ✅ nginx signed fetch 200"; else echo "  ❌ signed fetch expected 200 got $C"; FAILED=1; fi
else
  H="$(curl -s -o /dev/null -D - -w '%{http_code}' "$BASE_URL/files-signed/$PATHQ")"
  CODE="$(printf '%s' "$H" | tail -1)"
  if [ "$CODE" = "200" ]; then echo "  ✅ signed GET 200"; else echo "  ❌ signed GET expected 200 got $CODE"; FAILED=1; fi
  if printf '%s' "$H" | grep -qi 'x-accel-redirect'; then echo "  ✅ X-Accel-Redirect header"; else echo "  ❌ no X-Accel-Redirect (dev stream may be on)"; fi
fi

# negative: tamper sig → 403
BAD="$(printf '%s' "$BASE_URL/files-signed/$PATHQ" | sed 's/sig=\(.\)/sig=x/')"
C="$(curl -s -o /dev/null -w '%{http_code}' "$BAD")"
if [ "$C" = "403" ]; then echo "  ✅ tampered sig 403"; else echo "  ❌ tampered sig expected 403 got $C"; FAILED=1; fi

# negative: expired exp → 403 (rebuild query with exp in the past, keep same sig — mismatch → 403)
EXPQ="$(printf '%s' "/files-signed/$PATHQ" | sed -E 's/exp=[0-9]+/exp=1/')"
C="$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL$EXPQ")"
if [ "$C" = "403" ]; then echo "  ✅ expired/mismatch exp 403"; else echo "  ❌ expired exp expected 403 got $C"; FAILED=1; fi
finish
