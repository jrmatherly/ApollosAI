"""Tests for rate limiting on auth endpoints."""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

from apollosai.server.routes.auth import router


@pytest.fixture(autouse=True)
def _reset_limiter_storage():
    """Reset limiter in-memory storage between tests to avoid state bleed."""
    from apollosai.server.rate_limit import limiter

    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture
def app(async_session):
    """Create app with rate limiting enabled."""
    from apollosai.server.deps import get_db_session
    from apollosai.server.rate_limit import limiter

    app = FastAPI()
    app.state.limiter = limiter
    app.add_middleware(
        SessionMiddleware, secret_key='test-session-secret-32-chars!!!!!'
    )
    app.include_router(router)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    async def _override_session():
        yield async_session

    app.dependency_overrides[get_db_session] = _override_session
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def test_login_rate_limited_after_10_requests(client):
    """10 login requests should succeed, 11th should return 429."""
    mock_flow = {
        'auth_uri': 'https://login.microsoftonline.com/test',
        'state': 'test-state',
    }
    with patch('apollosai.server.routes.auth.get_auth_url', return_value=mock_flow):
        for _ in range(10):
            resp = client.get('/auth/login', follow_redirects=False)
            assert resp.status_code in (307, 200)

        resp = client.get('/auth/login', follow_redirects=False)
        assert resp.status_code == 429


def test_logout_rate_limited(client):
    """Logout should also be rate limited."""
    for _ in range(10):
        resp = client.post('/auth/logout')
        assert resp.status_code == 200

    resp = client.post('/auth/logout')
    assert resp.status_code == 429


def test_rate_limit_uses_redis_when_available(monkeypatch):
    """When REDIS_URL is set, limiter should use it."""
    monkeypatch.setenv('REDIS_URL', 'redis://localhost:6379')
    import importlib

    import apollosai.server.rate_limit as rl_mod

    importlib.reload(rl_mod)
    assert rl_mod.limiter._storage_uri == 'redis://localhost:6379'
    # Clean up — reload with no REDIS_URL
    monkeypatch.delenv('REDIS_URL', raising=False)
    importlib.reload(rl_mod)
