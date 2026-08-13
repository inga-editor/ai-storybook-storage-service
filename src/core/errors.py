"""Service error taxonomy + FastAPI exception handlers.

Envelope (parity image-api / swap-service):
    { "success": false, "error": { "code", "message", "details"? } }

HTTP code convention (inherited from image-api):
  - Pydantic body/query invalid -> 400 VALIDATION_ERROR (NOT FastAPI's default 422)
  - not found                   -> 404 NOT_FOUND

Error codes (design 03 §6): VALIDATION_ERROR(400), UNAUTHORIZED(401),
PREFIX_NOT_ALLOWED(403), NOT_FOUND(404), ALREADY_EXISTS(409),
PAYLOAD_TOO_LARGE(413), UNSUPPORTED_MEDIA_TYPE(415), INSUFFICIENT_STORAGE(507),
STORAGE_IO_ERROR(500), INTERNAL_ERROR(500).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.core.logging import get_logger
from src.drivers.errors import InsufficientStorageError, StorageIoError

logger = get_logger("errors")


class ServiceError(Exception):
    """Domain error carrying a stable `code` + HTTP status. Handlers render it to the
    spec envelope. `message` is client-safe (never raw disk path / stack detail)."""

    def __init__(
        self,
        code: str,
        http_status: int,
        message: str,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.message = message
        self.details = details


# Constructor helpers pin the status per code so call-sites read as intent.
def validation_error(message: str, details: dict | None = None) -> ServiceError:
    return ServiceError("VALIDATION_ERROR", 400, message, details)


def unauthorized(message: str = "Unauthorized") -> ServiceError:
    """Missing/invalid X-API-Key OR JWT invalid/expired/bad-aud/bad-alg — ONE code,
    never distinguished, to deny an auth oracle."""
    return ServiceError("UNAUTHORIZED", 401, message)


def prefix_not_allowed(message: str = "Key prefix not writable") -> ServiceError:
    return ServiceError("PREFIX_NOT_ALLOWED", 403, message)


def forbidden(message: str = "Forbidden") -> ServiceError:
    """Signed-GET verify failure (bad sig / expired) — ONE 403, never distinguished."""
    return ServiceError("FORBIDDEN", 403, message)


def not_found(message: str = "Not found") -> ServiceError:
    return ServiceError("NOT_FOUND", 404, message)


def already_exists(message: str = "Object already exists") -> ServiceError:
    return ServiceError("ALREADY_EXISTS", 409, message)


def payload_too_large(message: str = "Payload too large") -> ServiceError:
    return ServiceError("PAYLOAD_TOO_LARGE", 413, message)


def unsupported_media_type(message: str = "Unsupported media type") -> ServiceError:
    return ServiceError("UNSUPPORTED_MEDIA_TYPE", 415, message)


def insufficient_storage(message: str = "Insufficient storage") -> ServiceError:
    return ServiceError("INSUFFICIENT_STORAGE", 507, message)


def storage_io_error(message: str = "Storage IO error") -> ServiceError:
    return ServiceError("STORAGE_IO_ERROR", 500, message)


def _envelope(exc: ServiceError) -> dict:
    error: dict = {"code": exc.code, "message": exc.message}
    if exc.details:
        error["details"] = exc.details
    return {"success": False, "error": error}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def _service_error_handler(_request: Request, exc: ServiceError) -> JSONResponse:
        if exc.http_status >= 500:
            logger.error("service_error", extra={"data": {"code": exc.code}})
        return JSONResponse(status_code=exc.http_status, content=_envelope(exc))

    @app.exception_handler(InsufficientStorageError)
    async def _insufficient_storage_handler(_request: Request, _exc: InsufficientStorageError) -> JSONResponse:
        logger.error("insufficient_storage", extra={"data": {"code": "INSUFFICIENT_STORAGE"}})
        return JSONResponse(status_code=507, content=_envelope(insufficient_storage()))

    @app.exception_handler(StorageIoError)
    async def _storage_io_handler(_request: Request, exc: StorageIoError) -> JSONResponse:
        logger.error("storage_io_error", extra={"data": {"type": exc.__class__.__name__}}, exc_info=exc)
        return JSONResponse(status_code=500, content=_envelope(storage_io_error()))

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        """Pydantic body/query errors -> 400 VALIDATION_ERROR (parity image-api)."""
        errors = exc.errors()
        first = errors[0] if errors else {}
        loc = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
        msg = first.get("msg", "Validation error")
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"{loc}: {msg}" if loc else msg,
                    "details": {
                        "fields": [
                            {"loc": [str(p) for p in e.get("loc", ())], "msg": e.get("msg")}
                            for e in errors
                        ]
                    },
                },
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(_request: Request, exc: Exception) -> JSONResponse:
        """Last resort: log full trace server-side, return a static 500 (no leak)."""
        logger.error("internal_error", extra={"data": {"type": exc.__class__.__name__}}, exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}},
        )
