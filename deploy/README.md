# Deploy — Storybook Storage Service (port 8200)

Scope of this doc = **artifacts** (nginx conf + systemd unit + checklist). Real prod
deploy (DNS, TLS, dedicated volume) happens when a server + domain exist — likely
folded into the migration plan. Validate the unit file with `systemd-analyze verify
storybook-storage.service`; don't `systemctl start` without a real `STORAGE_ROOT`.

## Exposure matrix (this IS the security boundary)

| Route | Auth | Exposed by nginx? |
|---|---|---|
| `GET /files/…` | none | ✅ public (sendfile) |
| `GET /files-signed/…` | HMAC sig | ✅ public (proxy → FastAPI verify) |
| `POST /api/storage/uploads` | user JWT | ✅ public (proxy → 127.0.0.1:8200) |
| `DELETE /api/storage/objects/…` (user) | user JWT | ✅ public (`limit_except DELETE`) |
| `PUT` / `HEAD /api/storage/objects/…`, `POST /api/storage/sign` | X-API-Key | ❌ **loopback-only** |
| `GET /healthz` | none | ❌ loopback + internal monitor |

## Checklist

1. Create user + volume: `useradd -r storybook-storage`; `mkdir -p /var/lib/storybook-storage`; `chown storybook-storage: /var/lib/storybook-storage`.
2. Deploy code to `/opt/storybook-storage-service`; `uv sync`.
3. `.env` from `.env.example` — set REQUIRED `STORAGE_PUBLIC_BASE_URL` + `STORAGE_SIGN_SECRET`, the `STORAGE_API_KEYS` map, and either `SUPABASE_JWT_SECRET` (dev) or `SUPABASE_URL` (prod JWKS). `STORAGE_ROOT=/var/lib/storybook-storage`. `STORAGE_SIGNED_GET_DEV_STREAM=false`.
4. systemd: copy `storybook-storage.service` → `/etc/systemd/system/`; `systemctl daemon-reload && systemctl enable --now storybook-storage`.
5. nginx: copy `nginx-storage.conf.example` → sites; substitute `{STORAGE_ROOT}` + `storage.{domain}`; keep the `exports/` block and `\.(meta|tmp)/` deny; `nginx -t && systemctl reload nginx`.
6. DNS `storage.{domain}` (recommended dedicated subdomain) + TLS cert.

## Verify exposure (do NOT trust the config on paper)

```bash
# from an EXTERNAL host — S2S route must be unreachable (404 from nginx, NOT 401):
curl -sS -o /dev/null -w '%{http_code}\n' -X PUT https://storage.{domain}/api/storage/objects/storybook-assets/x.png
# expect: 404

# public read works + immutable cache + Range:
curl -I https://storage.{domain}/files/storybook-assets/<some-key>      # 200 + Cache-Control immutable
curl -r 0-99 https://storage.{domain}/files/storybook-assets/<some-key> # 206

# private prefix blocked:
curl -o /dev/null -w '%{http_code}\n' https://storage.{domain}/files/storybook-assets/exports/x.pdf   # 403
# sidecar not leaked:
curl -o /dev/null -w '%{http_code}\n' https://storage.{domain}/files/.meta/storybook-assets/x.png     # 403/404
```

## Local dev smoke via docker nginx

```bash
# 1) run the service against a dev root
STORAGE_ROOT=./.storage-dev ./scripts/run-service.sh
# 2) run nginx in docker, mounting the conf + the same STORAGE_ROOT
docker run --rm -p 8080:80 \
  -v "$PWD/deploy/nginx-storage.conf.example:/etc/nginx/conf.d/default.conf:ro" \
  -v "$PWD/.storage-dev:/var/lib/storybook-storage:ro" \
  --add-host host.docker.internal:host-gateway nginx:1.27
# (edit the conf: proxy_pass http://host.docker.internal:8200; alias /var/lib/storybook-storage/)
# 3) smoke: NGINX=1 ./test-scripts/test-sign-and-fetch.sh ; curl -I localhost:8080/files/...
```

## Ops checklist when adding a private prefix

Add both: (a) the prefix to `STORAGE_PRIVATE_PREFIXES` env, and (b) a
`location ^~ /files/storybook-assets/{prefix} { return 403; }` block **before**
`location /files/`. They must stay in sync by hand.
