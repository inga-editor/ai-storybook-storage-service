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
from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

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

# Security scheme (not a plain Header param): OpenAPI ignores header parameters
# named Authorization, so Swagger UI silently drops them — a scheme gets the
# Authorize button instead. auto_error=False keeps every failure on our single
# UNAUTHORIZED envelope (FastAPI's built-in error is a 403 with a different body).
bearer_scheme = HTTPBearer(auto_error=False)


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


async def authenticate_token(token: str) -> Principal:
    try:
        claims = await _decode(token)
    except jwt.InvalidTokenError:
        raise unauthorized()  # normal bad token — silent, no oracle
    except jwt.PyJWTError as exc:
        # Infra-side verify failure (JWKS fetch/parse, missing crypto backend…) —
        # still fail-closed on the single UNAUTHORIZED envelope, but LOG it: unlike
        # a bad token this needs ops attention, and without the log it would
        # masquerade as a client error.
        logger.warning("jwt_verify_infra_error", extra={"data": {"error": type(exc).__name__}})
        raise unauthorized()
    sub = claims.get("sub")
    if not sub:
        raise unauthorized()
    return Principal("user", str(sub))


async def require_user_jwt(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> Principal:
    # Scheme check is defensive — HTTPBearer already yields None for non-Bearer.
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials.strip():
        raise unauthorized()
    return await authenticate_token(credentials.credentials.strip())
