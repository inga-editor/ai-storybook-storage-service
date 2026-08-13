"""Filesystem path helpers for the local-fs driver — the LAST line of defense
against traversal (HTTP-layer key grammar is the first).

Layout (design 02 §2):
    STORAGE_ROOT/{bucket}/{key}              # object bytes
    STORAGE_ROOT/.meta/{bucket}/{key}.json   # sidecar metadata (parallel tree)
    STORAGE_ROOT/.tmp/{uuid}                 # atomic-rename staging (same volume)
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid

META_DIR = ".meta"
TMP_DIR = ".tmp"


def _assert_within(root: str, candidate: str) -> str:
    """realpath(candidate) MUST live under realpath(root) — else raise ValueError.
    Catches traversal even if HTTP-layer validation is bypassed."""
    root_real = os.path.realpath(root)
    cand_real = os.path.realpath(candidate)
    if cand_real != root_real and not cand_real.startswith(root_real + os.sep):
        raise ValueError("resolved path escapes storage root")
    return cand_real


def object_path(root: str, bucket: str, key: str) -> str:
    """Absolute path to the object bytes; asserted inside `root/bucket`."""
    bucket_root = os.path.join(root, bucket)
    joined = os.path.join(bucket_root, key)
    _assert_within(bucket_root, joined)
    return joined


def meta_path(root: str, bucket: str, key: str) -> str:
    meta_root = os.path.join(root, META_DIR, bucket)
    joined = os.path.join(meta_root, key + ".json")
    _assert_within(meta_root, joined)
    return joined


def new_tmp_path(root: str) -> str:
    return os.path.join(root, TMP_DIR, uuid.uuid4().hex)


async def ensure_layout(root: str, buckets: list[str]) -> None:
    """Create root, .tmp, .meta, and each bucket dir. `.tmp` MUST be on the same
    volume as buckets (atomic rename) — it lives under root, guaranteeing that."""
    def _mk() -> None:
        os.makedirs(os.path.join(root, TMP_DIR), exist_ok=True)
        os.makedirs(os.path.join(root, META_DIR), exist_ok=True)
        for b in buckets:
            os.makedirs(os.path.join(root, b), exist_ok=True)
            os.makedirs(os.path.join(root, META_DIR, b), exist_ok=True)

    await asyncio.to_thread(_mk)


async def cleanup_stale_tmp(root: str, older_than_sec: int = 3600) -> int:
    """Remove orphaned staging files (crash mid-write) older than the threshold.
    Returns the count removed. Best-effort; never raises."""
    def _clean() -> int:
        tmp = os.path.join(root, TMP_DIR)
        if not os.path.isdir(tmp):
            return 0
        cutoff = time.time() - older_than_sec
        removed = 0
        for name in os.listdir(tmp):
            p = os.path.join(tmp, name)
            try:
                if os.path.isfile(p) and os.path.getmtime(p) < cutoff:
                    os.remove(p)
                    removed += 1
            except OSError:
                continue
        return removed

    return await asyncio.to_thread(_clean)
