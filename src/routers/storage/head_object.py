"""HEAD /api/storage/objects/{bucket}/{key:path} — headers-only metadata.

CHỐT (validation 260813): headers-only, NO body JSON, NO /meta route. `curl -I`
reads it directly. Migration-verify clients read: ETag, Content-Length,
Content-Type, Last-Modified. Missing object -> 404.
"""

from __future__ import annotations

from email.utils import format_datetime

from fastapi import Depends, Response

from src.auth.api_key import require_api_key
from src.auth.principal import Principal
from src.core.errors import not_found
from src.drivers.registry import get_driver
from src.validation import key_grammar


async def head_object(
    bucket: str,
    key: str,
    _principal: Principal = Depends(require_api_key),
) -> Response:
    key_grammar.validate(bucket, key)
    info = await get_driver().head(bucket, key)
    if info is None:
        raise not_found()

    headers = {
        "Content-Length": str(info["bytes"]),
        "Content-Type": info["content_type"],
    }
    if info["etag"]:
        headers["ETag"] = f'"{info["etag"]}"'
    last_modified = _http_date(info["modified_at"])
    if last_modified:
        headers["Last-Modified"] = last_modified
    return Response(status_code=200, headers=headers)


def _http_date(iso_utc: str) -> str | None:
    from datetime import datetime

    try:
        dt = datetime.fromisoformat(iso_utc)
        return format_datetime(dt, usegmt=True)
    except ValueError:
        return None
