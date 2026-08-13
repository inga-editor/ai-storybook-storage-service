"""In-memory BlobDriver for router tests — no disk. Records `.calls` for wiring
assertions; reproduces the driver's `deduped` + best-effort-delete semantics."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import AsyncIterator
from urllib.parse import quote

from src.drivers import signing
from src.drivers.base import ListPage, ObjectInfo, PutResult


async def _collect(data: bytes | AsyncIterator[bytes]) -> bytes:
    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    buf = bytearray()
    async for chunk in data:
        buf += chunk
    return bytes(buf)


class FakeBlobDriver:
    def __init__(self, sign_secret: str = "test-sign-secret-0123456789abcdefXYZ",
                 public_base_url: str = "http://storage.test") -> None:
        self._store: dict[tuple[str, str], tuple[bytes, str, dict]] = {}
        self._sign_secret = sign_secret
        self._public_base = public_base_url.rstrip("/")
        self.calls: list[tuple] = []

    async def put(self, bucket, key, data, *, content_type, if_none_match=None, metadata=None) -> PutResult:
        self.calls.append(("put", bucket, key, content_type, if_none_match, metadata))
        if if_none_match == "*" and (bucket, key) in self._store:
            existing, _ct, _md = self._store[(bucket, key)]
            return PutResult(etag=hashlib.sha256(existing).hexdigest(), bytes=len(existing), deduped=True)
        raw = await _collect(data)
        self._store[(bucket, key)] = (raw, content_type, metadata or {})
        return PutResult(etag=hashlib.sha256(raw).hexdigest(), bytes=len(raw), deduped=False)

    async def get(self, bucket, key) -> AsyncIterator[bytes] | None:
        if (bucket, key) not in self._store:
            return None

        async def _gen():
            yield self._store[(bucket, key)][0]

        return _gen()

    async def head(self, bucket, key) -> ObjectInfo | None:
        entry = self._store.get((bucket, key))
        if entry is None:
            return None
        raw, ct, md = entry
        return ObjectInfo(
            key=key,
            bytes=len(raw),
            content_type=ct,
            etag=hashlib.sha256(raw).hexdigest(),
            modified_at=datetime.now(timezone.utc).isoformat(),
            metadata=md,
        )

    async def delete(self, bucket, key) -> bool:
        self.calls.append(("delete", bucket, key))
        return self._store.pop((bucket, key), None) is not None

    async def list(self, bucket, prefix, *, cursor=None, limit=1000) -> ListPage:
        keys = sorted(k for (b, k) in self._store if b == bucket and k.startswith(prefix))
        if cursor:
            keys = [k for k in keys if k > cursor]
        page = keys[:limit]
        objects = [await self.head(bucket, k) for k in page]
        next_cursor = page[-1] if len(keys) > limit and page else None
        return ListPage(objects=[o for o in objects if o], next_cursor=next_cursor)

    def presign_get(self, bucket, key, *, ttl_sec) -> str:
        import time

        exp = int(time.time()) + ttl_sec
        sig = signing.sign(self._sign_secret, bucket, key, exp)
        return f"{self._public_base}/files-signed/{bucket}/{quote(key)}?exp={exp}&sig={sig}"

    def presign_put(self, bucket, key, *, ttl_sec) -> str:
        raise NotImplementedError
