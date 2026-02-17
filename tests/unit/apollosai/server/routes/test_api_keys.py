"""Tests for API key management routes.

Review fix [H4-test]: Full route tests with FastAPI TestClient.
"""

import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apollosai.server.routes.api_keys import router


class _FakeAuth:
    """Fake auth instance for testing."""

    __test__ = False

    def __init__(self, user_id=None, email='test@example.com'):
        self.user_id = user_id
        self.email = email


def _make_app(async_session):
    """Create a FastAPI app with test overrides."""
    app = FastAPI()
    app.include_router(router)

    async def _override_session():
        yield async_session

    from apollosai.server.deps import get_db_session
    app.dependency_overrides[get_db_session] = _override_session

    return app


@pytest.mark.asyncio
async def test_create_key_returns_plaintext(async_session, monkeypatch):
    """POST /api/keys should return the key plaintext once."""
    user_id = str(uuid.uuid4())
    fake_auth = _FakeAuth(user_id=user_id)

    # Monkeypatch at the source module (lazy import target)
    fake_cls = type('FakeAuth', (), {'get_instance': AsyncMock(return_value=fake_auth)})
    monkeypatch.setattr(
        'apollosai.server.auth.entraid_auth.EntraIDUserAuth', fake_cls,
    )

    app = _make_app(async_session)
    client = TestClient(app)

    org_id = str(uuid.uuid4())
    resp = client.post('/api/keys', json={'name': 'test-key', 'org_id': org_id})
    assert resp.status_code == 200
    data = resp.json()
    assert data['key'].startswith('sk-aai-')
    assert data['name'] == 'test-key'


@pytest.mark.asyncio
async def test_list_keys_returns_metadata_only(async_session, monkeypatch):
    """GET /api/keys should return prefix + name, not hash/salt."""
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    fake_auth = _FakeAuth(user_id=str(user_id))
    fake_cls = type('FakeAuth', (), {'get_instance': AsyncMock(return_value=fake_auth)})
    monkeypatch.setattr(
        'apollosai.server.auth.entraid_auth.EntraIDUserAuth', fake_cls,
    )

    app = _make_app(async_session)
    client = TestClient(app)

    # Create a key first via the service directly
    from apollosai.storage.services.api_key_service import create_api_key
    await create_api_key(async_session, user_id=user_id, org_id=org_id, name='my-key')

    resp = client.get(f'/api/keys?org_id={org_id}')
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert 'key_hash' not in data[0]
    assert 'salt' not in data[0]
    assert data[0]['name'] == 'my-key'


@pytest.mark.asyncio
async def test_delete_key_revokes(async_session, monkeypatch):
    """DELETE /api/keys/{key_id} should revoke the key."""
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    fake_auth = _FakeAuth(user_id=str(user_id))
    fake_cls = type('FakeAuth', (), {'get_instance': AsyncMock(return_value=fake_auth)})
    monkeypatch.setattr(
        'apollosai.server.auth.entraid_auth.EntraIDUserAuth', fake_cls,
    )

    app = _make_app(async_session)
    client = TestClient(app)

    from apollosai.storage.services.api_key_service import create_api_key, verify_api_key
    raw_key, record = await create_api_key(
        async_session, user_id=user_id, org_id=org_id, name='del-key',
    )

    resp = client.delete(f'/api/keys/{record.id}')
    assert resp.status_code == 200
    assert resp.json()['status'] == 'revoked'

    # Verify key no longer works
    result = await verify_api_key(async_session, raw_key)
    assert result is None


@pytest.mark.asyncio
async def test_unauthenticated_returns_401(async_session, monkeypatch):
    """Unauthenticated requests should get 401."""
    fake_auth = _FakeAuth(user_id=None)
    fake_cls = type('FakeAuth', (), {'get_instance': AsyncMock(return_value=fake_auth)})
    monkeypatch.setattr(
        'apollosai.server.auth.entraid_auth.EntraIDUserAuth', fake_cls,
    )

    app = _make_app(async_session)
    client = TestClient(app)

    resp = client.post('/api/keys', json={'name': 'test', 'org_id': str(uuid.uuid4())})
    assert resp.status_code == 401
