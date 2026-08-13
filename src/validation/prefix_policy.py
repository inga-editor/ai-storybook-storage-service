"""User-write prefix policy + mime-based size caps (design 04 §2, REV 260813).

DENYLIST model (replaces the launch allowlist — REV 260813, generic-storage
decision): a user-JWT write/delete may target ANY prefix EXCEPT
`STORAGE_SERVICE_ONLY_PREFIXES`. S2S (X-API-Key) is never restricted here.
Rationale: a new FE feature folder must be an env/ops concern, not a code
deploy; protection of service-written trees (exports/, AI outputs, ...) is
config. Note the two prefix lists are ORTHOGONAL:
  - STORAGE_PRIVATE_PREFIXES      -> READ privacy (signed GET only, nginx 403)
  - STORAGE_SERVICE_ONLY_PREFIXES -> WRITE restriction (S2S only)
`exports/` sits in both.

Mime/size for user uploads no longer derives from the key prefix: the cap
comes from `STORAGE_USER_MIME_CAPS` (mime-prefix -> byte cap, longest match
wins). FAIL-CLOSED — a declared mime with no matching entry -> 415, missing
mime -> 415. This keeps text/html and image/svg+xml unservable from the
public read domain unless ops explicitly opts in.

Since RLS is gone, the residual exposure is unchanged from launch: any
authenticated user can overwrite any user-writable key (accepted in ADR-054
§4 — no per-user scoping; uuid-carrying keys make accidental collision ~0).
"""

from __future__ import annotations

from src.config.settings import settings
from src.core.errors import payload_too_large, prefix_not_allowed, unsupported_media_type


def check_user_writable(key: str) -> None:
    """Raise 403 when the key sits under a service-only prefix (user-JWT mode)."""
    for prefix in settings.service_only_prefixes:
        if key.startswith(prefix):
            raise prefix_not_allowed()


def resolve_user_cap(content_type: str | None) -> int:
    """Byte cap for a user upload, from the longest matching mime-prefix entry.
    Missing/unlisted mime -> 415 (fail-closed)."""
    ct = (content_type or "").split(";", 1)[0].strip().lower()
    match: str | None = None
    for mime_prefix in settings.user_mime_caps:
        if ct.startswith(mime_prefix) and (match is None or len(mime_prefix) > len(match)):
            match = mime_prefix
    if not ct or match is None:
        raise unsupported_media_type()
    return settings.user_mime_caps[match]


def check_user_upload(key: str, content_type: str | None, size: int | None) -> int:
    """Full user-upload gate: prefix (403) -> mime (415) -> declared size (413).
    Returns the byte cap for the streaming counter."""
    check_user_writable(key)
    cap = resolve_user_cap(content_type)
    if size is not None and size > cap:
        raise payload_too_large()
    return cap
