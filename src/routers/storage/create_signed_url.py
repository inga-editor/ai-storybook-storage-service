"""POST /api/storage/sign — mint a signed GET URL (S2S). Pure computation: no disk
I/O, no existence check (design 03 §5). `expires_in` capped at 24h by the model.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends

from src.auth.api_key import require_api_key
from src.auth.principal import Principal
from src.drivers.registry import get_driver
from src.models.storage import SignRequest
from src.validation import key_grammar


async def create_signed_url(
    payload: SignRequest,
    _principal: Principal = Depends(require_api_key),
) -> dict:
    key_grammar.validate(payload.bucket, payload.key, allow_at=True)
    signed_url = get_driver().presign_get(payload.bucket, payload.key, ttl_sec=payload.expires_in)
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=payload.expires_in)).isoformat()
    return {"success": True, "data": {"signed_url": signed_url, "expires_at": expires_at}}
