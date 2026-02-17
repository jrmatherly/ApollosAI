import uuid

import pytest

from apollosai.monitoring.audit import record_audit
from apollosai.storage.models.audit_log import AuditAction, AuditLog


@pytest.mark.asyncio
async def test_record_audit_creates_entry(async_session):
    from apollosai.storage.models.organization import Organization
    from apollosai.storage.models.user import User

    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    async_session.add(Organization(id=org_id, name='test-org'))
    async_session.add(User(id=user_id, entra_oid='oid-1', email='a@b.com'))
    await async_session.flush()

    log = await record_audit(
        async_session,
        actor_id=user_id,
        org_id=org_id,
        action=AuditAction.MEMBER_INVITED,
        resource_type='user',
        resource_id=str(uuid.uuid4()),
        details={'role': 'member'},
        ip_address='10.0.0.1',
    )

    assert log.id is not None
    assert log.action == AuditAction.MEMBER_INVITED
    assert log.details == {'role': 'member'}
    assert log.ip_address == '10.0.0.1'

    fetched = await async_session.get(AuditLog, log.id)
    assert fetched is not None
    assert fetched.actor_id == user_id


@pytest.mark.asyncio
async def test_record_audit_optional_fields(async_session):
    from apollosai.storage.models.organization import Organization
    from apollosai.storage.models.user import User

    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    async_session.add(Organization(id=org_id, name='test-org'))
    async_session.add(User(id=user_id, entra_oid='oid-2'))
    await async_session.flush()

    log = await record_audit(
        async_session,
        actor_id=user_id,
        org_id=org_id,
        action=AuditAction.SETTINGS_UPDATED,
        resource_type='org',
        resource_id=str(org_id),
    )

    assert log.details is None
    assert log.ip_address is None
