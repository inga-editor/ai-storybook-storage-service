"""S2S per-prefix size caps (design 03 §2). Longest-prefix match against
`STORAGE_PREFIX_SIZE_CAPS`, else `STORAGE_MAX_OBJECT_BYTES` (50MB default).

  videos/ -> 3GB (book MP4 finals 500MB–2GB, ADR-036)
"""

from __future__ import annotations

from src.config.settings import settings


def resolve_s2s_cap(key: str) -> int:
    caps = settings.prefix_size_caps
    best_prefix: str | None = None
    for prefix in caps:
        if key.startswith(prefix) and (best_prefix is None or len(prefix) > len(best_prefix)):
            best_prefix = prefix
    if best_prefix is not None:
        return caps[best_prefix]
    return settings.storage_max_object_bytes
