#!/bin/bash
# Canonical run command for the Storybook Storage Service.
#
# Bind 127.0.0.1 by DEFAULT (auth 04 §1 Network exposure): the S2S routes
# (PUT/HEAD objects, POST /sign, DELETE mode-service) are the security boundary —
# they must never listen on a public interface. nginx is the ONLY thing that
# exposes the user-facing routes (uploads / delete / files-signed) + public
# /files/ read path. Do NOT change HOST to 0.0.0.0 without a firewall in front.
#
# The service is STATELESS (no in-memory session state) ⇒ WORKERS is free, unlike
# swap-service's mandatory workers=1. Scale with WORKERS env when CPU-bound.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
exec uv run uvicorn src.main:app \
  --host "${HOST:-127.0.0.1}" \
  --port "${PORT:-8200}" \
  --workers "${WORKERS:-1}"
