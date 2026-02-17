"""Tests for admin audit log routes."""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apollosai.server.routes.admin import _require_admin, router
from apollosai.storage.models.audit_log import AuditAction, AuditLog


def _make_admin_app(async_session, user_id, org_id):
    """Create a FastAPI app with admin auth overrides."""
    from apollosai.server.auth.rbac import AuthedUser
    from apollosai.server.deps import get_db_session

    app = FastAPI()
    app.include_router(router)

    async def _override_session():
        yield async_session

    authed_user = AuthedUser(
        user_id=user_id,
        email='admin@example.com',
        org_id=org_id,
        role_name='admin',
        role_rank=1,
    )

    async def _override_admin(org_id=None, user=None, session=None):
        authed_user.org_id = org_id
        return authed_user

    app.dependency_overrides[get_db_session] = _override_session
    app.dependency_overrides[_require_admin] = _override_admin

    return app


@pytest.mark.asyncio
async def test_list_audit_logs_empty(async_session):
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    from apollosai.storage.models.organization import Organization
    from apollosai.storage.models.user import User

    async_session.add(Organization(id=org_id, name='test-org'))
    async_session.add(User(id=user_id, entra_oid='oid-1'))
    await async_session.flush()

    app = _make_admin_app(async_session, user_id, org_id)
    client = TestClient(app)
    resp = client.get(f'/api/admin/orgs/{org_id}/audit')
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_audit_logs_returns_entries(async_session):
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    from apollosai.storage.models.organization import Organization
    from apollosai.storage.models.user import User

    async_session.add(Organization(id=org_id, name='test-org'))
    async_session.add(User(id=user_id, entra_oid='oid-1', email='a@b.com'))
    await async_session.flush()

    log = AuditLog(
        actor_id=user_id,
        org_id=org_id,
        action=AuditAction.MEMBER_INVITED,
        resource_type='user',
        resource_id=str(uuid.uuid4()),
        details={'role': 'member'},
    )
    async_session.add(log)
    await async_session.commit()

    app = _make_admin_app(async_session, user_id, org_id)
    client = TestClient(app)
    resp = client.get(f'/api/admin/orgs/{org_id}/audit')
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]['action'] == 'member_invited'
    assert data[0]['details'] == {'role': 'member'}


@pytest.mark.asyncio
async def test_list_audit_logs_respects_limit(async_session):
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    from apollosai.storage.models.organization import Organization
    from apollosai.storage.models.user import User

    async_session.add(Organization(id=org_id, name='test-org'))
    async_session.add(User(id=user_id, entra_oid='oid-1'))
    await async_session.flush()

    for i in range(5):
        async_session.add(
            AuditLog(
                actor_id=user_id,
                org_id=org_id,
                action=AuditAction.SETTINGS_UPDATED,
                resource_type='org',
                resource_id=str(org_id),
            )
        )
    await async_session.commit()

    app = _make_admin_app(async_session, user_id, org_id)
    client = TestClient(app)
    resp = client.get(f'/api/admin/orgs/{org_id}/audit?limit=2')
    assert resp.status_code == 200
    assert len(resp.json()) == 2
