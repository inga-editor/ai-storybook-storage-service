"""S2S api-key auth — constant-time match + fail-closed."""

from __future__ import annotations

import pytest

from src.auth import api_key
from src.auth.principal import Principal
from src.core.errors import ServiceError


async def test_valid_key():
    p = await api_key.require_api_key(x_api_key="test-key")
    assert isinstance(p, Principal)
    assert p.kind == "service"
    assert p.name == "image-api"


async def test_second_key_name():
    p = await api_key.require_api_key(x_api_key="test-ops")
    assert p.name == "ops"


async def test_wrong_key():
    with pytest.raises(ServiceError) as ei:
        await api_key.require_api_key(x_api_key="nope")
    assert ei.value.code == "UNAUTHORIZED"


async def test_missing_key():
    with pytest.raises(ServiceError) as ei:
        await api_key.require_api_key(x_api_key=None)
    assert ei.value.code == "UNAUTHORIZED"


async def test_fail_closed_empty_map(monkeypatch):
    from src.config.settings import settings

    # Override the cached_property value on the instance.
    monkeypatch.setitem(settings.__dict__, "api_keys", {})
    with pytest.raises(ServiceError) as ei:
        await api_key.require_api_key(x_api_key="test-key")
    assert ei.value.code == "UNAUTHORIZED"
