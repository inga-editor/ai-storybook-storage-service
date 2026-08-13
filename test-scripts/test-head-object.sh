#!/bin/bash
# HEAD /api/storage/objects/{bucket}/{key:path} — headers-only metadata (validation 260813).
#   existing -> 200 + ETag/Content-Length/Content-Type ; missing -> 404.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
[ -f "$KEYS_ENV" ] && source "$KEYS_ENV"
echo "── head-object ──"

KEY="${PUT_KEY:-}"
if [ -z "$KEY" ]; then
  KEY="ai-logs/head-$(date +%s)-$RANDOM.png"; TMP="$(mktemp)"; printf 'H-%s' "$RANDOM" > "$TMP"
  req PUT "/api/storage/objects/$BUCKET/$KEY" -H "X-API-Key: $API_KEY" -H "Content-Type: image/png" --data-binary "@$TMP" >/dev/null; rm -f "$TMP"
fi

# HEAD existing → 200 + headers (curl -I style; capture status + headers)
H="$(curl -s -o /dev/null -D - -w '%{http_code}' -X HEAD "$BASE_URL/api/storage/objects/$BUCKET/$KEY" -H "X-API-Key: $API_KEY")"
CODE="$(printf '%s' "$H" | tail -1)"
if [ "$CODE" = "200" ]; then echo "  ✅ existing HEAD 200"; else echo "  ❌ existing HEAD expected 200 got $CODE"; FAILED=1; fi
if printf '%s' "$H" | grep -qi '^etag:'; then echo "  ✅ ETag header"; else echo "  ❌ no ETag header"; FAILED=1; fi
if printf '%s' "$H" | grep -qi '^content-length:'; then echo "  ✅ Content-Length header"; else echo "  ❌ no Content-Length"; FAILED=1; fi

# HEAD missing → 404
C="$(curl -s -o /dev/null -w '%{http_code}' -X HEAD "$BASE_URL/api/storage/objects/$BUCKET/ai-logs/does-not-exist-$RANDOM.png" -H "X-API-Key: $API_KEY")"
if [ "$C" = "404" ]; then echo "  ✅ missing HEAD 404"; else echo "  ❌ missing HEAD expected 404 got $C"; FAILED=1; fi
finish
