"""Key + bucket grammar (design 04 §3)."""

from __future__ import annotations

import pytest

from src.core.errors import ServiceError
from src.validation import key_grammar

BUCKET = "storybook-assets"

BAD_KEYS = [
    "a/../b.png",       # traversal
    "a//b.png",         # empty segment
    "/a.png",           # leading slash
    "a\\b.png",         # backslash
    "a%2e.png",         # percent-encoded
    "a\x01b.png",       # control char
    "noext",            # missing extension
    "trailingdot.",     # empty extension
    "a/" + "x" * 300 + ".png",   # segment > 255
    "x" * 1100 + ".png",         # key > 1024
    ".",                # dot segment
    "..",               # dotdot only
]

VALID_KEYS = [
    "ai-logs/3fa8c2.png",
    "humans/id-1/uuid_v4.png",
    "videos/books/abc/hd/file.mp4",
    "a.b.c.png",
]


@pytest.mark.parametrize("key", BAD_KEYS)
def test_invalid_keys(key):
    with pytest.raises(ServiceError) as ei:
        key_grammar.validate_key(key)
    assert ei.value.code == "VALIDATION_ERROR"


@pytest.mark.parametrize("key", VALID_KEYS)
def test_valid_keys(key):
    key_grammar.validate_key(key)  # no raise


def test_bad_bucket_charset():
    with pytest.raises(ServiceError) as ei:
        key_grammar.validate_bucket("Bad_Bucket")
    assert ei.value.code == "VALIDATION_ERROR"


def test_unknown_bucket():
    with pytest.raises(ServiceError) as ei:
        key_grammar.validate_bucket("some-other-bucket")
    assert ei.value.code == "VALIDATION_ERROR"


def test_known_bucket_ok():
    key_grammar.validate_bucket(BUCKET)  # in STORAGE_BUCKETS


def test_full_validate():
    key_grammar.validate(BUCKET, "humans/x/y.png")
    with pytest.raises(ServiceError):
        key_grammar.validate("wrong", "humans/x/y.png")


# --- @ grammar (ADR-057, S2S-only sibling rendition key) --------------------


def test_at_rejected_by_default():
    with pytest.raises(ServiceError) as ei:
        key_grammar.validate_key("uploads/images/a.png@web.webp")
    assert ei.value.code == "VALIDATION_ERROR"


def test_at_accepted_when_allow_at():
    key_grammar.validate_key("uploads/images/a.png@web.webp", allow_at=True)  # no raise


def test_at_extension_resolves_to_rendition_ext():
    # "abc.png@web.webp" -> last segment's extension is "webp", not "png".
    key_grammar.validate_key("abc.png@web.webp", allow_at=True)


def test_multi_at_in_segment_valid():
    # Charset-based rule — no reason to special-case a second "@".
    key_grammar.validate_key("abc.png@web@extra.webp", allow_at=True)


def test_at_still_rejects_other_violations():
    with pytest.raises(ServiceError):
        key_grammar.validate_key("a/../b.png@web.webp", allow_at=True)  # traversal
    with pytest.raises(ServiceError):
        key_grammar.validate_key("noext@web", allow_at=True)  # missing extension


def test_full_validate_allow_at_forwarded():
    key_grammar.validate(BUCKET, "uploads/images/a.png@web.webp", allow_at=True)
    with pytest.raises(ServiceError):
        key_grammar.validate(BUCKET, "uploads/images/a.png@web.webp")  # default False
