"""POST /api/storage/uploads — multipart browser upload."""

from __future__ import annotations


def _post(client, tok, key, *, filename="a.png", content=b"img", mime="image/png"):
    return client.post(
        "/api/storage/uploads",
        headers={"Authorization": f"Bearer {tok}"},
        files={"file": (filename, content, mime)},
        data={"key": key},
    )


def test_upload_happy_201(client, fake_driver, user_jwt):
    r = _post(client, user_jwt(), "humans/abc/uuid.png")
    assert r.status_code == 201
    assert "/files/storybook-assets/" in r.json()["data"]["url"]


def test_upload_system_prefix_403(client, fake_driver, user_jwt):
    r = _post(client, user_jwt(), "ai-logs/x.png")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "PREFIX_NOT_ALLOWED"


def test_upload_mime_415(client, fake_driver, user_jwt):
    r = _post(client, user_jwt(), "humans/abc/x.mp3", filename="a.mp3", content=b"aud", mime="audio/mpeg")
    assert r.status_code == 415
    assert r.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_upload_media_mixed_audio_ok(client, fake_driver, user_jwt):
    # audio into a stages/ (media class) folder is allowed
    r = _post(client, user_jwt(), "stages/s1/sounds/clip.mp3", filename="c.mp3", content=b"aud", mime="audio/mpeg")
    assert r.status_code == 201


def test_upload_no_auth_401(client, fake_driver):
    r = client.post(
        "/api/storage/uploads",
        files={"file": ("a.png", b"img", "image/png")},
        data={"key": "humans/abc/x.png"},
    )
    assert r.status_code == 401


def test_upload_uploader_tag(client, fake_driver, user_jwt):
    _post(client, user_jwt(sub="user-xyz"), "humans/abc/uuid.png")
    put_call = next(c for c in fake_driver.calls if c[0] == "put")
    assert put_call[5]["uploader"] == "user:user-xyz"
