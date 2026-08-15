# Storybook Storage Service

Self-hosted blob storage replacing Supabase Storage ([ADR-054](../docs/technical-decisions/adr-054-self-hosted-storage-service.md)).
FastAPI + a `BlobDriver` seam (local-fs v1). **No DB, no Supabase SDK, no AI** — the
smallest sibling of `ai-storybook-python-api` / `ai-storybook-swap-service`. Port **8200**.

Design SSOT: `ai-storybook-design/service/storage-service/` (00–06).

> Status: **bootstrapped** — the service runs, is tested, and has deploy artifacts.
> **No client has cut over yet** (image-api / swap-service / FE / video-worker are
> untouched). Client cutover + data migration are separate plans (design spec 06).

## Scope

- Owns: object write API, best-effort delete, HEAD metadata, browser multipart upload,
  signed-GET minting/verify, atomic streaming writes, content sha256 ETag, sidecar
  metadata, HMAC presign, disk-layout + tmp cleanup.
- Read path (public `GET /files/…`) is served by **nginx**, not FastAPI (design 05 §3):
  service down ⇒ writes stop but reads keep working.

## Endpoints

| Method + Path | Auth | Purpose |
|---|---|---|
| `PUT /api/storage/objects/{bucket}/{key:path}` | `X-API-Key` | S2S raw-bytes write (streaming, `?upsert=`) |
| `DELETE /api/storage/objects/{bucket}/{key:path}` | `X-API-Key` **or** user JWT | best-effort delete (always 200) |
| `HEAD /api/storage/objects/{bucket}/{key:path}` | `X-API-Key` | metadata via headers (ETag/Content-Length/Content-Type/Last-Modified) |
| `POST /api/storage/uploads` | user JWT | browser multipart upload (any prefix except `STORAGE_SERVICE_ONLY_PREFIXES`) |
| `POST /api/storage/sign` | `X-API-Key` | mint a signed GET URL (private prefix) |
| `GET /files-signed/{bucket}/{key:path}?exp&sig` | HMAC sig | verify → `X-Accel-Redirect` (nginx sendfile) |
| `GET /healthz` | none | `{status, driver, disk_free_bytes, degraded}` |

Envelope: `{success, data}` / `{success:false, error:{code, message, details?}}`.
Error codes: `VALIDATION_ERROR`(400) `UNAUTHORIZED`(401) `PREFIX_NOT_ALLOWED`/`FORBIDDEN`(403)
`NOT_FOUND`(404) `ALREADY_EXISTS`(409) `PAYLOAD_TOO_LARGE`(413) `UNSUPPORTED_MEDIA_TYPE`(415)
`INSUFFICIENT_STORAGE`(507) `STORAGE_IO_ERROR`/`INTERNAL_ERROR`(500).

## Auth

- **S2S** `X-API-Key`: constant-time match against `STORAGE_API_KEYS` (name→key map,
  multi-key for independent rotation). Empty map ⇒ fail-closed. Loopback-only surface.
- **User** Supabase JWT `Authorization: Bearer`: HS256 (`SUPABASE_JWT_SECRET`, dev) or
  JWKS RS256/ES256 (`SUPABASE_URL`, prod — the primary prod path). Pinned algorithms
  (rejects `alg=none`), `aud=authenticated`, `exp`. `sub` is audit-only — **no per-user
  scoping** (ADR-054 §4: all users are admins over shared media).

## Environment

See `.env.example`. Required: `STORAGE_PUBLIC_BASE_URL`, `STORAGE_SIGN_SECRET`.
Key others: `STORAGE_DRIVER` (`local-fs`), `STORAGE_ROOT`, `STORAGE_API_KEYS`,
`SUPABASE_JWT_SECRET`|`SUPABASE_URL`, `STORAGE_BUCKETS`, `STORAGE_PRIVATE_PREFIXES`,
`STORAGE_MAX_OBJECT_BYTES`, `STORAGE_PREFIX_SIZE_CAPS`, `HOST` (default `127.0.0.1`), `PORT` (8200).

## Run

```bash
uv sync
cp .env.example .env    # set the two required secrets
./scripts/run-service.sh          # uvicorn on 127.0.0.1:8200 (loopback — see script comment)
```

## Test

```bash
uv run pytest tests/ -q                              # unit — must be green FIRST
STORAGE_ROOT=./.storage-dev ./scripts/run-service.sh # then, in another shell:
./test-scripts/run-all.sh                            # integration (RUN_BIG=1 for ~1GB stream; NGINX=1 with docker nginx)
```

Dev user JWT: `uv run python scripts/mint_dev_user_token.py` (CLI only — no HTTP dev-mint endpoint).

## Deploy

`deploy/` has `nginx-storage.conf.example`, `storybook-storage.service` (systemd), and a
checklist + exposure-verify commands. See `deploy/README.md`.

## Boundary (what this service does NOT own)

- **No app semantics**: content-addressing, path builders, `resource_persist`, retry
  policy all stay in the clients. The service takes a fully-formed `{bucket}/{key}`.
- **No DB**, no snapshot/remix knowledge, no Supabase SDK.
- **No image transformation** (resize/composite/segment) — that stays in image-api.
- **No public read**: nginx serves `/files/`. FastAPI only sits on the signed-GET path.
