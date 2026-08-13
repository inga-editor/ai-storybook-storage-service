"""LocalFsBlobDriver.put — streaming, dedup, upsert, ETag, atomicity, ENOSPC."""

from __future__ import annotations

import errno
import hashlib
import os

import pytest

from src.drivers import local_fs, paths
from src.drivers.errors import InsufficientStorageError, StorageIoError

BUCKET = "storybook-assets"


async def _chunks(*parts: bytes):
    for p in parts:
        yield p


async def test_put_new(local_driver):
    r = await local_driver.put(BUCKET, "ai-logs/a.png", b"hello", content_type="image/png")
    assert r["deduped"] is False
    assert r["bytes"] == 5
    assert r["etag"] == hashlib.sha256(b"hello").hexdigest()


async def test_put_streaming_multi_chunk(local_driver):
    r = await local_driver.put(BUCKET, "videos/v.mp4", _chunks(b"ab", b"cd", b"ef"), content_type="video/mp4")
    assert r["bytes"] == 6
    assert r["etag"] == hashlib.sha256(b"abcdef").hexdigest()
    # assembled bytes on disk match
    dest = paths.object_path(local_driver._root, BUCKET, "videos/v.mp4")
    assert open(dest, "rb").read() == b"abcdef"


async def test_etag_is_sha256(local_driver):
    payload = b"content-addressed-bytes"
    r = await local_driver.put(BUCKET, "ai-logs/c.bin", payload, content_type="application/octet-stream")
    assert r["etag"] == hashlib.sha256(payload).hexdigest()


async def test_if_none_match_dedup_no_rewrite(local_driver):
    await local_driver.put(BUCKET, "ai-logs/d.png", b"orig", content_type="image/png")
    dest = paths.object_path(local_driver._root, BUCKET, "ai-logs/d.png")
    mtime_before = os.path.getmtime(dest)
    r = await local_driver.put(BUCKET, "ai-logs/d.png", b"IGNORED", content_type="image/png", if_none_match="*")
    assert r["deduped"] is True
    assert r["etag"] == hashlib.sha256(b"orig").hexdigest()
    assert os.path.getmtime(dest) == mtime_before  # untouched
    assert open(dest, "rb").read() == b"orig"


async def test_upsert_overwrite(local_driver):
    await local_driver.put(BUCKET, "ai-logs/e.png", b"one", content_type="image/png")
    r = await local_driver.put(BUCKET, "ai-logs/e.png", b"two-longer", content_type="image/png")
    assert r["deduped"] is False
    dest = paths.object_path(local_driver._root, BUCKET, "ai-logs/e.png")
    assert open(dest, "rb").read() == b"two-longer"


async def test_atomicity_rename_failure_cleans_tmp(local_driver, monkeypatch):
    real_rename = os.rename

    def boom(src, dst):
        if os.path.dirname(dst).startswith(os.path.join(local_driver._root, BUCKET)):
            raise OSError(errno.EIO, "rename failed")
        return real_rename(src, dst)

    monkeypatch.setattr(os, "rename", boom)
    with pytest.raises(StorageIoError):
        await local_driver.put(BUCKET, "ai-logs/f.png", b"data", content_type="image/png")
    # dest absent
    dest = paths.object_path(local_driver._root, BUCKET, "ai-logs/f.png")
    assert not os.path.exists(dest)
    # tmp cleaned
    tmp_dir = os.path.join(local_driver._root, paths.TMP_DIR)
    assert os.listdir(tmp_dir) == []


async def test_enospc_raises_insufficient_storage_and_cleans_tmp(local_driver, monkeypatch):
    def enospc(_fd):
        raise OSError(errno.ENOSPC, "no space")

    monkeypatch.setattr(local_fs.os, "fsync", enospc)
    with pytest.raises(InsufficientStorageError):
        await local_driver.put(BUCKET, "ai-logs/g.png", b"data", content_type="image/png")
    tmp_dir = os.path.join(local_driver._root, paths.TMP_DIR)
    assert os.listdir(tmp_dir) == []


class _Boom(Exception):
    pass


async def test_non_oserror_abort_cleans_tmp(local_driver):
    """Regression (code-review H1): a mid-stream raise that is NOT an OSError —
    e.g. counting_stream's payload_too_large() or a ClientDisconnect — must still
    unlink the staging tmp file (else disk-fill DoS). No object lands at dest."""

    async def boom():
        yield b"aaaa"
        raise _Boom()

    with pytest.raises(_Boom):
        await local_driver.put(BUCKET, "videos/abort.mp4", boom(), content_type="video/mp4")

    dest = paths.object_path(local_driver._root, BUCKET, "videos/abort.mp4")
    assert not os.path.exists(dest)
    tmp_dir = os.path.join(local_driver._root, paths.TMP_DIR)
    assert os.listdir(tmp_dir) == []
