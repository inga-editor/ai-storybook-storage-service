"""FE-writable prefix allowlist + media-class limits (design 04 §2)."""

from __future__ import annotations

import pytest

from src.core.errors import ServiceError
from src.validation import prefix_policy as pp


def test_resolve_longest_match_mixed_media():
    assert pp.resolve_fe_class("humans/id/uuid.png") == "image"
    assert pp.resolve_fe_class("stages/s1/sounds/clip.mp3") == "media"
    assert pp.resolve_fe_class("props/p1/variant/img.png") == "media"
    assert pp.resolve_fe_class("videos/a.mp4") == "video"
    assert pp.resolve_fe_class("auto-pics/a.webp") == "auto_pic"


def test_system_prefix_not_writable():
    assert pp.resolve_fe_class("ai-logs/x.png") is None
    with pytest.raises(ServiceError) as ei:
        pp.check_fe_writable("ai-logs/x.png")
    assert ei.value.code == "PREFIX_NOT_ALLOWED"


def test_check_fe_writable_returns_class():
    assert pp.check_fe_writable("humans/x/y.png") == "image"


def test_media_class_mime_reject():
    with pytest.raises(ServiceError) as ei:
        pp.check_media_class("image", "audio/mpeg", 100)
    assert ei.value.code == "UNSUPPORTED_MEDIA_TYPE"


def test_media_class_size_reject():
    with pytest.raises(ServiceError) as ei:
        pp.check_media_class("image", "image/png", 11 * 1024**2)
    assert ei.value.code == "PAYLOAD_TOO_LARGE"


def test_media_class_accepts_image_and_audio():
    pp.check_media_class("media", "image/png", 1000)
    pp.check_media_class("media", "audio/mpeg", 1000)


def test_missing_mime_is_415():
    with pytest.raises(ServiceError) as ei:
        pp.check_media_class("image", None, 100)
    assert ei.value.code == "UNSUPPORTED_MEDIA_TYPE"
