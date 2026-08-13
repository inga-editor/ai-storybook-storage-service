"""Shared helpers for storage write handlers — thin glue, no business logic."""

from __future__ import annotations

from typing import AsyncIterator
from urllib.parse import quote

from src.config.settings import settings
from src.core.errors import payload_too_large
from src.drivers.base import PutResult


def build_public_url(bucket: str, key: str) -> str:
    """Canonical persisted URL: {base}/files/{bucket}/{key} (key path-escaped)."""
    return f"{settings.public_base_url}/files/{bucket}/{key}"


def object_response(bucket: str, key: str, result: PutResult) -> dict:
    return {
        "success": True,
        "data": {
            "bucket": bucket,
            "key": key,
            "url": build_public_url(bucket, key),
            "etag": result["etag"],
            "bytes": result["bytes"],
            "deduped": result["deduped"],
        },
    }


async def counting_stream(source: AsyncIterator[bytes], cap: int) -> AsyncIterator[bytes]:
    """Wrap a byte stream with a hard byte counter. Aborts with 413 the moment the
    running total exceeds `cap` — the SECOND (mandatory) size gate after the
    Content-Length fast-fail. The driver's `put` unlinks its staging tmp file on
    ANY pre-rename raise (this 413 included), so an aborted oversized upload leaves
    nothing behind."""
    total = 0
    async for chunk in source:
        total += len(chunk)
        if total > cap:
            raise payload_too_large()
        yield chunk


# quote kept importable for callers that build internal redirect targets.
__all__ = ["build_public_url", "object_response", "counting_stream", "quote"]
