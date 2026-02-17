"""Tests for API key CRUD and HMAC-SHA256 verification.

Review fixes incorporated:
- [C3]: Timing-safe comparison via hmac.compare_digest
- [C3-test]: Unique salt per key, source inspection for compare_digest
"""

import uuid

import pytest


@pytest.mark.asyncio
async def test_create_and_verify_roundtrip(async_session):
    """Create key then verify it should succeed."""
    from apollosai.storage.services.api_key_service import create_api_key, verify_api_key

    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    raw_key, record = await create_api_key(
        async_session, user_id=user_id, org_id=org_id, name='test-key',
    )
    assert raw_key.startswith('sk-aai-')
    result = await verify_api_key(async_session, raw_key)
    assert result is not None
    assert result.user_id == user_id


@pytest.mark.asyncio
async def test_revoked_key_verify_returns_none(async_session):
    """Revoked key (is_active=False) must not authenticate."""
    from apollosai.storage.services.api_key_service import (
        create_api_key,
        revoke_api_key,
        verify_api_key,
    )

    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    raw_key, record = await create_api_key(
        async_session, user_id=user_id, org_id=org_id, name='revokable',
    )
    await revoke_api_key(async_session, record.id, user_id=user_id)
    result = await verify_api_key(async_session, raw_key)
    assert result is None


@pytest.mark.asyncio
async def test_verify_nonexistent_prefix_returns_none(async_session):
    """Prefix not in DB should return None, not raise."""
    from apollosai.storage.services.api_key_service import verify_api_key

    result = await verify_api_key(async_session, 'sk-aai-nonexistentprefix12345')
    assert result is None


@pytest.mark.asyncio
async def test_two_keys_same_user_have_different_salts(async_session):
    """Review fix [C3-test]: Each key must have unique salt."""
    from apollosai.storage.services.api_key_service import create_api_key

    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    _, k1 = await create_api_key(async_session, user_id=user_id, org_id=org_id, name='k1')
    _, k2 = await create_api_key(async_session, user_id=user_id, org_id=org_id, name='k2')
    assert k1.salt != k2.salt


def test_verify_uses_timing_safe_comparison():
    """Review fix [C3-test]: HMAC comparison must use hmac.compare_digest."""
    import inspect

    from apollosai.storage.services.api_key_service import verify_api_key

    source = inspect.getsource(verify_api_key)
    assert 'compare_digest' in source, 'Must use hmac.compare_digest for timing safety'


@pytest.mark.asyncio
async def test_list_api_keys_returns_prefix_and_name(async_session):
    """list_api_keys should return metadata, never the hash or salt."""
    from apollosai.storage.services.api_key_service import create_api_key, list_api_keys

    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    await create_api_key(async_session, user_id=user_id, org_id=org_id, name='my-key')
    keys = await list_api_keys(async_session, user_id=user_id, org_id=org_id)
    assert len(keys) == 1
    assert keys[0].name == 'my-key'
    assert keys[0].prefix.startswith('sk-aai-')


@pytest.mark.asyncio
async def test_revoke_wrong_user_raises(async_session):
    """Cannot revoke another user's key."""
    from apollosai.storage.services.api_key_service import create_api_key, revoke_api_key

    user_id = uuid.uuid4()
    other_user = uuid.uuid4()
    org_id = uuid.uuid4()
    _, record = await create_api_key(
        async_session, user_id=user_id, org_id=org_id, name='protected',
    )
    with pytest.raises(PermissionError):
        await revoke_api_key(async_session, record.id, user_id=other_user)


@pytest.mark.asyncio
async def test_list_excludes_revoked_keys(async_session):
    """Revoked keys should not appear in list."""
    from apollosai.storage.services.api_key_service import (
        create_api_key,
        list_api_keys,
        revoke_api_key,
    )

    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    await create_api_key(async_session, user_id=user_id, org_id=org_id, name='active')
    _, revokable = await create_api_key(
        async_session, user_id=user_id, org_id=org_id, name='revokable',
    )
    await revoke_api_key(async_session, revokable.id, user_id=user_id)
    keys = await list_api_keys(async_session, user_id=user_id, org_id=org_id)
    assert len(keys) == 1
    assert keys[0].name == 'active'
