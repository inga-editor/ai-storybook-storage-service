"""LocalFsBlobDriver.head / delete / list / get."""

from __future__ import annotations

import hashlib
import os

from src.drivers import paths

BUCKET = "storybook-assets"


async def test_head_with_sidecar(local_driver):
    await local_driver.put(BUCKET, "ai-logs/h.png", b"pixels", content_type="image/png",
                           metadata={"uploader": "svc:image-api"})
    info = await local_driver.head(BUCKET, "ai-logs/h.png")
    assert info is not None
    assert info["content_type"] == "image/png"
    assert info["bytes"] == 6
    assert info["etag"] == hashlib.sha256(b"pixels").hexdigest()
    assert info["metadata"].get("uploader") == "svc:image-api"


async def test_head_missing(local_driver):
    assert await local_driver.head(BUCKET, "ai-logs/none.png") is None


async def test_head_sidecar_fallback(local_driver):
    await local_driver.put(BUCKET, "ai-logs/i.png", b"data", content_type="image/png")
    # delete the sidecar -> head falls back to stat + mime-by-extension + recompute etag
    meta = paths.meta_path(local_driver._root, BUCKET, "ai-logs/i.png")
    os.remove(meta)
    info = await local_driver.head(BUCKET, "ai-logs/i.png")
    assert info is not None
    assert info["content_type"] == "image/png"  # guessed from .png
    assert info["etag"] == hashlib.sha256(b"data").hexdigest()  # recomputed (small file)


async def test_delete_best_effort(local_driver):
    await local_driver.put(BUCKET, "ai-logs/j.png", b"x", content_type="image/png")
    assert await local_driver.delete(BUCKET, "ai-logs/j.png") is True
    assert await local_driver.delete(BUCKET, "ai-logs/j.png") is False  # already gone, no raise


async def test_delete_removes_sidecar(local_driver):
    await local_driver.put(BUCKET, "ai-logs/k.png", b"x", content_type="image/png")
    meta = paths.meta_path(local_driver._root, BUCKET, "ai-logs/k.png")
    assert os.path.exists(meta)
    await local_driver.delete(BUCKET, "ai-logs/k.png")
    assert not os.path.exists(meta)


async def test_get_stream(local_driver):
    await local_driver.put(BUCKET, "ai-logs/l.png", b"streamed", content_type="image/png")
    it = await local_driver.get(BUCKET, "ai-logs/l.png")
    assert it is not None
    buf = b""
    async for chunk in it:
        buf += chunk
    assert buf == b"streamed"
    assert await local_driver.get(BUCKET, "ai-logs/missing.png") is None


async def test_list_prefix_and_cursor(local_driver):
    for i in range(5):
        await local_driver.put(BUCKET, f"videos/v{i}.mp4", b"x", content_type="video/mp4")
    await local_driver.put(BUCKET, "ai-logs/other.png", b"x", content_type="image/png")

    page1 = await local_driver.list(BUCKET, "videos/", limit=2)
    keys1 = [o["key"] for o in page1["objects"]]
    assert keys1 == ["videos/v0.mp4", "videos/v1.mp4"]
    assert page1["next_cursor"] == "videos/v1.mp4"

    page2 = await local_driver.list(BUCKET, "videos/", cursor=page1["next_cursor"], limit=2)
    keys2 = [o["key"] for o in page2["objects"]]
    assert keys2 == ["videos/v2.mp4", "videos/v3.mp4"]
    # prefix isolation: no ai-logs leak
    assert all(k.startswith("videos/") for k in keys1 + keys2)
