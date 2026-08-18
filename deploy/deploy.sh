#!/usr/bin/env bash
# Build + deploy storage-service on the prod server (runs from repo root, via the
# self-hosted runner or by hand). Requires: docker + compose v2, .env in STATE_DIR.
set -euo pipefail

STATE_DIR=/home/tbng84/Projects/AI-Story-Book/ai-storybook-storage-service
HEALTH_URL=http://localhost:8200/healthz
COMPOSE="docker compose -f deploy/compose.yml"
KEEP_TAGS=5

SHA=$(git rev-parse --short HEAD)
echo "==> deploying storage-service:$SHA"

# warn (not fail) on env keys present in .env.example but missing on the server —
# a missing optional var is legitimate, a missing required one will fail the health gate
comm -23 <(grep -oE '^[A-Z_]+' .env.example | sort -u) \
         <(grep -oE '^[A-Z_]+' "$STATE_DIR/.env" | sort -u) \
  | sed 's/^/WARN missing in server .env: /' || true

# run the container as the owner of STORAGE_ROOT so written blobs stay readable by
# nginx and interchangeable with the manual script-run fallback
STORAGE_ROOT_HOST=$(grep -E '^STORAGE_ROOT=' "$STATE_DIR/.env" | cut -d= -f2)
STORAGE_UID=$(stat -c %u "$STORAGE_ROOT_HOST")
STORAGE_GID=$(stat -c %g "$STORAGE_ROOT_HOST")
export STORAGE_UID STORAGE_GID
echo "==> STORAGE_ROOT=$STORAGE_ROOT_HOST (owner $STORAGE_UID:$STORAGE_GID)"

PREV=$(docker inspect -f '{{.Config.Image}}' storage-service 2>/dev/null || echo "")
echo "==> current image: ${PREV:-<none>}"

docker build -t "storage-service:$SHA" .

TAG=$SHA $COMPOSE up -d

# health gate: HTTP 200 AND degraded:false (disk-free check inside /healthz)
ok=""
for _ in $(seq 1 30); do
  sleep 2
  if body=$(curl -sf "$HEALTH_URL") && echo "$body" | grep -q '"degraded": *false'; then
    ok=1
    break
  fi
done

if [ -z "$ok" ]; then
  echo "!! HEALTH GATE FAILED for storage-service:$SHA — recent logs:"
  journalctl CONTAINER_NAME=storage-service -n 100 --no-pager || true
  if [ -n "$PREV" ]; then
    echo "!! rolling back to $PREV"
    TAG=${PREV#storage-service:} $COMPOSE up -d
  else
    echo "!! no previous image to roll back to — container left as-is for inspection"
    echo "!! manual fallback: docker rm -f storage-service && cd $STATE_DIR && ./scripts/run-service.sh"
  fi
  exit 1
fi
echo "==> healthy: storage-service:$SHA"

# keep the last $KEEP_TAGS images for manual rollback, drop the rest
docker images storage-service --format '{{.Tag}}' \
  | grep -vx "$SHA" | tail -n "+$KEEP_TAGS" \
  | xargs -r -I{} docker rmi "storage-service:{}" 2>/dev/null || true
docker image prune -f >/dev/null

echo "==> deploy done: storage-service:$SHA"
