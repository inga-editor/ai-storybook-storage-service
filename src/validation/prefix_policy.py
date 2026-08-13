"""FE-writable prefix allowlist + media-class limits (design 04 §2).

This is the SSOT that REPLACES the old Supabase RLS. It applies to the user-JWT
mode only — S2S (X-API-Key) may write ANY prefix. A user write whose key matches no
listed prefix -> 403 (this is a security IMPROVEMENT over the old RLS, which let any
authenticated user INSERT anywhere in the bucket).

── Provenance (grep of `ai-storybook-editor/src`, 2026-08-13) ──────────────────
The design draft listed 6 prefixes; the real FE call sites use MORE, and two roots
carry MIXED media. Verified upload sites:
  uploads/        image   storage-api.ts defaultSupabaseImageUploader (default prefix)
  humans/         image   human-api.ts .upload(humans/{id}/{uuid}.ext)
  art-styles/     image   style-api.ts .upload(art-styles/{id}/{uuid}.ext)
  characters/     media   characters variant-item (image) + entity sounds (audio)
  props/          media   props variant-item (image) + props sound-item (audio)
  stages/         media   stages variant-item (image) + stages sound-item (audio)
  branch-images/  image   story-branching-modal
  parametric/     image   use-parametric-value-upload (pathPrefix "parametric/img_N")
  extract-results/ image  extract-image-modal-utils
  extract-objects/ image  extract-image-modal-utils
  auto-pics/      auto_pic use-auto-pic-upload (image webp + video webm)
  audios/         audio    uploadAudioToStorage default prefix
  audio-objects/  audio    edit-audio-modal
  videos/         video    uploadVideoToStorage default prefix
  video-objects/  video    objects-video-toolbar

DIVERGENCE FROM DESIGN (flag to sync into design 04 §2): the `media` class (image +
audio) is NEW — the draft's per-prefix single class cannot express `stages/` and
`props/` carrying BOTH variant images and sound clips (the entity id sits in a middle
segment, so a static longest-prefix map cannot split them). Adding a new FE prefix =
one entry here (additive).
"""

from __future__ import annotations

from src.core.errors import payload_too_large, prefix_not_allowed, unsupported_media_type

FE_WRITABLE_PREFIXES: dict[str, str] = {  # prefix -> media_class
    "uploads/": "image",
    "humans/": "image",
    "art-styles/": "image",
    "characters/": "media",
    "props/": "media",
    "stages/": "media",
    "branch-images/": "image",
    "parametric/": "image",
    "extract-results/": "image",
    "extract-objects/": "image",
    "auto-pics/": "auto_pic",
    "audios/": "audio",
    "audio-objects/": "audio",
    "videos/": "video",
    "video-objects/": "video",
}

MEDIA_CLASS_LIMITS: dict[str, dict] = {
    "image": {"max_bytes": 10 * 1024**2, "allowed_mime_prefixes": ["image/"]},
    "audio": {"max_bytes": 20 * 1024**2, "allowed_mime_prefixes": ["audio/"]},
    "video": {"max_bytes": 50 * 1024**2, "allowed_mime_prefixes": ["video/"]},
    "auto_pic": {"max_bytes": 50 * 1024**2, "allowed_mime_prefixes": ["image/", "video/"]},
    # Mixed entity folders (stages/props/characters) — variant images + sound clips.
    "media": {"max_bytes": 20 * 1024**2, "allowed_mime_prefixes": ["image/", "audio/"]},
}


def resolve_fe_class(key: str) -> str | None:
    """Longest matching FE-writable prefix -> media_class, or None if not writable."""
    match: str | None = None
    for prefix, media_class in FE_WRITABLE_PREFIXES.items():
        if key.startswith(prefix) and (match is None or len(prefix) > len(match)):
            match = prefix
    return FE_WRITABLE_PREFIXES[match] if match else None


def check_fe_writable(key: str) -> str:
    """Return the media_class for a user-writable key, or raise 403."""
    media_class = resolve_fe_class(key)
    if media_class is None:
        raise prefix_not_allowed()
    return media_class


def check_media_class(media_class: str, content_type: str | None, size: int | None) -> None:
    """Enforce mime (415) + size (413) for the resolved class. `content_type`/`size`
    may be None when unknown; mime None -> 415 (must be declared)."""
    limits = MEDIA_CLASS_LIMITS[media_class]
    ct = (content_type or "").split(";", 1)[0].strip().lower()
    if not any(ct.startswith(p) for p in limits["allowed_mime_prefixes"]):
        raise unsupported_media_type()
    if size is not None and size > limits["max_bytes"]:
        raise payload_too_large()
