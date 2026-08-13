"""POST /api/storage/uploads — browser multipart upload (user JWT).

Replaces supabase-js `.upload()`. Validation: key grammar -> service-only prefix
denylist -> mime cap map. Writes with upsert=true (FE keys carry a uuid ->
collision ~0).
"""

from __future__ import annotations

from fastapi import Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse

from src.auth.principal import Principal
from src.auth.user_jwt import require_user_jwt
from src.drivers.local_fs import CHUNK_SIZE
from src.drivers.registry import get_driver
from src.routers.storage.common import counting_stream, object_response
from src.validation import key_grammar
from src.validation.prefix_policy import check_user_upload


async def _upload_iter(upload: UploadFile):
    while True:
        chunk = await upload.read(CHUNK_SIZE)
        if not chunk:
            break
        yield chunk


async def create_upload(
    file: UploadFile = File(...),
    key: str = Form(...),
    bucket: str = Form("storybook-assets"),
    principal: Principal = Depends(require_user_jwt),
) -> JSONResponse:
    key_grammar.validate(bucket, key)
    # 403 service-only prefix -> 415 mime outside STORAGE_USER_MIME_CAPS -> 413
    # fast-fail on client-declared size; the counter re-enforces the cap on stream.
    cap = check_user_upload(key, file.content_type, file.size)

    stream = counting_stream(_upload_iter(file), cap)
    result = await get_driver().put(
        bucket,
        key,
        stream,
        content_type=file.content_type or "application/octet-stream",
        if_none_match=None,  # upsert=true
        metadata={"uploader": principal.uploader_tag()},
    )
    return JSONResponse(status_code=201, content=object_response(bucket, key, result))
