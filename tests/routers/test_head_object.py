"""HEAD /api/storage/objects — headers-only metadata; 404 on missing."""

from __future__ import annotations

BUCKET = "storybook-assets"


def _put(client, key, body=b"pixels"):
    return client.put(
        f"/api/storage/objects/{BUCKET}/{key}",
        headers={"X-API-Key": "test-key", "Content-Type": "image/png"},
        content=body,
    )


def test_head_existing_headers_only(client, fake_driver):
    _put(client, "ai-logs/h.png")
    r = client.head(f"/api/storage/objects/{BUCKET}/ai-logs/h.png", headers={"X-API-Key": "test-key"})
    assert r.status_code == 200
    lower = {k.lower() for k in r.headers}
    assert "etag" in lower
    assert "content-length" in lower
    assert r.headers["content-type"] == "image/png"
    assert r.content == b""  # headers-only, no body


def test_head_missing_404(client, fake_driver):
    r = client.head(f"/api/storage/objects/{BUCKET}/ai-logs/none.png", headers={"X-API-Key": "test-key"})
    assert r.status_code == 404


def test_head_no_auth_401(client, fake_driver):
    r = client.head(f"/api/storage/objects/{BUCKET}/ai-logs/x.png")
    assert r.status_code == 401
