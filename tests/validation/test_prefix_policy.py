"""Service-only prefix denylist + mime-cap map (design 04 §2, REV 260813)."""

from __future__ import annotations

import pytest

from src.config.settings import settings
from src.core.errors import ServiceError
from src.validation import prefix_policy as pp


def test_any_prefix_writable_by_default():
    # Denylist model: unknown/new prefixes are user-writable without a code change.
    pp.check_user_writable("uploads/a.png")
    pp.check_user_writable("humans/id/uuid.png")
    pp.check_user_writable("brand-new-feature/x.webp")
    pp.check_user_writable("ai-logs/x.png")  # not service-only by DEFAULT env


def test_service_only_prefix_403():
    with pytest.raises(ServiceError) as ei:
        pp.check_user_writable("exports/book.pdf")
    assert ei.value.code == "PREFIX_NOT_ALLOWED"


def test_service_only_prefixes_env_extendable(monkeypatch):
    monkeypatch.setitem(settings.__dict__, "service_only_prefixes", ["exports/", "ai-logs/"])
    with pytest.raises(ServiceError) as ei:
        pp.check_user_writable("ai-logs/x.png")
    assert ei.value.code == "PREFIX_NOT_ALLOWED"
    pp.check_user_writable("uploads/x.png")


def test_resolve_user_cap_defaults():
    assert pp.resolve_user_cap("image/png") == 10 * 1024**2
    assert pp.resolve_user_cap("audio/mpeg") == 20 * 1024**2
    assert pp.resolve_user_cap("video/mp4; codecs=avc1") == 50 * 1024**2


def test_unlisted_mime_415():
    for mime in ("application/pdf", "text/html", "image", None, ""):
        with pytest.raises(ServiceError) as ei:
            pp.resolve_user_cap(mime)
        assert ei.value.code == "UNSUPPORTED_MEDIA_TYPE"


def test_longest_mime_prefix_wins(monkeypatch):
    monkeypatch.setitem(settings.__dict__, "user_mime_caps", {"image/": 100, "image/webp": 999})
    assert pp.resolve_user_cap("image/webp") == 999
    assert pp.resolve_user_cap("image/png") == 100


def test_check_user_upload_size_413():
    with pytest.raises(ServiceError) as ei:
        pp.check_user_upload("uploads/a.png", "image/png", 11 * 1024**2)
    assert ei.value.code == "PAYLOAD_TOO_LARGE"


def test_check_user_upload_returns_cap():
    assert pp.check_user_upload("uploads/a.png", "image/png", 100) == 10 * 1024**2
