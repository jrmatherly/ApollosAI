import uuid

import pytest

from apollosai.storage.models.audit_log import AuditAction, AuditLog


@pytest.mark.asyncio
async def test_audit_log_create(async_session):
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()

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
        ip_address='127.0.0.1',
    )
    async_session.add(log)
    await async_session.commit()

    fetched = await async_session.get(AuditLog, log.id)
    assert fetched is not None
    assert fetched.action == AuditAction.MEMBER_INVITED
    assert fetched.details == {'role': 'member'}


@pytest.mark.asyncio
async def test_audit_log_system_action_nullable_actor(async_session):
    """System-initiated actions have no actor_id."""
    org_id = uuid.uuid4()

    from apollosai.storage.models.organization import Organization

    async_session.add(Organization(id=org_id, name='test-org'))
    await async_session.flush()

    log = AuditLog(
        actor_id=None,
        org_id=org_id,
        action=AuditAction.SETTINGS_UPDATED,
        resource_type='org',
        resource_id=str(org_id),
    )
    async_session.add(log)
    await async_session.commit()

    fetched = await async_session.get(AuditLog, log.id)
    assert fetched is not None
    assert fetched.actor_id is None
