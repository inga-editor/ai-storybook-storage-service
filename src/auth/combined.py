"""Two-mode auth for DELETE (design 03 §4):
  - valid X-API-Key  -> service principal (may delete any key)
  - else valid Bearer -> user principal (route enforces FE-writable allowlist)
  - neither           -> 401
"""

from __future__ import annotations

from fastapi import Header

from src.auth.api_key import _match_key_name
from src.auth.principal import Principal
from src.auth.user_jwt import _bearer_token, _decode
from src.config.settings import settings
from src.core.errors import unauthorized

import jwt


async def require_api_key_or_user_jwt(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> Principal:
    if x_api_key is not None and settings.api_keys:
        name = _match_key_name(x_api_key)
        if name is not None:
            return Principal("service", name)
    if authorization:
        try:
            claims = await _decode(_bearer_token(authorization))
        except jwt.InvalidTokenError:
            raise unauthorized()
        sub = claims.get("sub")
        if sub:
            return Principal("user", str(sub))
    raise unauthorized()
