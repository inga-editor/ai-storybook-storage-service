"""Driver-layer domain exceptions.

Deliberately FastAPI-free (design 02 §1: the driver does not know HTTP). The HTTP
layer maps these to status codes in `core/errors.register_exception_handlers`:
  - InsufficientStorageError -> 507 INSUFFICIENT_STORAGE
  - StorageIoError           -> 500 STORAGE_IO_ERROR
"""

from __future__ import annotations


class DriverError(Exception):
    """Base for local-fs / future s3 driver failures."""


class InsufficientStorageError(DriverError):
    """Disk full (ENOSPC) while writing an object."""


class StorageIoError(DriverError):
    """Any other filesystem/IO failure while reading or writing an object."""
