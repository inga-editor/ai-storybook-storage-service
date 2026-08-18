"""DELETE /api/storage/objects — best-effort 200, 2-mode auth."""

from __future__ import annotations

BUCKET = "storybook-assets"


def _put(client, key):
    return client.put(
        f"/api/storage/objects/{BUCKET}/{key}",
        headers={"X-API-Key": "test-key", "Content-Type": "image/png"},
        content=b"data",
    )


def test_delete_twice_always_200(client, fake_driver):
    _put(client, "ai-logs/d.png")
    r1 = client.delete(f"/api/storage/objects/{BUCKET}/ai-logs/d.png", headers={"X-API-Key": "test-key"})
    assert r1.status_code == 200 and r1.json()["data"]["deleted"] is True
    r2 = client.delete(f"/api/storage/objects/{BUCKET}/ai-logs/d.png", headers={"X-API-Key": "test-key"})
    assert r2.status_code == 200 and r2.json()["data"]["deleted"] is False


def test_delete_user_mode_service_only_prefix_403(client, fake_driver, user_jwt):
    tok = user_jwt()
    r = client.delete(
        f"/api/storage/objects/{BUCKET}/exports/x.pdf",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "PREFIX_NOT_ALLOWED"


def test_delete_user_mode_any_other_prefix_200(client, fake_driver, user_jwt):
    tok = user_jwt()
    for key in ("humans/id/x.png", "ai-logs/x.png"):  # denylist: only service-only blocked
        r = client.delete(
            f"/api/storage/objects/{BUCKET}/{key}",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 200


def test_delete_no_auth_401(client, fake_driver):
    r = client.delete(f"/api/storage/objects/{BUCKET}/ai-logs/x.png")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


def test_delete_sibling_rendition_key_service_accepted(client, fake_driver):
    # ADR-057: S2S principal may delete a sibling rendition key.
    key = "ai-logs/d.png@web.webp"
    _put(client, key)
    r = client.delete(f"/api/storage/objects/{BUCKET}/{key}", headers={"X-API-Key": "test-key"})
    assert r.status_code == 200
    assert r.json()["data"]["deleted"] is True


def test_delete_sibling_rendition_key_user_rejected_400(client, fake_driver, user_jwt):
    # ADR-057: user JWT principal must NOT be able to delete/craft a sibling key.
    tok = user_jwt()
    r = client.delete(
        f"/api/storage/objects/{BUCKET}/ai-logs/d.png@web.webp",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
