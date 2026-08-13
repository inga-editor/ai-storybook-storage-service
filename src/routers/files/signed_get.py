"""GET /files-signed/{bucket}/{key:path}?exp&sig — verify HMAC then hand off to nginx.

FastAPI does NOT stream the bytes: it verifies and returns `X-Accel-Redirect` to an
nginx `internal` location that does the sendfile. Service down => write is down but
public read still lives (design 05 §3). Any verify failure -> ONE 403 (no oracle).
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import Response
from fastapi.responses import StreamingResponse

from src.config.settings import settings
from src.core.errors import forbidden, not_found
from src.drivers import signing
from src.drivers.registry import get_driver
from src.validation import key_grammar


async def signed_get(bucket: str, key: str, exp: int, sig: str) -> Response:
    key_grammar.validate(bucket, key)  # traversal guard on the read path too
    if not signing.verify(settings.storage_sign_secret, bucket, key, exp, sig):
        raise forbidden()

    if settings.storage_signed_get_dev_stream:
        # DEV ONLY (no nginx). MUST stay off in prod — prod serves via X-Accel-Redirect.
        stream = await get_driver().get(bucket, key)
        if stream is None:
            raise not_found()
        return StreamingResponse(stream, headers={"Cache-Control": "private, no-store"})

    redirect = f"/internal-files/{bucket}/{quote(key)}"
    return Response(
        status_code=200,
        headers={"X-Accel-Redirect": redirect, "Cache-Control": "private, no-store"},
    )
