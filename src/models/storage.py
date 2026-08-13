"""Pydantic request/response models for the storage API (design 03 §2)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SignRequest(BaseModel):
    bucket: str = "storybook-assets"
    key: str
    expires_in: int = Field(default=3600, gt=0, le=86400)  # cap 24h


class SignResponseData(BaseModel):
    signed_url: str
    expires_at: str  # ISO-8601 UTC


class PutObjectResponseData(BaseModel):
    bucket: str
    key: str
    url: str
    etag: str
    bytes: int
    deduped: bool


class DeleteResponseData(BaseModel):
    deleted: bool
