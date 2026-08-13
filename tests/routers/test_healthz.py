"""GET /healthz — liveness shape + driver Protocol conformance."""

from __future__ import annotations

from src.drivers.base import BlobDriver
from src.drivers.local_fs import LocalFsBlobDriver
from tests.fakes.fake_blob_driver import FakeBlobDriver


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "disk_free_bytes" in body
    assert "degraded" in body
    assert "driver" in body


def test_local_fs_is_blob_driver():
    d = LocalFsBlobDriver(root="/tmp/x", sign_secret="s", public_base_url="http://x")
    assert isinstance(d, BlobDriver)


def test_fake_is_blob_driver():
    assert isinstance(FakeBlobDriver(), BlobDriver)
