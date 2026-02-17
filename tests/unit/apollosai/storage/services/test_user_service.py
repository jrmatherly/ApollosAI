"""Tests for user lifecycle operations — upsert on login.

Review fix [H3]: Must verify OrgMembership is created with owner role.
Review fix [C6]: Org name collision DoS prevented with UUID suffix.
"""

import pytest

from apollosai.storage.services.user_service import upsert_user_on_login


@pytest.mark.asyncio
async def test_upsert_user_creates_new_user(async_session):
    """First login should create User + default Org + OrgMembership."""
    user = await upsert_user_on_login(
        session=async_session,
        entra_oid='test-oid-123',
        email='test@example.com',
        display_name='Test User',
    )
    assert user is not None
    assert user.entra_oid == 'test-oid-123'
    assert user.current_org_id is not None  # Default org created


@pytest.mark.asyncio
async def test_upsert_user_updates_existing(async_session):
    """Second login should update email, not create duplicate."""
    user1 = await upsert_user_on_login(
        session=async_session,
        entra_oid='test-oid-123',
        email='old@example.com',
        display_name='Test User',
    )
    user2 = await upsert_user_on_login(
        session=async_session,
        entra_oid='test-oid-123',
        email='new@example.com',
        display_name='Test User Updated',
    )
    assert user1.id == user2.id
    assert user2.email == 'new@example.com'


@pytest.mark.asyncio
async def test_upsert_creates_org_membership_with_owner_role(async_session):
    """Review fix [H3]: User must get OrgMembership with owner role on first login."""
    user = await upsert_user_on_login(
        session=async_session, entra_oid='oid-1', email='test@example.com',
    )
    from sqlalchemy import select
    from apollosai.storage.models.org_membership import OrgMembership
    from apollosai.storage.models.role import Role

    stmt = select(OrgMembership).where(OrgMembership.user_id == user.id)
    result = await async_session.execute(stmt)
    membership = result.scalar_one()
    role = await async_session.get(Role, membership.role_id)
    assert role.name == 'owner'
