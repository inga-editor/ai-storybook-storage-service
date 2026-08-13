"""Auth principal — who is writing. Used ONLY for the sidecar `uploader` audit tag.

NO per-user/per-book scoping (ADR-054 §4, chốt 260813): all authenticated users are
admins over shared media. `sub` is audit metadata, NEVER an authorization input.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Principal:
    kind: Literal["service", "user"]
    name: str  # service: api-key name (e.g. "image-api"); user: jwt.sub

    def uploader_tag(self) -> str:
        return f"svc:{self.name}" if self.kind == "service" else f"user:{self.name}"
