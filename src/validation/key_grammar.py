"""Key + bucket grammar (design 04 §3). Pure functions — REJECT only, never rewrite
(client builders already sanitized). Raises `validation_error` (400) with a
client-safe message that names the rule, never echoing the full key into logs.

Rules:
  charset per segment : [A-Za-z0-9._-]  (S2S mode adds "@" — sibling rendition
                         key `{key}@{tier}.{rext}`, ADR-057 REV 260818. User JWT
                         mode keeps rejecting "@" — see design 04 §3.)
  forbidden           : "..", empty segment ("//"), leading "/", "\\", control chars, "%"
  length              : key <= 1024, each segment <= 255
  extension           : required (nginx resolves Content-Type by extension)
  bucket              : [a-z0-9-]{3,63} AND in STORAGE_BUCKETS
"""

from __future__ import annotations

import re

from src.config.settings import settings
from src.core.errors import validation_error

_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_SEGMENT_AT_RE = re.compile(r"^[A-Za-z0-9._@-]+$")
_BUCKET_RE = re.compile(r"^[a-z0-9-]{3,63}$")
MAX_KEY_LEN = 1024
MAX_SEGMENT_LEN = 255


def validate_bucket(bucket: str) -> None:
    if not _BUCKET_RE.match(bucket):
        raise validation_error("Invalid bucket name")
    if bucket not in settings.buckets:
        raise validation_error("Unknown bucket")


def validate_key(key: str, *, allow_at: bool = False) -> None:
    """`allow_at=True` (S2S write paths only) permits `@` in segment charset —
    sibling rendition key `{key}@{tier}.{rext}` (design 04 §3, ADR-057). User JWT
    paths must call with the default `allow_at=False`.
    """
    if not key or len(key) > MAX_KEY_LEN:
        raise validation_error("Key length out of range")
    if key.startswith("/"):
        raise validation_error("Key must not start with '/'")
    if "\\" in key:
        raise validation_error("Backslash not allowed in key")
    if "%" in key:
        raise validation_error("Percent-encoding not allowed in key")
    if any(ord(c) < 0x20 for c in key):
        raise validation_error("Control characters not allowed in key")

    segment_re = _SEGMENT_AT_RE if allow_at else _SEGMENT_RE
    segments = key.split("/")
    for seg in segments:
        if seg == "" or seg == "." or seg == "..":
            raise validation_error("Empty or dot segment not allowed in key")
        if len(seg) > MAX_SEGMENT_LEN:
            raise validation_error("Key segment too long")
        if not segment_re.match(seg):
            raise validation_error("Illegal character in key segment")

    last = segments[-1]
    if "." not in last or last.rsplit(".", 1)[1] == "":
        raise validation_error("Key must have a file extension")


def validate(bucket: str, key: str, *, allow_at: bool = False) -> None:
    """Full check used by every write/read handler."""
    validate_bucket(bucket)
    validate_key(key, allow_at=allow_at)
