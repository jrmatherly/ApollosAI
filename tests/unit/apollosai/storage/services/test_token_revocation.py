"""Tests for JWT token revocation service."""

import datetime

import pytest

from apollosai.server.auth.jwt_utils import create_session_token, decode_session_token


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch):
    monkeypatch.setenv('JWT_SECRET', 'test-jwt-secret-must-be-long-enough-32!')


@pytest.mark.asyncio
async def test_revoke_token_inserts_record(async_session):
    """revoke_token should insert a RevokedToken row with the given jti."""
    from apollosai.storage.models.revoked_token import RevokedToken
    from apollosai.storage.services.token_revocation_service import revoke_token

    token = create_session_token(user_id='u1', email='e@e.com', entra_oid='o1')
    payload = decode_session_token(token)
    jti = payload['jti']
    expires_at = datetime.datetime.fromtimestamp(
        payload['exp'], tz=datetime.timezone.utc
    )

    await revoke_token(async_session, jti, expires_at)

    row = await async_session.get(RevokedToken, jti)
    assert row is not None
    assert row.jti == jti
    # SQLite strips timezone — compare naive datetimes
    assert row.expires_at.replace(tzinfo=None) == expires_at.replace(tzinfo=None)


@pytest.mark.asyncio
async def test_is_token_revoked_returns_true_for_revoked(async_session):
    """is_token_revoked should return True for a revoked jti."""
    from apollosai.storage.services.token_revocation_service import (
        is_token_revoked,
        revoke_token,
    )

    token = create_session_token(user_id='u1', email='e@e.com', entra_oid='o1')
    payload = decode_session_token(token)
    jti = payload['jti']
    expires_at = datetime.datetime.fromtimestamp(
        payload['exp'], tz=datetime.timezone.utc
    )

    await revoke_token(async_session, jti, expires_at)
    assert await is_token_revoked(async_session, jti) is True


@pytest.mark.asyncio
async def test_is_token_revoked_returns_false_for_active(async_session):
    """is_token_revoked should return False for a non-revoked jti."""
    from apollosai.storage.services.token_revocation_service import is_token_revoked

    assert await is_token_revoked(async_session, 'nonexistent-jti') is False


@pytest.mark.asyncio
async def test_revoke_duplicate_jti_is_idempotent(async_session):
    """Revoking the same jti twice should not raise."""
    from apollosai.storage.services.token_revocation_service import revoke_token

    token = create_session_token(user_id='u1', email='e@e.com', entra_oid='o1')
    payload = decode_session_token(token)
    jti = payload['jti']
    expires_at = datetime.datetime.fromtimestamp(
        payload['exp'], tz=datetime.timezone.utc
    )

    await revoke_token(async_session, jti, expires_at)
    # Second call should not raise
    await revoke_token(async_session, jti, expires_at)
