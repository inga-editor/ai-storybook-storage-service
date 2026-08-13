#!/usr/bin/env python3
"""Mint a dev Supabase-style user JWT (HS256) for local testing.

Precedent (feedback_no_http_dev_mint_endpoint): minting is a CLI script ONLY —
there is NO HTTP dev-mint endpoint. Signs with SUPABASE_JWT_SECRET from .env,
claims `{aud:"authenticated", sub:<uuid>, exp:+ttl}`. Prints the token to stdout.

Usage:
  uv run python scripts/mint_dev_user_token.py                 # 1h token
  uv run python scripts/mint_dev_user_token.py --exp-in -60    # already-expired
  uv run python scripts/mint_dev_user_token.py --aud wrong     # bad-aud (401 test)
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import uuid
from pathlib import Path

import jwt


def _load_secret() -> str:
    secret = os.environ.get("SUPABASE_JWT_SECRET", "")
    if secret:
        return secret
    env = Path(__file__).resolve().parent.parent / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line.startswith("SUPABASE_JWT_SECRET="):
                return line.split("=", 1)[1].strip()
    print("SUPABASE_JWT_SECRET not set (env or .env)", file=sys.stderr)
    sys.exit(2)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp-in", type=int, default=3600, help="seconds until expiry (negative = already expired)")
    ap.add_argument("--sub", default=None, help="subject uuid (default: random)")
    ap.add_argument("--aud", default="authenticated", help="audience claim (use a wrong value to test 401)")
    args = ap.parse_args()

    now = int(time.time())
    claims = {
        "aud": args.aud,
        "sub": args.sub or str(uuid.uuid4()),
        "role": "authenticated",
        "iat": now,
        "exp": now + args.exp_in,
    }
    token = jwt.encode(claims, _load_secret(), algorithm="HS256")
    print(token)


if __name__ == "__main__":
    main()
