"""Tests for MSAL token cache persistence.

Review fix [H5]: Full test code required for token cache persistence.
"""

import uuid

import pytest


@pytest.mark.asyncio
async def test_save_and_load_token_cache_roundtrip(async_session, monkeypatch):
    """Token cache should survive encrypt -> store -> load -> decrypt."""
    monkeypatch.setenv('APOLLOSAI_ENCRYPTION_KEY', 'a' * 32)
    from apollosai.storage.encrypt_utils import reset_key_cache

    reset_key_cache()
    from apollosai.storage.services.token_cache_service import (
        load_token_cache,
        save_token_cache,
    )

    user_id = uuid.uuid4()
    await save_token_cache(async_session, user_id, '{"AccessToken": {"key": "value"}}')
    loaded = await load_token_cache(async_session, user_id)
    assert loaded == '{"AccessToken": {"key": "value"}}'


@pytest.mark.asyncio
async def test_load_nonexistent_cache_returns_none(async_session):
    """No cached token should return None, not raise."""
    from apollosai.storage.services.token_cache_service import load_token_cache

    result = await load_token_cache(async_session, uuid.uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_save_overwrites_existing_cache(async_session, monkeypatch):
    """Second save should update, not create a duplicate."""
    monkeypatch.setenv('APOLLOSAI_ENCRYPTION_KEY', 'a' * 32)
    from apollosai.storage.encrypt_utils import reset_key_cache

    reset_key_cache()
    from apollosai.storage.services.token_cache_service import (
        load_token_cache,
        save_token_cache,
    )

    user_id = uuid.uuid4()
    await save_token_cache(async_session, user_id, '{"v": 1}')
    await save_token_cache(async_session, user_id, '{"v": 2}')
    loaded = await load_token_cache(async_session, user_id)
    assert '"v": 2' in loaded


@pytest.mark.asyncio
async def test_cache_encrypted_at_rest(async_session, monkeypatch):
    """Raw DB value should not equal plaintext (encryption verified)."""
    monkeypatch.setenv('APOLLOSAI_ENCRYPTION_KEY', 'a' * 32)
    from apollosai.storage.encrypt_utils import reset_key_cache

    reset_key_cache()
    from apollosai.storage.models.auth_token import AuthToken
    from apollosai.storage.services.token_cache_service import save_token_cache

    user_id = uuid.uuid4()
    plaintext = '{"AccessToken": {"key": "secret"}}'
    await save_token_cache(async_session, user_id, plaintext)
    token = await async_session.get(AuthToken, user_id)
    assert token.token_cache != plaintext  # Must be encrypted
