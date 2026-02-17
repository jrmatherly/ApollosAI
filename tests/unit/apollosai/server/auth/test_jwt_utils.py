import pytest

from apollosai.server.auth.jwt_utils import create_session_token, decode_session_token

import jwt as pyjwt


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
        user_id='abc-123', email='test@example.com', entra_oid='oid-456',
    )
    # Change secret — decode must reject
    monkeypatch.setenv('JWT_SECRET', 'different-secret-should-fail-validation!')
    with pytest.raises(pyjwt.InvalidSignatureError):
        decode_session_token(token)


def test_decode_validates_audience():
    """Tokens without correct audience must be rejected."""
    import jwt
    secret = 'test-jwt-secret-must-be-long-enough-32!'
    bad_token = jwt.encode({'sub': 'x', 'aud': 'other-service'}, secret, algorithm='HS256')
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
        user_id='abc-123', email='test@example.com', entra_oid='oid-456',
    )
    payload = decode_session_token(token)
    assert isinstance(payload['sub'], str)
    assert isinstance(payload['email'], str)
    assert isinstance(payload['entra_oid'], str)
