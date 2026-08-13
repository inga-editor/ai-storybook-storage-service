"""User JWT auth — HS256 verify, aud/exp, alg=none rejection."""

from __future__ import annotations

import time

import jwt
import pytest
from fastapi.security import HTTPAuthorizationCredentials

from src.auth import user_jwt
from src.auth.principal import Principal
from src.config.settings import settings
from src.core.errors import ServiceError

SECRET = settings.supabase_jwt_secret


def _mint(sub="u1", aud="authenticated", ttl=60, alg="HS256", key=None):
    now = int(time.time())
    claims = {"aud": aud, "sub": sub, "exp": now + ttl, "iat": now}
    return jwt.encode(claims, key if key is not None else ("" if alg == "none" else SECRET), algorithm=alg)


def _creds(token, scheme="Bearer"):
    return HTTPAuthorizationCredentials(scheme=scheme, credentials=token)


async def test_valid_hs256():
    p = await user_jwt.require_user_jwt(credentials=_creds(_mint()))
    assert isinstance(p, Principal)
    assert p.kind == "user"
    assert p.name == "u1"


async def test_missing_header():
    # HTTPBearer(auto_error=False) yields None for a missing/non-Bearer header.
    with pytest.raises(ServiceError) as ei:
        await user_jwt.require_user_jwt(credentials=None)
    assert ei.value.code == "UNAUTHORIZED"


async def test_bad_scheme():
    # Defensive: scheme is re-checked even though HTTPBearer filters non-Bearer.
    with pytest.raises(ServiceError) as ei:
        await user_jwt.require_user_jwt(credentials=_creds("abc", scheme="Token"))
    assert ei.value.code == "UNAUTHORIZED"


async def test_bad_signature():
    tok = _mint(key="a-completely-different-secret-value")
    with pytest.raises(ServiceError) as ei:
        await user_jwt.require_user_jwt(credentials=_creds(tok))
    assert ei.value.code == "UNAUTHORIZED"


async def test_expired():
    tok = _mint(ttl=-120)
    with pytest.raises(ServiceError) as ei:
        await user_jwt.require_user_jwt(credentials=_creds(tok))
    assert ei.value.code == "UNAUTHORIZED"


async def test_wrong_aud():
    tok = _mint(aud="anon")
    with pytest.raises(ServiceError) as ei:
        await user_jwt.require_user_jwt(credentials=_creds(tok))
    assert ei.value.code == "UNAUTHORIZED"


async def test_alg_none_rejected():
    tok = jwt.encode({"aud": "authenticated", "sub": "u1", "exp": int(time.time()) + 60}, "", algorithm="none")
    with pytest.raises(ServiceError) as ei:
        await user_jwt.require_user_jwt(credentials=_creds(tok))
    assert ei.value.code == "UNAUTHORIZED"


async def test_broken_token():
    with pytest.raises(ServiceError) as ei:
        await user_jwt.require_user_jwt(credentials=_creds("not.a.jwt"))
    assert ei.value.code == "UNAUTHORIZED"


async def test_jwks_infra_error_is_401_not_500(monkeypatch):
    # PyJWKClientError is a PyJWTError but NOT an InvalidTokenError — it must still
    # map to the UNAUTHORIZED envelope (live bug: ES256 without `cryptography`
    # escaped as a 500 traceback).
    async def _boom(token):
        raise jwt.exceptions.PyJWKClientError("jwks fetch failed")

    monkeypatch.setattr(user_jwt, "_decode", _boom)
    with pytest.raises(ServiceError) as ei:
        await user_jwt.require_user_jwt(credentials=_creds(_mint()))
    assert ei.value.code == "UNAUTHORIZED"
