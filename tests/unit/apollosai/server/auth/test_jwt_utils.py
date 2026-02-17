import datetime

import jwt as pyjwt
import pytest

from apollosai.server.auth.jwt_utils import create_session_token, decode_session_token


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch):
    monkeypatch.setenv('JWT_SECRET', 'test-jwt-secret-must-be-long-enough-32!')


def test_create_and_decode_roundtrip():
    token = create_session_token(
        user_id='abc-123',
        email='test@example.com',
        entra_oid='oid-456',
    )
    payload = decode_session_token(token)
    assert payload['sub'] == 'abc-123'
    assert payload['email'] == 'test@example.com'
    assert payload['entra_oid'] == 'oid-456'
    assert payload['aud'] == 'apollosai'


def test_decode_expired_raises():
    import time

    import jwt

    # Build an already-expired token directly to avoid time-mocking complications.
    # PyJWT uses datetime.now(tz=timezone.utc) internally for validation, so the
    # most reliable approach is to encode a token whose exp is in the past.
    secret = 'test-jwt-secret-must-be-long-enough-32!'
    past = time.time() - 100
    expired_token = jwt.encode(
        {
            'sub': 'abc-123',
            'email': 'test@example.com',
            'entra_oid': 'oid-456',
            'aud': 'apollosai',
            'iat': past,
            'exp': past + 10,  # expired 90 seconds ago
        },
        secret,
        algorithm='HS256',
    )
    with pytest.raises(pyjwt.ExpiredSignatureError):
        decode_session_token(expired_token)


def test_decode_invalid_raises():
    with pytest.raises(pyjwt.InvalidTokenError):
        decode_session_token('not-a-valid-jwt')


def test_decode_wrong_secret(monkeypatch):
    # Create token with current secret
    token = create_session_token(
        user_id='abc-123',
        email='test@example.com',
        entra_oid='oid-456',
    )
    # Change secret — decode must reject
    monkeypatch.setenv('JWT_SECRET', 'different-secret-should-fail-validation!')
    with pytest.raises(pyjwt.InvalidSignatureError):
        decode_session_token(token)


def test_decode_validates_audience():
    """Tokens without correct audience must be rejected."""
    import jwt

    secret = 'test-jwt-secret-must-be-long-enough-32!'
    bad_token = jwt.encode(
        {'sub': 'x', 'aud': 'other-service'}, secret, algorithm='HS256'
    )
    with pytest.raises(pyjwt.InvalidAudienceError):
        decode_session_token(bad_token)


def test_jwt_secret_too_short_raises(monkeypatch):
    """JWT_SECRET must be at least 32 characters."""
    monkeypatch.setenv('JWT_SECRET', 'short')
    with pytest.raises(ValueError, match='at least 32 characters'):
        create_session_token(user_id='x', email='x@x.com', entra_oid='o')


def test_decode_returns_required_claims():
    """Decoded payload must contain sub, email, entra_oid."""
    token = create_session_token(
        user_id='abc-123',
        email='test@example.com',
        entra_oid='oid-456',
    )
    payload = decode_session_token(token)
    assert isinstance(payload['sub'], str)
    assert isinstance(payload['email'], str)
    assert isinstance(payload['entra_oid'], str)


def test_create_session_token_includes_jti():
    """Tokens must include a jti claim (UUID string)."""
    token = create_session_token(
        user_id='abc-123',
        email='test@example.com',
        entra_oid='oid-456',
    )
    payload = decode_session_token(token)
    assert 'jti' in payload
    # Validate it looks like a UUID
    import uuid

    uuid.UUID(payload['jti'])  # Raises ValueError if not a valid UUID


def test_jti_is_unique_per_token():
    """Each token must have a unique jti."""
    t1 = create_session_token(user_id='u', email='e@e.com', entra_oid='o')
    t2 = create_session_token(user_id='u', email='e@e.com', entra_oid='o')
    p1 = decode_session_token(t1)
    p2 = decode_session_token(t2)
    assert p1['jti'] != p2['jti']


@pytest.mark.asyncio
async def test_validate_session_token_accepts_valid(async_session):
    """validate_session_token should accept a valid, non-revoked token."""
    from apollosai.server.auth.jwt_utils import validate_session_token

    token = create_session_token(
        user_id='abc-123',
        email='test@example.com',
        entra_oid='oid-456',
    )
    payload = await validate_session_token(token, async_session)
    assert payload['sub'] == 'abc-123'
    assert 'jti' in payload


@pytest.mark.asyncio
async def test_revoked_token_rejected_at_validation(async_session):
    """A valid JWT with revoked jti must be rejected by validate_session_token."""
    from apollosai.server.auth.jwt_utils import validate_session_token
    from apollosai.storage.services.token_revocation_service import revoke_token

    token = create_session_token(user_id='u1', email='e@e.com', entra_oid='o1')
    payload = decode_session_token(token)
    expires_at = datetime.datetime.fromtimestamp(
        payload['exp'], tz=datetime.timezone.utc
    )
    await revoke_token(async_session, payload['jti'], expires_at)

    with pytest.raises(pyjwt.InvalidTokenError, match='revoked'):
        await validate_session_token(token, async_session)


@pytest.mark.asyncio
async def test_token_without_jti_still_works(async_session):
    """Backward compat: existing tokens without jti should NOT break."""
    # Manually create a token without jti (simulates pre-Phase 2 tokens)
    import time

    import jwt

    from apollosai.server.auth.jwt_utils import validate_session_token

    secret = 'test-jwt-secret-must-be-long-enough-32!'
    now = time.time()
    old_token = jwt.encode(
        {
            'sub': 'old-user',
            'email': 'old@example.com',
            'entra_oid': 'old-oid',
            'aud': 'apollosai',
            'iat': now,
            'exp': now + 3600,
        },
        secret,
        algorithm='HS256',
    )
    # Should succeed — no jti means skip revocation check
    payload = await validate_session_token(old_token, async_session)
    assert payload['sub'] == 'old-user'
