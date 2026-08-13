"""S2S per-prefix size caps (design 03 §2)."""

from __future__ import annotations

from src.config.settings import settings
from src.validation.size_caps import resolve_s2s_cap


def test_videos_cap_3gb():
    assert resolve_s2s_cap("videos/books/x/hd.mp4") == 3 * 1024**3


def test_default_cap():
    assert resolve_s2s_cap("ai-logs/x.png") == settings.storage_max_object_bytes
    assert resolve_s2s_cap("ai-logs/x.png") == 52428800
