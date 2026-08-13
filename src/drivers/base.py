"""BlobDriver Protocol + result types (design 02 §1).

A CLOSED surface of 6 verbs mirroring S3 core semantics — extension is additive
only. The driver knows NOTHING about HTTP (no FastAPI imports): key validation +
auth + error->status mapping all live above it. Swapping infra later = a new driver
+ `STORAGE_DRIVER` env; HTTP API and clients do not change.
"""

from __future__ import annotations

from typing import AsyncIterator, Protocol, TypedDict, runtime_checkable


class PutResult(TypedDict):
    etag: str          # opaque to client (local-fs: sha256 hex)
    bytes: int
    deduped: bool      # True when if_none_match="*" met an existing key (409-benign)


class ObjectInfo(TypedDict):
    key: str
    bytes: int
    content_type: str
    etag: str
    modified_at: str   # ISO-8601 UTC
    metadata: dict[str, str]


class ListPage(TypedDict):
    objects: list[ObjectInfo]
    next_cursor: str | None


@runtime_checkable
class BlobDriver(Protocol):
    async def put(
        self,
        bucket: str,
        key: str,
        data: bytes | AsyncIterator[bytes],
        *,
        content_type: str,
        if_none_match: str | None = None,   # "*" = fail-if-exists (dedup) -> deduped=True, NO raise
        metadata: dict[str, str] | None = None,
    ) -> PutResult: ...

    async def get(self, bucket: str, key: str) -> AsyncIterator[bytes] | None: ...

    async def head(self, bucket: str, key: str) -> ObjectInfo | None: ...

    async def delete(self, bucket: str, key: str) -> bool: ...   # False = not found (best-effort)

    async def list(
        self, bucket: str, prefix: str, *, cursor: str | None = None, limit: int = 1000
    ) -> ListPage: ...

    def presign_get(self, bucket: str, key: str, *, ttl_sec: int) -> str: ...

    def presign_put(self, bucket: str, key: str, *, ttl_sec: int) -> str: ...   # declared, v1 unused
