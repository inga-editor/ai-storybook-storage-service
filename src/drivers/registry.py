"""Driver accessor seam — the single injection point for tests + lifespan.

Same idiom as swap-service `set_adapter/get_adapter`: a module-global driver set at
lifespan startup (or by a test fixture). `build_driver()` (added with the concrete
drivers) constructs the driver from settings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.config.settings import Settings
    from src.drivers.base import BlobDriver

_DRIVER: BlobDriver | None = None


def set_driver(driver: BlobDriver | None) -> None:
    global _DRIVER
    _DRIVER = driver


def get_driver() -> BlobDriver:
    if _DRIVER is None:
        raise RuntimeError("BlobDriver not set — wire it in lifespan startup (or a test fixture)")
    return _DRIVER


def build_driver(settings: Settings) -> BlobDriver:
    """Construct the driver from `STORAGE_DRIVER`. `s3` is declared but NOT
    implemented in v1 — fail fast instead of silently falling back."""
    driver = settings.storage_driver
    if driver == "local-fs":
        from src.drivers.local_fs import LocalFsBlobDriver

        return LocalFsBlobDriver(
            root=settings.storage_root,
            sign_secret=settings.storage_sign_secret,
            public_base_url=settings.public_base_url,
        )
    if driver == "s3":
        raise RuntimeError("STORAGE_DRIVER=s3 is declared but not implemented in v1 (see design 02 §3)")
    raise RuntimeError(f"Unknown STORAGE_DRIVER={driver!r} (expected 'local-fs' or 's3')")
