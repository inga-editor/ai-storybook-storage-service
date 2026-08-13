# Changelog

## [0.1.0] — 2026-08-13 — bootstrap

Initial self-hosted storage service ([ADR-054](../docs/technical-decisions/adr-054-self-hosted-storage-service.md)),
design spec `ai-storybook-design/service/storage-service/` (00–06). **No client has cut
over** — image-api / swap-service / FE / video-worker are untouched (separate plans).

### Added
- FastAPI app on `127.0.0.1:8200` (loopback default — S2S routes are the security boundary), stateless (`workers` free).
- `BlobDriver` Protocol (6 verbs) + module-global accessor seam (`set_driver`/`get_driver`/`build_driver`).
- **local-fs driver**: streaming atomic writes (tmp → fsync → rename), content sha256 ETag computed in one pass, sidecar metadata (`.meta/`), best-effort delete, `list` with cursor, HMAC `presign_get`. `presign_put`/`s3` declared but not implemented (v1).
- **6 endpoints**: PUT / DELETE / HEAD objects, POST `/uploads` (multipart), POST `/sign`, GET `/files-signed` (verify → `X-Accel-Redirect`); plus `/healthz`.
- **Auth**: S2S `X-API-Key` multi-key (constant-time, fail-closed); user Supabase JWT (HS256 dev / JWKS RS256-ES256 prod, pinned algorithms, `aud`/`exp`, no per-user scoping).
- **Validation**: key grammar (traversal/charset/length/extension/bucket), FE-writable prefix allowlist + mime/size media classes, per-prefix S2S size caps (`videos/`→3GB).
- **nginx contract**: `deploy/nginx-storage.conf.example` (public read immutable-cache, private-prefix block, sidecar deny, internal X-Accel target, user-facing proxy), systemd unit, deploy README with exposure-verify commands.
- Test bookends: `test-scripts/` (integration) + `tests/` (pytest unit).

### Hardening (post code-review)
- **Tmp staging file is unlinked on ANY pre-rename failure** (payload_too_large / client disconnect / OSError), not just OSError — closes a disk-fill DoS via aborted oversized uploads. Regression-tested.
- **Periodic `.tmp` sweep** (hourly background task) in addition to the startup sweep — orphans from a crash between open and unlink cannot accumulate.
- **Sidecar staging name uses uuid** (not PID-only) — concurrent same-key sidecar writes no longer collide.

### Notes / divergences from design
- **FE-writable prefix allowlist expanded** beyond the 6-prefix draft after grepping `ai-storybook-editor/src` (2026-08-13): added `uploads/ characters/ branch-images/ parametric/ extract-results/ extract-objects/ audio-objects/ video-objects/`, and a NEW `media` class (image+audio) for `stages/`/`props/`/`characters/` which carry both variant images and sound clips. Design 04 §2 should be synced. See `src/validation/prefix_policy.py` docstring for full provenance.
