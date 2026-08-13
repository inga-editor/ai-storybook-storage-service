"""S2S auth — `X-API-Key` matched constant-time against `STORAGE_API_KEYS` (name->key).

Fail-closed: empty map OR missing header -> 401. Compare EVERY configured entry with
`compare_digest` (no early `in dict.values()` exit) so lookup time does not leak which
key matched. Route S2S surface is loopback-only (auth 04 §1), so this is defense in
depth, not the sole barrier.
"""

from __future__ import annotations

from secrets import compare_digest

from fastapi import Header

from src.auth.principal import Principal
from src.config.settings import settings
from src.core.errors import unauthorized
from src.core.logging import get_logger

logger = get_logger("auth")
_warned_empty = False


def _match_key_name(supplied: str) -> str | None:
    """Return the key NAME whose value matches, comparing all entries constant-time."""
    matched: str | None = None
    supplied_b = supplied.encode()
    for name, value in settings.api_keys.items():
        if compare_digest(supplied_b, value.encode()):
            matched = name  # do not break — keep timing uniform across the map
    return matched


async def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> Principal:
    global _warned_empty
    if not settings.api_keys:
        if not _warned_empty:
            logger.warning("api_keys_empty", extra={"data": {"effect": "S2S fail-closed"}})
            _warned_empty = True
        raise unauthorized()
    if x_api_key is None:
        raise unauthorized()
    name = _match_key_name(x_api_key)
    if name is None:
        raise unauthorized()
    return Principal("service", name)
