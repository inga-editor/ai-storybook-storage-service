"""JWKS cache for prod user-JWT verify (RS256/ES256 — confirmed prod path, 260813).

`PyJWKClient(cache_keys=True)` caches keys by `kid` in-process; an unknown `kid`
triggers a single refetch of the JWK set. `prewarm_jwks` (called at lifespan when
`SUPABASE_URL` is set) does the initial fetch so the FIRST real request never pays
network latency. Once prewarmed, a token whose `kid` is already cached costs no
network call.

v1 limitation (tracked): a flood of tokens carrying random unknown `kid`s could
still provoke repeated refetches. Acceptable for v1 — the user-JWT surface reaches
this service only via the nginx proxy from the editor FE (not open S2S); revisit
with a refetch throttle if abuse is observed.
"""

from __future__ import annotations

import asyncio

from jwt import PyJWKClient

from src.core.logging import get_logger

logger = get_logger("auth")

_JWKS_PATH = "/auth/v1/.well-known/jwks.json"

_client: PyJWKClient | None = None
_client_url: str = ""


def _jwks_uri(supabase_url: str) -> str:
    return supabase_url.rstrip("/") + _JWKS_PATH


def _get_client(supabase_url: str) -> PyJWKClient:
    global _client, _client_url
    if _client is None or _client_url != supabase_url:
        _client = PyJWKClient(_jwks_uri(supabase_url), cache_keys=True)
        _client_url = supabase_url
    return _client


async def prewarm_jwks(supabase_url: str) -> None:
    """Best-effort initial fetch at boot. A failure logs and returns — must not
    block startup (the first request will retry)."""
    try:
        client = _get_client(supabase_url)
        await asyncio.to_thread(client.get_jwk_set)
        logger.info("jwks_prewarmed", extra={"data": {"uri": _jwks_uri(supabase_url)}})
    except Exception as exc:  # noqa: BLE001 — boot must survive a JWKS outage
        logger.warning("jwks_prewarm_failed", extra={"data": {"error": str(exc)}})


async def get_signing_key(supabase_url: str, token: str):
    """Return the signing key for `token` (from the kid-cache; refetch only on a
    kid miss). Wrapped in `to_thread` — PyJWKClient does blocking I/O on a miss."""
    client = _get_client(supabase_url)
    return await asyncio.to_thread(client.get_signing_key_from_jwt, token)


def _reset_for_tests() -> None:
    global _client, _client_url
    _client = None
    _client_url = ""
