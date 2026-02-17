"""JWT session token creation and validation.

Session tokens are signed with HS256 using JWT_SECRET and stored in HttpOnly
cookies. They encode the user's identity (user_id, email, entra_oid) and are
independent from MSAL tokens — the JWT cookie is our session, MSAL tokens
are stored server-side in the auth_token table.

Security properties:
- HS256 with minimum 32-character secret (enforced at creation time)
- Audience claim ('apollosai') prevents cross-service token replay
- Required claims (sub, email, entra_oid) validated after decode
"""

import time

import jwt

from apollosai.server.auth.constants import get_jwt_secret

# 24 hours default session
DEFAULT_EXPIRY_SECONDS = 86400
JWT_AUDIENCE = 'apollosai'
MIN_SECRET_LENGTH = 32


def _get_validated_secret() -> str:
    """Get JWT secret with minimum length enforcement."""
    secret = get_jwt_secret()
    if not secret:
        raise ValueError('JWT_SECRET environment variable is required')
    if len(secret) < MIN_SECRET_LENGTH:
        raise ValueError(
            f'JWT_SECRET must be at least {MIN_SECRET_LENGTH} characters '
            f'(got {len(secret)}). Use a cryptographically random string.'
        )
    return secret


def create_session_token(
    user_id: str,
    email: str,
    entra_oid: str,
    expires_in_seconds: int = DEFAULT_EXPIRY_SECONDS,
) -> str:
    """Create a signed JWT session token."""
    secret = _get_validated_secret()
    now = time.time()
    payload = {
        'sub': user_id,
        'email': email,
        'entra_oid': entra_oid,
        'aud': JWT_AUDIENCE,
        'iat': now,
        'exp': now + expires_in_seconds,
    }
    return jwt.encode(payload, secret, algorithm='HS256')


def decode_session_token(token: str) -> dict:
    """Decode and validate a JWT session token.

    Validates: signature, expiry, audience, and required claims.
    Raises jwt.ExpiredSignatureError if expired.
    Raises jwt.InvalidTokenError if invalid.
    Raises jwt.InvalidAudienceError if audience doesn't match.
    Raises jwt.InvalidTokenError if required claims are missing.
    """
    secret = _get_validated_secret()
    payload = jwt.decode(
        token, secret, algorithms=['HS256'], audience=JWT_AUDIENCE,
    )
    # Validate required claims exist and are strings
    for claim in ('sub', 'email', 'entra_oid'):
        if claim not in payload or not isinstance(payload[claim], str):
            raise jwt.InvalidTokenError(f'Missing or invalid required claim: {claim}')
    return payload
