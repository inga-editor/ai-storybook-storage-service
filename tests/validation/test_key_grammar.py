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
