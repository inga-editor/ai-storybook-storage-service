"""GET /files-signed — HMAC verify -> X-Accel-Redirect; 403 on bad sig / expired."""

from __future__ import annotations

import time

from src.config.settings import settings
from src.drivers import signing

BUCKET = "storybook-assets"
KEY = "exports/report.pdf"


def _url(exp, sig):
    return f"/files-signed/{BUCKET}/{KEY}?exp={exp}&sig={sig}"


def test_signed_get_ok_xaccel(client):
    exp = int(time.time()) + 3600
    sig = signing.sign(settings.storage_sign_secret, BUCKET, KEY, exp)
    r = client.get(_url(exp, sig), follow_redirects=False)
    assert r.status_code == 200
    headers = {k.lower() for k in r.headers}
    assert "x-accel-redirect" in headers
    assert r.headers["x-accel-redirect"] == f"/internal-files/{BUCKET}/{KEY}"
    assert r.headers["cache-control"] == "private, no-store"


def test_signed_get_bad_sig_403(client):
    exp = int(time.time()) + 3600
    r = client.get(_url(exp, "deadbeef"), follow_redirects=False)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN"


def test_signed_get_expired_403(client):
    past = int(time.time()) - 60
    sig = signing.sign(settings.storage_sign_secret, BUCKET, KEY, past)
    r = client.get(_url(past, sig), follow_redirects=False)
    assert r.status_code == 403


def test_signed_get_bad_grammar_400(client):
    exp = int(time.time()) + 3600
    sig = signing.sign(settings.storage_sign_secret, BUCKET, "noext", exp)
    r = client.get(f"/files-signed/{BUCKET}/noext?exp={exp}&sig={sig}", follow_redirects=False)
    assert r.status_code == 400
