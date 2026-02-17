"""RBAC dependency tests — review fix [C4-test]: comprehensive edge cases."""

import uuid

import pytest

from apollosai.server.auth.rbac import (
    AuthedUser,
    DEV_MODE_USER_ID,
    PermissionDeniedError,
    require_role,
)


async def _seed_user_with_role(session, role_name, role_rank, entra_oid, email):
    """Helper: create org + user + role + membership, return (org_id, user_id)."""
    from apollosai.storage.models.org_membership import OrgMembership
    from apollosai.storage.models.organization import Organization
    from apollosai.storage.models.role import Role
    from apollosai.storage.models.user import User

    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    session.add(Organization(id=org_id, name=f'org-{entra_oid}'))
    role = Role(name=role_name, rank=role_rank)
    session.add(role)
    await session.flush()  # Populate role.id (autoincrement)

    session.add(User(
        id=user_id, entra_oid=entra_oid, email=email, current_org_id=org_id,
    ))
    session.add(OrgMembership(org_id=org_id, user_id=user_id, role_id=role.id))
    await session.commit()
    return org_id, user_id


def test_permission_denied_error_is_auth_error():
    """PermissionDeniedError should be a subclass of AuthError."""
    from apollosai.server.auth.auth_error import AuthError
    assert issubclass(PermissionDeniedError, AuthError)


def test_dev_mode_user_id_is_zero_uuid():
    """DEV_MODE_USER_ID should be the well-known zero UUID."""
    assert DEV_MODE_USER_ID == uuid.UUID('00000000-0000-0000-0000-000000000000')


def test_authed_user_dataclass_fields():
    """AuthedUser should have the required fields."""
    user = AuthedUser(
        user_id=uuid.uuid4(), email='test@example.com',
        org_id=uuid.uuid4(), role_name='owner', role_rank=0,
    )
    assert user.email == 'test@example.com'
    assert user.role_name == 'owner'
    assert user.role_rank == 0


@pytest.mark.asyncio
async def test_owner_passes_admin_check(async_session):
    """rank 0 <= 1 should pass."""
    org_id, user_id = await _seed_user_with_role(
        async_session, 'owner', 0, 'oid-1', 'owner@test.com',
    )
    checker = require_role('admin')
    authed = AuthedUser(
        user_id=user_id, email='owner@test.com', org_id=None, role_name=None, role_rank=None,
    )
    result = await checker(org_id=org_id, user=authed, session=async_session)
    assert result.role_name == 'owner'
    assert result.role_rank == 0


@pytest.mark.asyncio
async def test_admin_passes_admin_check(async_session):
    """rank 1 <= 1 should pass."""
    org_id, user_id = await _seed_user_with_role(
        async_session, 'admin', 1, 'oid-2', 'admin@test.com',
    )
    checker = require_role('admin')
    authed = AuthedUser(
        user_id=user_id, email='admin@test.com', org_id=None, role_name=None, role_rank=None,
    )
    result = await checker(org_id=org_id, user=authed, session=async_session)
    assert result.role_name == 'admin'
    assert result.role_rank == 1


@pytest.mark.asyncio
async def test_manager_fails_admin_check(async_session):
    """rank 2 > 1 should raise PermissionDeniedError."""
    org_id, user_id = await _seed_user_with_role(
        async_session, 'manager', 2, 'oid-3', 'mgr@test.com',
    )
    checker = require_role('admin')
    authed = AuthedUser(
        user_id=user_id, email='mgr@test.com', org_id=None, role_name=None, role_rank=None,
    )
    with pytest.raises(PermissionDeniedError, match='Requires admin'):
        await checker(org_id=org_id, user=authed, session=async_session)


@pytest.mark.asyncio
async def test_member_fails_admin_check(async_session):
    """rank 3 > 1 should raise PermissionDeniedError."""
    org_id, user_id = await _seed_user_with_role(
        async_session, 'member', 3, 'oid-4', 'member@test.com',
    )
    checker = require_role('admin')
    authed = AuthedUser(
        user_id=user_id, email='member@test.com', org_id=None, role_name=None, role_rank=None,
    )
    with pytest.raises(PermissionDeniedError):
        await checker(org_id=org_id, user=authed, session=async_session)


@pytest.mark.asyncio
async def test_non_member_raises_permission_denied(async_session):
    """User not in org should get PermissionDeniedError."""
    from apollosai.storage.models.organization import Organization

    org_id = uuid.uuid4()
    async_session.add(Organization(id=org_id, name='other-org'))
    await async_session.commit()

    checker = require_role('member')
    authed = AuthedUser(
        user_id=uuid.uuid4(), email='nobody@test.com',
        org_id=None, role_name=None, role_rank=None,
    )
    with pytest.raises(PermissionDeniedError, match='Not a member'):
        await checker(org_id=org_id, user=authed, session=async_session)


@pytest.mark.asyncio
async def test_user_in_org_a_cannot_access_org_b(async_session):
    """Review fix [C4-test]: Cross-org access must be denied."""
    from apollosai.storage.models.org_membership import OrgMembership
    from apollosai.storage.models.organization import Organization
    from apollosai.storage.models.role import Role
    from apollosai.storage.models.user import User

    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    user_id = uuid.uuid4()

    async_session.add(Organization(id=org_a, name='org-a'))
    async_session.add(Organization(id=org_b, name='org-b'))
    role = Role(name='owner', rank=0)
    async_session.add(role)
    await async_session.flush()

    async_session.add(User(
        id=user_id, entra_oid='oid-x', email='x@test.com', current_org_id=org_a,
    ))
    async_session.add(OrgMembership(org_id=org_a, user_id=user_id, role_id=role.id))
    await async_session.commit()

    checker = require_role('member')
    authed = AuthedUser(
        user_id=user_id, email='x@test.com', org_id=None, role_name=None, role_rank=None,
    )
    with pytest.raises(PermissionDeniedError, match='Not a member'):
        await checker(org_id=org_b, user=authed, session=async_session)


@pytest.mark.asyncio
async def test_require_auth_with_no_user_id_raises(monkeypatch):
    """Review fix [C4]: Missing user_id should raise, not fabricate UUID."""
    from unittest.mock import AsyncMock, MagicMock

    from apollosai.server.auth.auth_error import NoCredentialsError
    from apollosai.server.auth.rbac import require_auth

    class _FakeAuth:
        __test__ = False
        user_id = None
        email = None

    monkeypatch.setattr(
        'apollosai.server.auth.entraid_auth.EntraIDUserAuth',
        type('FakeAuth', (), {'get_instance': AsyncMock(return_value=_FakeAuth())}),
    )
    monkeypatch.delenv('APOLLOSAI_ALLOW_UNAUTHENTICATED', raising=False)

    with pytest.raises(NoCredentialsError):
        await require_auth(request=MagicMock())


@pytest.mark.asyncio
async def test_require_auth_dev_mode_uses_sentinel(monkeypatch):
    """Review fix [C4]: Dev mode should use DEV_MODE_USER_ID, not random."""
    from unittest.mock import AsyncMock, MagicMock

    from apollosai.server.auth.rbac import require_auth

    class _FakeAuth:
        __test__ = False
        user_id = None
        email = None

    monkeypatch.setattr(
        'apollosai.server.auth.entraid_auth.EntraIDUserAuth',
        type('FakeAuth', (), {'get_instance': AsyncMock(return_value=_FakeAuth())}),
    )
    monkeypatch.setenv('APOLLOSAI_ALLOW_UNAUTHENTICATED', '1')

    result = await require_auth(request=MagicMock())
    assert result.user_id == DEV_MODE_USER_ID
    assert result.email == 'dev@localhost'
