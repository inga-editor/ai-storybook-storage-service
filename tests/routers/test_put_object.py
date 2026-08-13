"""PUT /api/storage/objects — 201/409/200 table, auth, grammar, Content-Type."""

from __future__ import annotations

BUCKET = "storybook-assets"


def _put(client, key, *, upsert=None, key_hdr="test-key", ct="image/png", body=b"data"):
    url = f"/api/storage/objects/{BUCKET}/{key}"
    if upsert is not None:
        url += f"?upsert={'true' if upsert else 'false'}"
    headers = {"Content-Type": ct}
    if key_hdr:
        headers["X-API-Key"] = key_hdr
    return client.put(url, headers=headers, content=body)


def test_put_new_201(client, fake_driver):
    r = _put(client, "ai-logs/new.png")
    assert r.status_code == 201
    data = r.json()["data"]
    assert data["bucket"] == BUCKET
    assert data["key"] == "ai-logs/new.png"
    assert data["url"] == "http://storage.test/files/storybook-assets/ai-logs/new.png"
    assert data["deduped"] is False


def test_put_upsert_false_existing_409(client, fake_driver):
    _put(client, "ai-logs/dup.png")
    r = _put(client, "ai-logs/dup.png", upsert=False)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ALREADY_EXISTS"


def test_put_upsert_true_200(client, fake_driver):
    _put(client, "ai-logs/ups.png")
    r = _put(client, "ai-logs/ups.png", upsert=True)
    assert r.status_code == 200
    assert r.json()["data"]["deduped"] is False


def test_missing_content_type_400(client, fake_driver):
    r = client.put(
        f"/api/storage/objects/{BUCKET}/ai-logs/x.png",
        headers={"X-API-Key": "test-key"},
        content=b"data",
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_missing_api_key_401(client, fake_driver):
    r = _put(client, "ai-logs/x.png", key_hdr=None)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


def test_multi_segment_key(client, fake_driver):
    r = _put(client, "humans/id-1/uuid.png")
    assert r.status_code == 201
    assert r.json()["data"]["key"] == "humans/id-1/uuid.png"


def test_uploader_metadata_wired(client, fake_driver):
    _put(client, "ai-logs/meta.png")
    put_call = next(c for c in fake_driver.calls if c[0] == "put")
    metadata = put_call[5]
    assert metadata["uploader"] == "svc:image-api"
