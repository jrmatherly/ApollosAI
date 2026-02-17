"""Tests for app_server exception handlers."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.testclient import TestClient

from apollosai.server.auth.rbac import PermissionDeniedError


async def permission_denied_handler(request: Request, exc: PermissionDeniedError):
    return JSONResponse(status_code=403, content={'error': 'Permission denied'})


def test_permission_denied_returns_403():
    """PermissionDeniedError should produce 403, not 500."""
    app = FastAPI()

    @app.get('/test')
    async def raise_perm():
        raise PermissionDeniedError('Not authorized')

    app.add_exception_handler(PermissionDeniedError, permission_denied_handler)
    client = TestClient(app)
    resp = client.get('/test')
    assert resp.status_code == 403
    assert resp.json()['error'] == 'Permission denied'
