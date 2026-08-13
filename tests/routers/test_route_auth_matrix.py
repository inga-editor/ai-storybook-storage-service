"""Route-table guard: every /api/storage/* route carries an auth dependency;
/healthz carries none. Cheapest insurance against 'added a route, forgot auth'.

NOTE: FastAPI 0.128 / Starlette 1.6 use LAZY includes — `app.routes` holds
`_IncludedRouter` objects whose real routes live at `.original_router.routes`.
"""

from __future__ import annotations

from fastapi.routing import APIRoute

from src.auth.api_key import require_api_key
from src.auth.combined import require_api_key_or_user_jwt
from src.auth.user_jwt import require_user_jwt
from src.main import app

AUTH_DEPS = {require_api_key, require_user_jwt, require_api_key_or_user_jwt}


def _flatten(routes):
    out = []
    for r in routes:
        if type(r).__name__ == "_IncludedRouter":
            out.extend(_flatten(r.original_router.routes))
        else:
            out.append(r)
    return out


def _has_auth_dep(route: APIRoute) -> bool:
    def walk(dep) -> bool:
        for sub in dep.dependencies:  # FastAPI dependant graph is acyclic
            if sub.call in AUTH_DEPS or walk(sub):
                return True
        return False

    return route.dependant.call in AUTH_DEPS or walk(route.dependant)


def test_all_storage_routes_have_auth():
    routes = [r for r in _flatten(app.routes) if isinstance(r, APIRoute)]
    storage_routes = [r for r in routes if r.path.startswith("/api/storage")]
    assert storage_routes, "no /api/storage routes discovered — include/flatten broke"
    ungated = [(r.path, sorted(r.methods)) for r in storage_routes if not _has_auth_dep(r)]
    assert not ungated, f"ungated /api/storage routes: {ungated}"


def test_healthz_has_no_auth():
    routes = [r for r in _flatten(app.routes) if isinstance(r, APIRoute)]
    healthz = [r for r in routes if r.path == "/healthz"]
    assert healthz, "healthz route missing"
    assert not _has_auth_dep(healthz[0])
