"""Application settings loaded from environment variables (Pydantic Settings).

Boundary: this service is a self-hosted blob store (ADR-054). It has NO database,
NO Supabase SDK, NO AI dependency — the smallest sibling of image-api/swap-service.
It shares only the `{success, data}` envelope + HTTP-code convention.

Fail-fast on the two REQUIRED secrets (`storage_public_base_url`,
`storage_sign_secret`): a missing value raises at `Settings()` construction so boot
dies with a clear message instead of surfacing as opaque 500s at request time.
"""

from __future__ import annotations

import json
from functools import cached_property

from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_json_or_csv_list(raw: str) -> list[str]:
    """Accept either a JSON array (`["a","b"]`) or a CSV string (`a,b`). Empties dropped."""
    raw = raw.strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
            return [str(x).strip() for x in parsed if str(x).strip()]
        except (json.JSONDecodeError, TypeError):
            pass
    return [s.strip() for s in raw.split(",") if s.strip()]


def _parse_json_map(raw: str) -> dict[str, str]:
    """Parse a JSON object env var into a `str -> str` map. Invalid/empty -> {}."""
    raw = raw.strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return {str(k): str(v) for k, v in parsed.items()}
    except (json.JSONDecodeError, TypeError):
        pass
    return {}


def _parse_json_int_map(raw: str) -> dict[str, int]:
    """Parse a JSON object env var into a `str -> int` map (prefix -> byte cap)."""
    raw = raw.strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return {str(k): int(v) for k, v in parsed.items()}
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return {}


class Settings(BaseSettings):
    """Configuration for the Storybook Storage Service."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- REQUIRED -----------------------------------------------------------
    # Public base URL used to BUILD persisted URLs (`{base}/files/{bucket}/{key}`)
    # and to sign GET URLs. e.g. https://storage.example.com. No trailing slash.
    storage_public_base_url: str
    # HMAC secret for signed GET. SECRET — never logged, never returned to client.
    storage_sign_secret: str

    # --- Driver / disk ------------------------------------------------------
    # `local-fs` (v1) | `s3` (declared, NOT implemented — boot fails clearly).
    storage_driver: str = "local-fs"
    storage_root: str = "/var/lib/storybook-storage"

    # --- Auth (S2S + user JWT) ----------------------------------------------
    # JSON map name->key, e.g. {"image-api":"…","swap-service":"…","ops":"…"}.
    # Empty => fail-closed on every S2S route (service still boots, warns once).
    storage_api_keys: str = ""
    # HS256 secret (local/dev). Prod verifies via JWKS (`supabase_url`).
    supabase_jwt_secret: str = ""
    # Source of JWKS (`{supabase_url}/auth/v1/.well-known/jwks.json`) for prod.
    supabase_url: str = ""

    # --- Buckets / prefixes / caps ------------------------------------------
    storage_buckets: str = "storybook-assets"          # CSV or JSON list
    storage_private_prefixes: str = "exports/"         # CSV list (signed-GET only)
    storage_max_object_bytes: int = 52428800           # 50MB default S2S cap
    storage_prefix_size_caps: str = '{"videos/": 3221225472}'  # JSON map prefix->cap
    storage_min_free_bytes: int = 10737418240          # 10GB -> healthz degraded

    # --- Signed GET dev fallback --------------------------------------------
    # When no nginx (dev), stream bytes through the driver on signed GET. Never on.
    # in prod (prod uses X-Accel-Redirect). Gated so it is impossible to enable by
    # accident behind nginx.
    storage_signed_get_dev_stream: bool = False

    # --- Request / CORS / bind ----------------------------------------------
    cors_allowed_origins: str = "http://localhost:5173"
    host: str = "127.0.0.1"
    port: int = 8200

    @cached_property
    def api_keys(self) -> dict[str, str]:
        """Parsed `name -> key` map. Empty => fail-closed S2S auth."""
        return _parse_json_map(self.storage_api_keys)

    @cached_property
    def buckets(self) -> list[str]:
        return _parse_json_or_csv_list(self.storage_buckets)

    @cached_property
    def private_prefixes(self) -> list[str]:
        return _parse_json_or_csv_list(self.storage_private_prefixes)

    @cached_property
    def prefix_size_caps(self) -> dict[str, int]:
        return _parse_json_int_map(self.storage_prefix_size_caps)

    @cached_property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @cached_property
    def public_base_url(self) -> str:
        """Public base URL without a trailing slash (URLs joined with `/files/...`)."""
        return self.storage_public_base_url.rstrip("/")


settings = Settings()  # type: ignore[call-arg]  # required fields come from env/.env
