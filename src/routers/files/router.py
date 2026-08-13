"""Signed-GET router `/files-signed/*` (public via nginx proxy; HMAC-gated)."""

from __future__ import annotations

from fastapi import APIRouter

from src.routers.files.signed_get import signed_get

router = APIRouter(tags=["files"])

router.add_api_route("/files-signed/{bucket}/{key:path}", signed_get, methods=["GET"])
