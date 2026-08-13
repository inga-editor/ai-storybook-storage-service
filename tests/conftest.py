"""Pytest fixtures + env bootstrap.

CRITICAL: env is set at the TOP of this file, BEFORE any `src` import — `settings`
is a module-global constructed at import with cached_property caches, so the vars
must exist first (mirrors swap-service conftest)."""

import os
import tempfile

# --- env BEFORE src imports -------------------------------------------------
_ROOT = tempfile.mkdtemp(prefix="storage-test-root-")
os.environ.setdefault("STORAGE_PUBLIC_BASE_URL", "http://storage.test")
os.environ.setdefault("STORAGE_SIGN_SECRET", "test-sign-secret-0123456789abcdefXYZ")
os.environ.setdefault("STORAGE_ROOT", _ROOT)
os.environ.setdefault("STORAGE_API_KEYS", '{"image-api":"test-key","ops":"test-ops"}')
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-0123456789abcdefghij")
os.environ.setdefault("STORAGE_BUCKETS", "storybook-assets")
os.environ.setdefault("SUPABASE_URL", "")
# Pin write-policy envs to the CODE defaults — a developer's local `.env` (read by
# pydantic-settings) must not leak its tuned values into assertions.
os.environ.setdefault("STORAGE_SERVICE_ONLY_PREFIXES", "exports/")
os.environ.setdefault("STORAGE_USER_MIME_CAPS", '{"image/": 10485760, "audio/": 20971520, "video/": 52428800}')

import asyncio  # noqa: E402
import time  # noqa: E402

import jwt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from src.config.settings import settings  # noqa: E402
from src.drivers import paths  # noqa: E402
from src.drivers.local_fs import LocalFsBlobDriver  # noqa: E402
from src.drivers.registry import set_driver  # noqa: E402
from src.main import app  # noqa: E402
from tests.fakes.fake_blob_driver import FakeBlobDriver  # noqa: E402

TEST_API_KEY = "test-key"


@pytest.fixture
def client():
    # No `with` — lifespan is skipped so no real driver is built; tests inject one.
    return TestClient(app)


@pytest.fixture
def api_key() -> str:
    return TEST_API_KEY


@pytest.fixture
def user_jwt():
    def _mint(sub: str = "user-123", aud: str = "authenticated", ttl: int = 3600, alg: str = "HS256") -> str:
        now = int(time.time())
        claims = {"aud": aud, "sub": sub, "role": "authenticated", "iat": now, "exp": now + ttl}
        key = "" if alg == "none" else settings.supabase_jwt_secret
        return jwt.encode(claims, key, algorithm=alg)

    return _mint


@pytest.fixture
def fake_driver():
    fake = FakeBlobDriver()
    set_driver(fake)
    yield fake
    set_driver(None)


@pytest.fixture
def local_driver(tmp_path):
    # ensure_layout is async; run it synchronously here (no running loop yet).
    asyncio.run(paths.ensure_layout(str(tmp_path), ["storybook-assets"]))
    return LocalFsBlobDriver(
        root=str(tmp_path),
        sign_secret=settings.storage_sign_secret,
        public_base_url=settings.public_base_url,
    )
