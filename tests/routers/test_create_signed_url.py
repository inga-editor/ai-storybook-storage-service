"""POST /api/storage/sign — signed URL + expires_in cap."""

from __future__ import annotations

BUCKET = "storybook-assets"


def test_sign_200(client, fake_driver):
    r = client.post(
        "/api/storage/sign",
        headers={"X-API-Key": "test-key"},
        json={"bucket": BUCKET, "key": "exports/a.pdf", "expires_in": 60},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert "/files-signed/" in data["signed_url"]
    assert "expires_at" in data


def test_sign_expires_in_too_large_400(client, fake_driver):
    r = client.post(
        "/api/storage/sign",
        headers={"X-API-Key": "test-key"},
        json={"bucket": BUCKET, "key": "exports/a.pdf", "expires_in": 99999999},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_sign_expires_in_zero_400(client, fake_driver):
    r = client.post(
        "/api/storage/sign",
        headers={"X-API-Key": "test-key"},
        json={"bucket": BUCKET, "key": "exports/a.pdf", "expires_in": 0},
    )
    assert r.status_code == 400


def test_sign_no_auth_401(client, fake_driver):
    r = client.post("/api/storage/sign", json={"bucket": BUCKET, "key": "exports/a.pdf"})
    assert r.status_code == 401


def test_sign_sibling_rendition_key_s2s_accepted(client, fake_driver):
    # ADR-057: S2S may sign a sibling rendition key `{key}@{tier}.{rext}`.
    r = client.post(
        "/api/storage/sign",
        headers={"X-API-Key": "test-key"},
        json={"bucket": BUCKET, "key": "exports/a.pdf@web.pdf", "expires_in": 60},
    )
    assert r.status_code == 200
