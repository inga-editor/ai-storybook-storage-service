"""HMAC signing round-trip + rejection cases."""

from __future__ import annotations

import time

from src.drivers import signing

SECRET = "unit-sign-secret"
BUCKET = "storybook-assets"
KEY = "exports/report.pdf"


def test_round_trip():
    exp = int(time.time()) + 3600
    sig = signing.sign(SECRET, BUCKET, KEY, exp)
    assert signing.verify(SECRET, BUCKET, KEY, exp, sig) is True


def test_wrong_sig():
    exp = int(time.time()) + 3600
    assert signing.verify(SECRET, BUCKET, KEY, exp, "deadbeef") is False


def test_expired():
    past = int(time.time()) - 10
    sig = signing.sign(SECRET, BUCKET, KEY, past)
    assert signing.verify(SECRET, BUCKET, KEY, past, sig) is False


def test_changed_key_fails():
    exp = int(time.time()) + 3600
    sig = signing.sign(SECRET, BUCKET, KEY, exp)
    assert signing.verify(SECRET, BUCKET, "exports/OTHER.pdf", exp, sig) is False


def test_changed_secret_fails():
    exp = int(time.time()) + 3600
    sig = signing.sign(SECRET, BUCKET, KEY, exp)
    assert signing.verify("other-secret", BUCKET, KEY, exp, sig) is False
