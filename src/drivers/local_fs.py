"""Local filesystem BlobDriver (v1).

Guarantees:
- Streaming write: never holds more than one chunk (1MB) in RAM — required for
  video finals (500MB–2GB). sha256 computed in the SAME pass (no second read).
- Atomic: bytes land in `.tmp/{uuid}` then `os.rename` into place — nginx never
  reads a partial file.
- Best-effort delete, sidecar metadata, HMAC presign. FastAPI-free (design 02 §1).
"""

from __future__ import annotations

import asyncio
import errno
import hashlib
import json
import mimetypes
import os
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator
from urllib.parse import quote

from src.drivers import paths, signing
from src.drivers.base import ListPage, ObjectInfo, PutResult
from src.drivers.errors import InsufficientStorageError, StorageIoError

CHUNK_SIZE = 1024 * 1024
_ETAG_FALLBACK_MAX_BYTES = 100 * 1024 * 1024  # recompute sha256 in head() only below this


async def _as_aiter(data: bytes | AsyncIterator[bytes]) -> AsyncIterator[bytes]:
    """Normalize bytes | AsyncIterator into ONE code path (DRY)."""
    if isinstance(data, (bytes, bytearray)):
        if data:
            yield bytes(data)
        return
    async for chunk in data:
        if chunk:
            yield chunk


class LocalFsBlobDriver:
    def __init__(self, root: str, *, sign_secret: str, public_base_url: str) -> None:
        self._root = root
        self._sign_secret = sign_secret
        self._public_base = public_base_url.rstrip("/")

    # -- write ---------------------------------------------------------------
    async def put(
        self,
        bucket: str,
        key: str,
        data: bytes | AsyncIterator[bytes],
        *,
        content_type: str,
        if_none_match: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> PutResult:
        dest = paths.object_path(self._root, bucket, key)

        if if_none_match == "*" and await asyncio.to_thread(os.path.exists, dest):
            info = await self.head(bucket, key)
            etag = info["etag"] if info else ""
            size = info["bytes"] if info else 0
            return PutResult(etag=etag, bytes=size, deduped=True)

        tmp = paths.new_tmp_path(self._root)
        hasher = hashlib.sha256()
        total = 0
        renamed = False
        try:
            fh = await asyncio.to_thread(open, tmp, "wb")
            try:
                async for chunk in _as_aiter(data):
                    hasher.update(chunk)
                    total += len(chunk)
                    await asyncio.to_thread(fh.write, chunk)
                await asyncio.to_thread(fh.flush)
                await asyncio.to_thread(os.fsync, fh.fileno())
            finally:
                await asyncio.to_thread(fh.close)

            await asyncio.to_thread(os.makedirs, os.path.dirname(dest), exist_ok=True)
            await asyncio.to_thread(os.rename, tmp, dest)
            renamed = True
        except OSError as exc:
            if exc.errno == errno.ENOSPC:
                raise InsufficientStorageError(str(exc)) from exc
            raise StorageIoError(str(exc)) from exc
        finally:
            # Cleanup the staging file on ANY pre-rename failure — OSError, a
            # payload_too_large() ServiceError from the counting stream, or a
            # ClientDisconnect. Without this the tmp file leaks -> disk-fill DoS.
            if not renamed:
                await self._safe_unlink(tmp)

        etag = hasher.hexdigest()
        await self._write_sidecar(bucket, key, content_type, etag, total, metadata or {})
        return PutResult(etag=etag, bytes=total, deduped=False)

    async def _write_sidecar(
        self, bucket: str, key: str, content_type: str, etag: str, size: int, metadata: dict[str, str]
    ) -> None:
        """Best-effort: sidecar loss never blocks serve (head falls back to stat)."""
        record = {
            "content_type": content_type,
            "etag": etag,
            "bytes": size,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "uploader": metadata.get("uploader", ""),
            "metadata": metadata,
        }
        try:
            mp = paths.meta_path(self._root, bucket, key)
            await asyncio.to_thread(os.makedirs, os.path.dirname(mp), exist_ok=True)
            await asyncio.to_thread(_atomic_write_text, mp, json.dumps(record))
        except OSError:
            pass  # audit-only; do not fail the request

    # -- read ----------------------------------------------------------------
    async def get(self, bucket: str, key: str) -> AsyncIterator[bytes] | None:
        dest = paths.object_path(self._root, bucket, key)
        if not await asyncio.to_thread(os.path.isfile, dest):
            return None
        return self._stream_file(dest)

    async def _stream_file(self, path: str) -> AsyncIterator[bytes]:
        fh = await asyncio.to_thread(open, path, "rb")
        try:
            while True:
                chunk = await asyncio.to_thread(fh.read, CHUNK_SIZE)
                if not chunk:
                    break
                yield chunk
        finally:
            await asyncio.to_thread(fh.close)

    async def head(self, bucket: str, key: str) -> ObjectInfo | None:
        dest = paths.object_path(self._root, bucket, key)
        stat = await asyncio.to_thread(_safe_stat, dest)
        if stat is None:
            return None
        modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        sidecar = await self._read_sidecar(bucket, key)
        if sidecar:
            return ObjectInfo(
                key=key,
                bytes=int(sidecar.get("bytes", stat.st_size)),
                content_type=sidecar.get("content_type") or _guess_mime(key),
                etag=sidecar.get("etag", ""),
                modified_at=modified,
                metadata=sidecar.get("metadata", {}) or {},
            )
        # Fallback: sidecar lost — stat + mime-by-extension; recompute etag only if small.
        etag = await self._etag_from_file(dest, stat.st_size)
        return ObjectInfo(
            key=key,
            bytes=stat.st_size,
            content_type=_guess_mime(key),
            etag=etag,
            modified_at=modified,
            metadata={},
        )

    async def _read_sidecar(self, bucket: str, key: str) -> dict | None:
        try:
            mp = paths.meta_path(self._root, bucket, key)
            raw = await asyncio.to_thread(_safe_read_text, mp)
            return json.loads(raw) if raw is not None else None
        except (OSError, json.JSONDecodeError):
            return None

    async def _etag_from_file(self, path: str, size: int) -> str:
        if size > _ETAG_FALLBACK_MAX_BYTES:
            return ""

        def _compute() -> str:
            h = hashlib.sha256()
            with open(path, "rb") as fh:
                for chunk in iter(lambda: fh.read(CHUNK_SIZE), b""):
                    h.update(chunk)
            return h.hexdigest()

        try:
            return await asyncio.to_thread(_compute)
        except OSError:
            return ""

    # -- delete --------------------------------------------------------------
    async def delete(self, bucket: str, key: str) -> bool:
        dest = paths.object_path(self._root, bucket, key)
        existed = await self._safe_unlink(dest)
        await self._safe_unlink(paths.meta_path(self._root, bucket, key))
        return existed

    async def _safe_unlink(self, path: str) -> bool:
        def _rm() -> bool:
            try:
                os.remove(path)
                return True
            except FileNotFoundError:
                return False
            except OSError:
                return False

        return await asyncio.to_thread(_rm)

    # -- list (ops / migration verify only — NOT hot path) -------------------
    async def list(
        self, bucket: str, prefix: str, *, cursor: str | None = None, limit: int = 1000
    ) -> ListPage:
        def _walk() -> list[str]:
            bucket_root = os.path.join(self._root, bucket)
            base = os.path.join(bucket_root, prefix)
            keys: list[str] = []
            for dirpath, _dirs, files in os.walk(bucket_root):
                for name in files:
                    full = os.path.join(dirpath, name)
                    if not full.startswith(base):
                        continue
                    keys.append(os.path.relpath(full, bucket_root))
            keys.sort()
            return keys

        all_keys = await asyncio.to_thread(_walk)
        if cursor:
            all_keys = [k for k in all_keys if k > cursor]
        page_keys = all_keys[:limit]
        objects: list[ObjectInfo] = []
        for k in page_keys:
            info = await self.head(bucket, k)
            if info:
                objects.append(info)
        next_cursor = page_keys[-1] if len(all_keys) > limit and page_keys else None
        return ListPage(objects=objects, next_cursor=next_cursor)

    # -- presign -------------------------------------------------------------
    def presign_get(self, bucket: str, key: str, *, ttl_sec: int) -> str:
        import time

        exp = int(time.time()) + ttl_sec
        sig = signing.sign(self._sign_secret, bucket, key, exp)
        return f"{self._public_base}/files-signed/{bucket}/{quote(key)}?exp={exp}&sig={sig}"

    def presign_put(self, bucket: str, key: str, *, ttl_sec: int) -> str:
        raise NotImplementedError("presign_put unused in v1 — see design 01 §3")


def _atomic_write_text(path: str, text: str) -> None:
    # uuid (not PID-only) so two concurrent same-key sidecar writes cannot collide
    # on the staging name and persist truncated JSON.
    tmp = f"{path}.{uuid.uuid4().hex}.tmp"
    with open(tmp, "w") as fh:
        fh.write(text)
    os.rename(tmp, path)


def _safe_stat(path: str) -> os.stat_result | None:
    try:
        st = os.stat(path)
        return st if os.path.isfile(path) else None
    except OSError:
        return None


def _safe_read_text(path: str) -> str | None:
    try:
        with open(path) as fh:
            return fh.read()
    except FileNotFoundError:
        return None


def _guess_mime(key: str) -> str:
    mime, _ = mimetypes.guess_type(key)
    return mime or "application/octet-stream"
