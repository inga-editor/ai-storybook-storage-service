"""Storage API router group `/api/storage/*`.

Auth is PER-ROUTE (three different modes) — deliberately NOT a router-level
dependency. `test_route_auth_matrix` walks the route table to prove every
`/api/storage/*` route carries an auth dependency.
"""

from __future__ import annotations

from fastapi import APIRouter

from src.routers.storage.create_signed_url import create_signed_url
from src.routers.storage.create_upload import create_upload
from src.routers.storage.delete_object import delete_object
from src.routers.storage.head_object import head_object
from src.routers.storage.put_object import put_object

router = APIRouter(prefix="/api/storage", tags=["storage"])

router.add_api_route("/objects/{bucket}/{key:path}", put_object, methods=["PUT"])
router.add_api_route("/objects/{bucket}/{key:path}", delete_object, methods=["DELETE"])
router.add_api_route("/objects/{bucket}/{key:path}", head_object, methods=["HEAD"])
router.add_api_route("/uploads", create_upload, methods=["POST"], status_code=201)
router.add_api_route("/sign", create_signed_url, methods=["POST"])
