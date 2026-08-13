"""User auth — Supabase JWT (Bearer). Stateless, no network in request path once
JWKS is prewarmed.

  - LOCAL/DEV: HS256 with `SUPABASE_JWT_SECRET`.
  - PROD: JWKS (RS256/ES256) from `SUPABASE_URL` — the confirmed prod path (260813).

Hardening:
  - `algorithms` is PINNED per path (never read `alg` from the token header) — blocks
    `alg=none` and HS/RS confusion.
  - Every failure (bad sig / expired / bad aud / unknown alg / missing header) maps to
    ONE code UNAUTHORIZED — never distinguished, to deny an oracle.
  - `sub` is returned for the sidecar audit tag ONLY — never an authorization input.
"""

from __future__ import annotations

import jwt
from fastapi import Header

from src.auth.jwks_cache import get_signing_key
from src.auth.principal import Principal
from src.config.settings import settings
from src.core.errors import unauthorized
from src.core.logging import get_logger

logger = get_logger("auth")

_AUDIENCE = "authenticated"
_LEEWAY_SEC = 30
_HS_ALGS = ["HS256"]
_JWKS_ALGS = ["RS256", "ES256"]

_warned_no_verifier = False


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise unauthorized()
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise unauthorized()
    return parts[1].strip()


async def _decode(token: str) -> dict:
    if settings.supabase_jwt_secret:
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=_HS_ALGS,
            audience=_AUDIENCE,
            leeway=_LEEWAY_SEC,
            options={"require": ["exp", "aud"]},
        )
    if settings.supabase_url:
        signing_key = await get_signing_key(settings.supabase_url, token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=_JWKS_ALGS,
            audience=_AUDIENCE,
            leeway=_LEEWAY_SEC,
            options={"require": ["exp", "aud"]},
        )
    # Neither verifier configured -> fail-closed.
    global _warned_no_verifier
    if not _warned_no_verifier:
        logger.warning("no_jwt_verifier", extra={"data": {"effect": "user routes fail-closed"}})
        _warned_no_verifier = True
    raise unauthorized()


async def require_user_jwt(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> Principal:
    token = _bearer_token(authorization)
    try:
        claims = await _decode(token)
    except jwt.InvalidTokenError:
        raise unauthorized()
    sub = claims.get("sub")
    if not sub:
        raise unauthorized()
    return Principal("user", str(sub))
