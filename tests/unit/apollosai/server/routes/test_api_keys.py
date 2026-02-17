"""Tests for API key management routes.

Review fix [H4-test]: Full route tests with FastAPI TestClient.
Review fix [H3]: Routes now use require_role('member') via org_id path param.
"""

import uuid
from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apollosai.server.routes.api_keys import _require_member, router


@dataclass
class _FakeUser:
    """Fake AuthedUser returned by the overridden RBAC dependency."""

    __test__ = False
    user_id: uuid.UUID
    email: str | None = 'test@example.com'
    org_id: uuid.UUID | None = None
    role_name: str | None = 'member'
    role_rank: int | None = 3


def _make_app(async_session, user_id: uuid.UUID | None = None):
    """Create a FastAPI app with test overrides."""
    app = FastAPI()
    app.include_router(router)

    async def _override_session():
        yield async_session

    from apollosai.server.deps import get_db_session

    app.dependency_overrides[get_db_session] = _override_session

    if user_id is not None:
        fake_user = _FakeUser(user_id=user_id)

        async def _override_member():
            return fake_user

        app.dependency_overrides[_require_member] = _override_member

    return app


@pytest.mark.asyncio
async def test_create_key_returns_plaintext(async_session):
    """POST /api/orgs/{org_id}/keys should return the key plaintext once."""
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()

    app = _make_app(async_session, user_id=user_id)
    client = TestClient(app)

    resp = client.post(f'/api/orgs/{org_id}/keys', json={'name': 'test-key'})
    assert resp.status_code == 200
    data = resp.json()
    assert data['key'].startswith('sk-aai-')
    assert data['name'] == 'test-key'


@pytest.mark.asyncio
async def test_list_keys_returns_metadata_only(async_session):
    """GET /api/orgs/{org_id}/keys should return prefix + name, not hash/salt."""
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()

    app = _make_app(async_session, user_id=user_id)
    client = TestClient(app)

    # Create a key first via the service directly
    from apollosai.storage.services.api_key_service import create_api_key

    await create_api_key(async_session, user_id=user_id, org_id=org_id, name='my-key')

    resp = client.get(f'/api/orgs/{org_id}/keys')
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert 'key_hash' not in data[0]
    assert 'salt' not in data[0]
    assert data[0]['name'] == 'my-key'


@pytest.mark.asyncio
async def test_delete_key_revokes(async_session):
    """DELETE /api/orgs/{org_id}/keys/{key_id} should revoke the key."""
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()

    app = _make_app(async_session, user_id=user_id)
    client = TestClient(app)

    from apollosai.storage.services.api_key_service import (
        create_api_key,
        verify_api_key,
    )

    raw_key, record = await create_api_key(
        async_session,
        user_id=user_id,
        org_id=org_id,
        name='del-key',
    )

    resp = client.delete(f'/api/orgs/{org_id}/keys/{record.id}')
    assert resp.status_code == 200
    assert resp.json()['status'] == 'revoked'

    # Verify key no longer works
    result = await verify_api_key(async_session, raw_key)
    assert result is None
