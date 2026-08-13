"""Storybook Storage Service — app entry point.

Self-hosted blob storage (ADR-054). Bind 127.0.0.1:8200 by default — S2S routes are
loopback-only (auth §1 Network exposure); only nginx exposes user-facing routes.

Stateless service ⇒ `workers` is free (unlike swap-service's mandatory workers=1).
Do NOT copy any single-process guard here.
"""

from __future__ import annotations

import os
import shutil
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from src.config.settings import settings
from src.core.errors import register_exception_handlers
from src.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger("main")
access_logger = get_logger("access")

_SKIP_LOG_PATHS = {"/healthz"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: ensure disk layout, clean stale tmp, build + wire the driver.
    Shutdown: release the driver seam."""
    from src.drivers.paths import cleanup_stale_tmp, ensure_layout
    from src.drivers.registry import build_driver, set_driver

    await ensure_layout(settings.storage_root, settings.buckets)
    removed = await cleanup_stale_tmp(settings.storage_root)
    driver = build_driver(settings)
    set_driver(driver)

    # Prewarm JWKS at boot when running in prod (JWKS is the primary verify path —
    # auth 04 §4). Best-effort: a fetch failure must not block boot.
    if settings.supabase_url and not settings.supabase_jwt_secret:
        from src.auth.jwks_cache import prewarm_jwks

        await prewarm_jwks(settings.supabase_url)

    free = shutil.disk_usage(settings.storage_root).free
    logger.info(
        "boot",
        extra={"data": {
            "driver": settings.storage_driver,
            "root": settings.storage_root,
            "buckets": settings.buckets,
            "api_keys": sorted(settings.api_keys.keys()),  # names only, never values
            "disk_free_bytes": free,
            "stale_tmp_removed": removed,
            "bind": f"{settings.host}:{settings.port}",
        }},
    )
    if not settings.api_keys:
        logger.warning("no_api_keys_configured", extra={"data": {"effect": "all S2S routes fail-closed (401)"}})

    # Periodic .tmp sweep: aborted writes are unlinked inline, but a crash between
    # open and unlink can still orphan a staging file. Sweep hourly so leaks cannot
    # accumulate toward ENOSPC (the startup sweep alone is not enough for a
    # long-running process).
    import asyncio

    sweeper = asyncio.create_task(_tmp_sweeper(cleanup_stale_tmp))
    try:
        yield
    finally:
        sweeper.cancel()
        set_driver(None)


async def _tmp_sweeper(cleanup_stale_tmp, interval_sec: int = 3600) -> None:
    import asyncio

    while True:
        try:
            await asyncio.sleep(interval_sec)
            removed = await cleanup_stale_tmp(settings.storage_root)
            if removed:
                logger.info("tmp_swept", extra={"data": {"removed": removed}})
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — a sweep failure must not kill the loop
            logger.warning("tmp_sweep_failed", extra={"data": {"error": str(exc)}})


app = FastAPI(
    title="Storybook Storage Service",
    description="Self-hosted blob storage (ADR-054) — BlobDriver seam, local-fs v1.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,  # Bearer / X-API-Key, not cookies
    allow_methods=["GET", "HEAD", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


@app.middleware("http")
async def access_log(request: Request, call_next):
    """Correlated access log (method/path/status/ms/req_id). No headers, no body."""
    req_id = os.urandom(4).hex()
    started = time.monotonic()
    response = await call_next(request)
    if request.url.path not in _SKIP_LOG_PATHS:
        access_logger.info(
            "req",
            extra={"data": {
                "id": req_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "ms": round((time.monotonic() - started) * 1000, 1),
            }},
        )
    return response


register_exception_handlers(app)


@app.get("/healthz")
async def healthz() -> dict:
    """Liveness + disk free + driver info. Does NOT depend on the driver seam being
    set (resilient in tests / before lifespan)."""
    import asyncio

    try:
        usage = await asyncio.to_thread(shutil.disk_usage, settings.storage_root)
        free = usage.free
        degraded = free < settings.storage_min_free_bytes
    except OSError:
        # Root not reachable (missing mount / not yet created) => degraded, not 500.
        free = 0
        degraded = True
    return {
        "status": "ok",
        "driver": settings.storage_driver,
        "disk_free_bytes": free,
        "degraded": degraded,
    }


# Routers are included in their phases (storage -> Phase 05, files -> Phase 06).
from src.routers.storage.router import router as storage_router  # noqa: E402
from src.routers.files.router import router as files_router  # noqa: E402

app.include_router(storage_router)
app.include_router(files_router)
