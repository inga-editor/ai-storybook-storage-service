"""Two-mode auth for DELETE (design 03 §4):
  - valid X-API-Key  -> service principal (may delete any key)
  - else valid Bearer -> user principal (route enforces FE-writable allowlist)
  - neither           -> 401

Bearer goes through the shared HTTPBearer security scheme (see user_jwt.py) so
Swagger UI's Authorize button covers this route too.
"""

from __future__ import annotations

from fastapi import Header, Security
from fastapi.security import HTTPAuthorizationCredentials

from src.auth.api_key import _match_key_name
from src.auth.principal import Principal
from src.auth.user_jwt import authenticate_token, bearer_scheme
from src.config.settings import settings
from src.core.errors import unauthorized


async def require_api_key_or_user_jwt(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> Principal:
    if x_api_key is not None and settings.api_keys:
        name = _match_key_name(x_api_key)
        if name is not None:
            return Principal("service", name)
    if credentials is not None and credentials.scheme.lower() == "bearer" and credentials.credentials.strip():
        return await authenticate_token(credentials.credentials.strip())
    raise unauthorized()
