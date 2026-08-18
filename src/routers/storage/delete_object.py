"""DELETE /api/storage/objects/{bucket}/{key:path} — best-effort, ALWAYS 200.

S2S may delete any key; user JWT any key EXCEPT service-only prefixes. Never 404
(parity `delete_object` swallowing missing keys — compensation flows must not fail).
"""

from __future__ import annotations

from fastapi import Depends

from src.auth.combined import require_api_key_or_user_jwt
from src.auth.principal import Principal
from src.drivers.registry import get_driver
from src.validation import key_grammar
from src.validation.prefix_policy import check_user_writable


async def delete_object(
    bucket: str,
    key: str,
    principal: Principal = Depends(require_api_key_or_user_jwt),
) -> dict:
    # Validate AFTER resolving principal: allow_at gates on who is calling —
    # service may delete sibling rendition keys, user JWT may not (design 04 §3).
    key_grammar.validate(bucket, key, allow_at=principal.kind == "service")
    if principal.kind == "user":
        check_user_writable(key)  # 403 on service-only prefixes
    deleted = await get_driver().delete(bucket, key)
    return {"success": True, "data": {"deleted": deleted}}
