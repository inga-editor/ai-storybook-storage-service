"""HMAC signing for signed GET URLs (design 02 §4 / 04 §4).

    sig = HMAC-SHA256(STORAGE_SIGN_SECRET, "{bucket}/{key}:{exp}")

Verify checks `exp > now` AND a constant-time signature compare. Any failure
(tampered sig / expired) collapses to a single 403 at the HTTP layer — no oracle.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from secrets import compare_digest


def _message(bucket: str, key: str, exp: int) -> bytes:
    return f"{bucket}/{key}:{exp}".encode()


def sign(secret: str, bucket: str, key: str, exp: int) -> str:
    return hmac.new(secret.encode(), _message(bucket, key, exp), hashlib.sha256).hexdigest()


def verify(secret: str, bucket: str, key: str, exp: int, sig: str, *, now: int | None = None) -> bool:
    current = int(time.time()) if now is None else now
    if exp <= current:
        return False
    expected = sign(secret, bucket, key, exp)
    return compare_digest(expected, sig)
