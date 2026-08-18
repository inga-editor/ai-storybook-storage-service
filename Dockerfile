FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

RUN useradd -r -u 999 -m app

ENV UV_CACHE_DIR=/tmp/uv-cache

WORKDIR /app
RUN chown app: /app
USER app

# deps layer — cached until pyproject/uv.lock change; wheel cache lives in a build-cache mount, not the image
COPY --chown=app:app pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/tmp/uv-cache,uid=999 uv sync --frozen --no-install-project --no-dev

COPY --chown=app:app . .
RUN --mount=type=cache,target=/tmp/uv-cache,uid=999 uv sync --frozen --no-dev

EXPOSE 8200

# 127.0.0.1: the S2S write routes are loopback-only by design (ADR-054) — prod runs
# with network_mode: host behind host nginx. Runtime uid comes from compose `user:`
# (owner of STORAGE_ROOT) so written blobs stay readable by nginx and the script-run
# fallback; the venv is owned by uid 999 but --no-sync never writes to it.
CMD ["uv", "run", "--no-sync", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", "8200"]
