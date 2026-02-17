"""Tests for Team CRUD routes.

Review fix [M1]: Input validation on team names.
Uses real RBAC chain with DB-seeded roles and monkeypatched auth.
"""

import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apollosai.server.deps import get_db_session
from apollosai.server.routes.teams import router


class _FakeAuth:
    """Fake auth for monkeypatching EntraIDUserAuth."""

    __test__ = False

    def __init__(self, user_id, email='test@example.com'):
        self.user_id = user_id
        self.email = email


async def _seed_admin(session, org_id):
    """Seed org, admin user, and return user_id."""
    from apollosai.storage.models.org_membership import OrgMembership
    from apollosai.storage.models.organization import Organization
    from apollosai.storage.models.role import Role
    from apollosai.storage.models.user import User

    user_id = uuid.uuid4()
    session.add(Organization(id=org_id, name=f'org-{uuid.uuid4().hex[:6]}'))
    role = Role(name='admin', rank=1)
    session.add(role)
    await session.flush()
    session.add(User(id=user_id, entra_oid=f'oid-{uuid.uuid4().hex[:6]}', email='admin@t.com', current_org_id=org_id))
    session.add(OrgMembership(org_id=org_id, user_id=user_id, role_id=role.id))
    await session.commit()
    return user_id


async def _seed_member(session, org_id):
    """Seed org, member user, and return user_id."""
    from apollosai.storage.models.org_membership import OrgMembership
    from apollosai.storage.models.organization import Organization
    from apollosai.storage.models.role import Role
    from apollosai.storage.models.user import User

    user_id = uuid.uuid4()
    # Org may already exist
    from sqlalchemy import select
    existing = await session.get(Organization, org_id)
    if existing is None:
        session.add(Organization(id=org_id, name=f'org-{uuid.uuid4().hex[:6]}'))

    role_result = await session.execute(select(Role).where(Role.name == 'member'))
    role = role_result.scalar_one_or_none()
    if role is None:
        role = Role(name='member', rank=3)
        session.add(role)
        await session.flush()

    session.add(User(id=user_id, entra_oid=f'oid-{uuid.uuid4().hex[:6]}', email='member@t.com', current_org_id=org_id))
    session.add(OrgMembership(org_id=org_id, user_id=user_id, role_id=role.id))
    await session.commit()
    return user_id


def _make_app(async_session):
    """Create FastAPI app with DB session override."""
    from fastapi import Request
    from fastapi.responses import JSONResponse as _JSONResponse

    from apollosai.server.auth.rbac import PermissionDeniedError

    app = FastAPI()
    app.include_router(router)

    @app.exception_handler(PermissionDeniedError)
    async def _perm_handler(request: Request, exc: PermissionDeniedError):
        return _JSONResponse(status_code=403, content={'error': str(exc)})

    async def _override_session():
        yield async_session

    app.dependency_overrides[get_db_session] = _override_session
    return app


@pytest.mark.asyncio
async def test_create_team_as_admin_succeeds(async_session, monkeypatch):
    """POST /api/teams as admin should create a team."""
    org_id = uuid.uuid4()
    user_id = await _seed_admin(async_session, org_id)

    monkeypatch.setattr(
        'apollosai.server.auth.entraid_auth.EntraIDUserAuth',
        type('F', (), {'get_instance': AsyncMock(return_value=_FakeAuth(str(user_id)))}),
    )

    app = _make_app(async_session)
    client = TestClient(app)

    resp = client.post('/api/teams', json={'name': 'Engineering', 'org_id': str(org_id)})
    assert resp.status_code == 200
    data = resp.json()
    assert data['name'] == 'Engineering'


@pytest.mark.asyncio
async def test_create_team_as_member_returns_403(async_session, monkeypatch):
    """POST /api/teams as member (rank 3) should return 403."""
    org_id = uuid.uuid4()
    user_id = await _seed_member(async_session, org_id)

    monkeypatch.setattr(
        'apollosai.server.auth.entraid_auth.EntraIDUserAuth',
        type('F', (), {'get_instance': AsyncMock(return_value=_FakeAuth(str(user_id)))}),
    )

    app = _make_app(async_session)
    client = TestClient(app)

    resp = client.post('/api/teams', json={'name': 'Forbidden', 'org_id': str(org_id)})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_teams_returns_org_teams(async_session, monkeypatch):
    """GET /api/orgs/{org_id}/teams should return teams."""
    from apollosai.storage.models.team import Team

    org_id = uuid.uuid4()
    user_id = await _seed_admin(async_session, org_id)

    async_session.add(Team(id=uuid.uuid4(), org_id=org_id, name='Alpha'))
    async_session.add(Team(id=uuid.uuid4(), org_id=org_id, name='Beta'))
    await async_session.commit()

    monkeypatch.setattr(
        'apollosai.server.auth.entraid_auth.EntraIDUserAuth',
        type('F', (), {'get_instance': AsyncMock(return_value=_FakeAuth(str(user_id)))}),
    )

    app = _make_app(async_session)
    client = TestClient(app)

    resp = client.get(f'/api/orgs/{org_id}/teams')
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    names = {t['name'] for t in data}
    assert names == {'Alpha', 'Beta'}


@pytest.mark.asyncio
async def test_delete_team_removes_memberships(async_session, monkeypatch):
    """DELETE /api/teams/{id} should delete team and memberships."""
    from apollosai.storage.models.role import Role
    from apollosai.storage.models.team import Team
    from apollosai.storage.models.team_membership import TeamMembership
    from apollosai.storage.models.user import User

    org_id = uuid.uuid4()
    team_id = uuid.uuid4()
    user_id = await _seed_admin(async_session, org_id)

    # Get the admin role that was just created
    from sqlalchemy import select
    role_result = await async_session.execute(select(Role).where(Role.name == 'admin'))
    role = role_result.scalar_one()

    async_session.add(Team(id=team_id, org_id=org_id, name='ToDelete'))
    async_session.add(TeamMembership(team_id=team_id, user_id=user_id, role_id=role.id))

    # Update user's current_team_id
    user = await async_session.get(User, user_id)
    user.current_team_id = team_id
    await async_session.commit()

    monkeypatch.setattr(
        'apollosai.server.auth.entraid_auth.EntraIDUserAuth',
        type('F', (), {'get_instance': AsyncMock(return_value=_FakeAuth(str(user_id)))}),
    )

    app = _make_app(async_session)
    client = TestClient(app)

    resp = client.delete(f'/api/teams/{team_id}')
    assert resp.status_code == 200

    team = await async_session.get(Team, team_id)
    assert team is None

    user = await async_session.get(User, user_id)
    assert user.current_team_id is None


@pytest.mark.asyncio
async def test_add_team_member_as_manager_succeeds(async_session, monkeypatch):
    """POST /api/teams/{id}/members should add member."""
    from apollosai.storage.models.org_membership import OrgMembership
    from apollosai.storage.models.organization import Organization
    from apollosai.storage.models.role import Role
    from apollosai.storage.models.team import Team
    from apollosai.storage.models.user import User

    org_id = uuid.uuid4()
    team_id = uuid.uuid4()
    manager_id = uuid.uuid4()
    target_id = uuid.uuid4()

    async_session.add(Organization(id=org_id, name=f'tm-org-{uuid.uuid4().hex[:6]}'))
    role = Role(name='manager', rank=2)
    async_session.add(role)
    await async_session.flush()
    async_session.add(User(id=manager_id, entra_oid='mgr', email='mgr@t.com', current_org_id=org_id))
    async_session.add(User(id=target_id, entra_oid='tgt', email='tgt@t.com'))
    async_session.add(OrgMembership(org_id=org_id, user_id=manager_id, role_id=role.id))
    async_session.add(Team(id=team_id, org_id=org_id, name='DevTeam'))
    await async_session.commit()

    monkeypatch.setattr(
        'apollosai.server.auth.entraid_auth.EntraIDUserAuth',
        type('F', (), {'get_instance': AsyncMock(return_value=_FakeAuth(str(manager_id)))}),
    )

    app = _make_app(async_session)
    client = TestClient(app)

    resp = client.post(
        f'/api/teams/{team_id}/members',
        json={'user_id': str(target_id), 'role': 'member'},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data['role'] == 'member'


@pytest.mark.asyncio
async def test_team_name_validation_rejects_special_chars(async_session, monkeypatch):
    """Team names with XSS should be rejected."""
    org_id = uuid.uuid4()
    user_id = await _seed_admin(async_session, org_id)

    monkeypatch.setattr(
        'apollosai.server.auth.entraid_auth.EntraIDUserAuth',
        type('F', (), {'get_instance': AsyncMock(return_value=_FakeAuth(str(user_id)))}),
    )

    app = _make_app(async_session)
    client = TestClient(app)

    resp = client.post('/api/teams', json={'name': '<script>', 'org_id': str(org_id)})
    assert resp.status_code == 422
