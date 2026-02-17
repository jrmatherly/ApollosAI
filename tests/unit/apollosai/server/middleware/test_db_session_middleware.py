"""Tests for DB-backed server-side session middleware."""

import json

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from apollosai.server.middleware.db_session_middleware import (
    DBSessionMiddleware,
)


def _make_app(async_session):
    """Create a minimal FastAPI app with DB session middleware."""
    app = FastAPI()

    app.add_middleware(
        DBSessionMiddleware,
        session_factory=lambda: async_session,
        max_age=3600,
    )

    @app.get('/set')
    async def set_session(request: Request, key: str, value: str):
        request.state.session[key] = value
        return {'ok': True}

    @app.get('/get')
    async def get_session(request: Request, key: str):
        return {'value': request.state.session.get(key)}

    @app.get('/clear')
    async def clear_session(request: Request):
        request.state.session.clear()
        return {'ok': True}

    return app


def test_new_request_creates_session(async_session):
    """First request should create a session and set a cookie."""
    app = _make_app(async_session)
    client = TestClient(app)

    resp = client.get('/set?key=foo&value=bar')
    assert resp.status_code == 200

    # Check that a session cookie was set
    cookies = resp.cookies
    assert 'session_id' in cookies


def test_session_data_persists_across_requests(async_session):
    """Data set in one request should be readable in the next."""
    app = _make_app(async_session)
    client = TestClient(app)

    # Set a value
    resp1 = client.get('/set?key=greeting&value=hello')
    assert resp1.status_code == 200

    # Read it back in a new request (same client preserves cookies)
    resp2 = client.get('/get?key=greeting')
    assert resp2.status_code == 200
    assert resp2.json()['value'] == 'hello'


def test_expired_session_returns_empty(async_session, monkeypatch):
    """An expired session should return empty data."""
    import time

    app = _make_app(async_session)
    client = TestClient(app)

    # Set a value
    resp1 = client.get('/set?key=temp&value=data')
    assert resp1.status_code == 200

    # Advance time past max_age (3600s)
    original_time = time.time
    monkeypatch.setattr('time.time', lambda: original_time() + 7200)

    # Read it back — should be empty since session expired
    resp2 = client.get('/get?key=temp')
    assert resp2.status_code == 200
    assert resp2.json()['value'] is None


def test_session_cookie_is_httponly(async_session):
    """Session cookie must be HttpOnly."""
    app = _make_app(async_session)
    client = TestClient(app)

    resp = client.get('/set?key=a&value=b')
    set_cookie = resp.headers.get('set-cookie', '')
    assert 'httponly' in set_cookie.lower()


def test_invalid_session_id_returns_empty_session(async_session):
    """A request with a bogus session_id cookie should get an empty session."""
    app = _make_app(async_session)
    client = TestClient(app, cookies={'session_id': 'bogus-nonexistent-id'})

    resp = client.get('/get?key=anything')
    assert resp.status_code == 200
    assert resp.json()['value'] is None


def test_session_id_is_cryptographically_random(async_session):
    """Session IDs must be long and random (secrets.token_urlsafe)."""
    app = _make_app(async_session)
    client = TestClient(app)

    resp = client.get('/set?key=x&value=y')
    session_id = resp.cookies.get('session_id', '')
    # token_urlsafe(32) produces ~43 characters
    assert len(session_id) >= 32


def test_clear_session_empties_data(async_session):
    """Clearing a session should remove all data."""
    app = _make_app(async_session)
    client = TestClient(app)

    client.get('/set?key=secret&value=data')
    client.get('/clear')

    resp = client.get('/get?key=secret')
    assert resp.json()['value'] is None
