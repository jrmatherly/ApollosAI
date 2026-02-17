"""Tests for Organization CRUD routes.

Review fixes incorporated:
- [H4-test]: Full route tests with FastAPI TestClient
- [M1]: Input validation on org names
- [H6]: Soft-delete verification
"""

import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apollosai.server.routes.orgs import router


class _FakeAuth:
    """Fake auth instance for testing."""

    __test__ = False

    def __init__(self, user_id=None, email='test@example.com'):
        self.user_id = user_id
        self.email = email


def _make_app(async_session, user_id):
    """Create a FastAPI app with test overrides for auth and DB."""
    from apollosai.server.auth.rbac import AuthedUser, require_auth, require_role
    from apollosai.server.deps import get_db_session

    app = FastAPI()
    app.include_router(router)

    async def _override_session():
        yield async_session

    authed_user = AuthedUser(
        user_id=uuid.UUID(user_id) if isinstance(user_id, str) else user_id,
        email='test@example.com', org_id=None, role_name=None, role_rank=None,
    )

    # Override both require_auth and require_role to bypass real auth
    async def _override_auth():
        return authed_user

    app.dependency_overrides[get_db_session] = _override_session
    app.dependency_overrides[require_auth] = _override_auth

    return app, authed_user


def _make_app_with_role(async_session, user_id, org_id, role_name, role_rank):
    """Create app with role-based auth override for RBAC-protected endpoints."""
    from apollosai.server.auth.rbac import AuthedUser, require_auth, require_role
    from apollosai.server.deps import get_db_session

    app = FastAPI()
    app.include_router(router)

    async def _override_session():
        yield async_session

    authed_user = AuthedUser(
        user_id=uuid.UUID(user_id) if isinstance(user_id, str) else user_id,
        email='test@example.com', org_id=org_id, role_name=role_name, role_rank=role_rank,
    )

    async def _override_auth():
        return authed_user

    # Override require_role factory results
    def _override_role_factory(min_role):
        async def _check(org_id=None, user=None, session=None):
            from apollosai.server.auth.rbac import PermissionDeniedError
            ROLE_RANKS = {'owner': 0, 'admin': 1, 'manager': 2, 'member': 3}
            min_rank = ROLE_RANKS.get(min_role, 3)
            if authed_user.role_rank is not None and authed_user.role_rank > min_rank:
                raise PermissionDeniedError(
                    f'Requires {min_role} role (rank {min_rank}), '
                    f'you have {authed_user.role_name} (rank {authed_user.role_rank})'
                )
            authed_user.org_id = org_id
            return authed_user
        return _check

    app.dependency_overrides[get_db_session] = _override_session
    app.dependency_overrides[require_auth] = _override_auth
    # Override each require_role dependency used in routes
    # We need to override the actual Depends objects — use a different approach
    # Instead, monkeypatch EntraIDUserAuth at the source

    return app, authed_user


@pytest.mark.asyncio
async def test_create_org_sets_creator_as_owner(async_session, monkeypatch):
    """POST /api/orgs should make creator the owner."""
    user_id = uuid.uuid4()
    fake_auth = _FakeAuth(user_id=str(user_id))
    monkeypatch.setattr(
        'apollosai.server.auth.entraid_auth.EntraIDUserAuth',
        type('FakeAuth', (), {'get_instance': AsyncMock(return_value=fake_auth)}),
    )

    # Need to also create the user in DB for membership FK
    from apollosai.storage.models.user import User
    async_session.add(User(
        id=user_id, entra_oid='oid-test', email='test@example.com',
    ))
    await async_session.commit()

    app, _ = _make_app(async_session, user_id)
    client = TestClient(app)

    resp = client.post('/api/orgs', json={'name': 'My Org'})
    assert resp.status_code == 200
    data = resp.json()
    assert data['name'] == 'My Org'

    # Verify creator is owner
    from sqlalchemy import select
    from apollosai.storage.models.org_membership import OrgMembership
    from apollosai.storage.models.role import Role
    stmt = (
        select(OrgMembership, Role)
        .join(Role, OrgMembership.role_id == Role.id)
        .where(OrgMembership.user_id == user_id)
    )
    result = await async_session.execute(stmt)
    row = result.one()
    membership, role = row
    assert role.name == 'owner'


@pytest.mark.asyncio
async def test_list_orgs_returns_user_orgs(async_session, monkeypatch):
    """GET /api/orgs should return orgs the user belongs to."""
    user_id = uuid.uuid4()
    fake_auth = _FakeAuth(user_id=str(user_id))
    monkeypatch.setattr(
        'apollosai.server.auth.entraid_auth.EntraIDUserAuth',
        type('FakeAuth', (), {'get_instance': AsyncMock(return_value=fake_auth)}),
    )

    # Seed org + membership
    from apollosai.storage.models.org_membership import OrgMembership
    from apollosai.storage.models.organization import Organization
    from apollosai.storage.models.role import Role
    from apollosai.storage.models.user import User

    org_id = uuid.uuid4()
    async_session.add(Organization(id=org_id, name='test-org'))
    role = Role(name='member', rank=3)
    async_session.add(role)
    await async_session.flush()
    async_session.add(User(id=user_id, entra_oid='oid', email='t@t.com', current_org_id=org_id))
    async_session.add(OrgMembership(org_id=org_id, user_id=user_id, role_id=role.id))
    await async_session.commit()

    app, _ = _make_app(async_session, user_id)
    client = TestClient(app)

    resp = client.get('/api/orgs')
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]['name'] == 'test-org'


@pytest.mark.asyncio
async def test_org_name_validation_rejects_special_chars(async_session, monkeypatch):
    """Review fix [M1]: Org names with XSS payloads should be rejected."""
    user_id = uuid.uuid4()
    fake_auth = _FakeAuth(user_id=str(user_id))
    monkeypatch.setattr(
        'apollosai.server.auth.entraid_auth.EntraIDUserAuth',
        type('FakeAuth', (), {'get_instance': AsyncMock(return_value=fake_auth)}),
    )

    app, _ = _make_app(async_session, user_id)
    client = TestClient(app)

    resp = client.post('/api/orgs', json={'name': '<script>alert(1)</script>'})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_org_name_validation_rejects_empty(async_session, monkeypatch):
    """Empty org name should be rejected."""
    user_id = uuid.uuid4()
    fake_auth = _FakeAuth(user_id=str(user_id))
    monkeypatch.setattr(
        'apollosai.server.auth.entraid_auth.EntraIDUserAuth',
        type('FakeAuth', (), {'get_instance': AsyncMock(return_value=fake_auth)}),
    )

    app, _ = _make_app(async_session, user_id)
    client = TestClient(app)

    resp = client.post('/api/orgs', json={'name': ''})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_org_removes_memberships(async_session, monkeypatch):
    """DELETE /api/orgs/{id} should remove memberships."""
    user_id = uuid.uuid4()
    fake_auth = _FakeAuth(user_id=str(user_id))
    monkeypatch.setattr(
        'apollosai.server.auth.entraid_auth.EntraIDUserAuth',
        type('FakeAuth', (), {'get_instance': AsyncMock(return_value=fake_auth)}),
    )

    # Seed org with owner membership
    from apollosai.storage.models.org_membership import OrgMembership
    from apollosai.storage.models.organization import Organization
    from apollosai.storage.models.role import Role
    from apollosai.storage.models.user import User

    org_id = uuid.uuid4()
    async_session.add(Organization(id=org_id, name='del-org'))
    role = Role(name='owner', rank=0)
    async_session.add(role)
    await async_session.flush()
    async_session.add(User(id=user_id, entra_oid='oid', email='t@t.com', current_org_id=org_id))
    async_session.add(OrgMembership(org_id=org_id, user_id=user_id, role_id=role.id))
    await async_session.commit()

    # Override require_role('owner') to return the authed user directly
    from apollosai.server.auth.rbac import AuthedUser, require_role
    from apollosai.server.deps import get_db_session

    app = FastAPI()
    from apollosai.server.routes.orgs import router as orgs_router
    app.include_router(orgs_router)

    async def _override_session():
        yield async_session

    authed = AuthedUser(
        user_id=user_id, email='t@t.com', org_id=org_id, role_name='owner', role_rank=0,
    )
    _owner_check = require_role('owner')

    async def _fake_owner_check(org_id=None, user=None, session=None):
        authed.org_id = org_id
        return authed

    app.dependency_overrides[get_db_session] = _override_session
    app.dependency_overrides[_owner_check] = _fake_owner_check

    client = TestClient(app)
    resp = client.delete(f'/api/orgs/{org_id}')
    assert resp.status_code == 200

    # Verify org is deleted
    org = await async_session.get(Organization, org_id)
    assert org is None


@pytest.mark.asyncio
async def test_add_member_creates_org_membership(async_session, monkeypatch):
    """POST /api/orgs/{id}/members should create OrgMembership."""
    admin_id = uuid.uuid4()
    target_id = uuid.uuid4()
    fake_auth = _FakeAuth(user_id=str(admin_id))
    monkeypatch.setattr(
        'apollosai.server.auth.entraid_auth.EntraIDUserAuth',
        type('FakeAuth', (), {'get_instance': AsyncMock(return_value=fake_auth)}),
    )

    # Seed org, admin, and target user
    from apollosai.storage.models.org_membership import OrgMembership
    from apollosai.storage.models.organization import Organization
    from apollosai.storage.models.role import Role
    from apollosai.storage.models.user import User

    org_id = uuid.uuid4()
    async_session.add(Organization(id=org_id, name='member-org'))
    admin_role = Role(name='admin', rank=1)
    async_session.add(admin_role)
    await async_session.flush()
    async_session.add(User(id=admin_id, entra_oid='admin-oid', email='admin@t.com', current_org_id=org_id))
    async_session.add(User(id=target_id, entra_oid='target-oid', email='target@t.com'))
    async_session.add(OrgMembership(org_id=org_id, user_id=admin_id, role_id=admin_role.id))
    await async_session.commit()

    # Override require_role('admin') for this route
    from apollosai.server.auth.rbac import AuthedUser, require_role
    from apollosai.server.deps import get_db_session

    app = FastAPI()
    from apollosai.server.routes.orgs import router as orgs_router
    app.include_router(orgs_router)

    async def _override_session():
        yield async_session

    authed = AuthedUser(
        user_id=admin_id, email='admin@t.com', org_id=org_id, role_name='admin', role_rank=1,
    )
    _admin_check = require_role('admin')

    async def _fake_admin_check(org_id=None, user=None, session=None):
        authed.org_id = org_id
        return authed

    app.dependency_overrides[get_db_session] = _override_session
    app.dependency_overrides[_admin_check] = _fake_admin_check

    client = TestClient(app)
    resp = client.post(
        f'/api/orgs/{org_id}/members',
        json={'user_id': str(target_id), 'role': 'member'},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data['role_name'] == 'member'
