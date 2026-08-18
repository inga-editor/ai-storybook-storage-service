"""PUT /api/storage/objects/{bucket}/{key:path} — S2S raw-bytes write (streaming).

Thin wrapper: auth -> validate -> stream into driver -> envelope. Body is read via
`request.stream()` (NEVER `request.body()`) so a 2GB video never lands in RAM.
"""

from __future__ import annotations

from fastapi import Depends, Query, Request
from fastapi.responses import JSONResponse

from src.auth.api_key import require_api_key
from src.auth.principal import Principal
from src.core.errors import already_exists, payload_too_large, validation_error
from src.drivers.registry import get_driver
from src.routers.storage.common import counting_stream, object_response
from src.validation import key_grammar
from src.validation.size_caps import resolve_s2s_cap


async def put_object(
    bucket: str,
    key: str,
    request: Request,
    upsert: bool = Query(default=False),
    principal: Principal = Depends(require_api_key),
) -> JSONResponse:
    key_grammar.validate(bucket, key, allow_at=True)

    content_type = request.headers.get("content-type")
    if not content_type:
        raise validation_error("Content-Type header is required")

    cap = resolve_s2s_cap(key)
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > cap:
        raise payload_too_large()  # fast-fail before reading any body

    stream = counting_stream(request.stream(), cap)
    result = await get_driver().put(
        bucket,
        key,
        stream,
        content_type=content_type,
        if_none_match=None if upsert else "*",
        metadata={"uploader": principal.uploader_tag()},
    )

    if result["deduped"] and not upsert:
        raise already_exists()

    status = 200 if upsert else 201
    return JSONResponse(status_code=status, content=object_response(bucket, key, result))
