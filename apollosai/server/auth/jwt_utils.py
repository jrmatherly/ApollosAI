"""JWT session token creation and validation.

Session tokens are signed with HS256 using JWT_SECRET and stored in HttpOnly
cookies. They encode the user's identity (user_id, email, entra_oid) and are
independent from MSAL tokens — the JWT cookie is our session, MSAL tokens
are stored server-side in the auth_token table.

Security properties:
- HS256 with minimum 32-character secret (enforced at creation time)
- Audience claim ('apollosai') prevents cross-service token replay
- Required claims (sub, email, entra_oid) validated after decode
- jti claim enables per-token revocation via revoked_token table
"""

import time
import uuid

import jwt
from sqlalchemy.ext.asyncio import AsyncSession

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
        'jti': str(uuid.uuid4()),
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
        token,
        secret,
        algorithms=['HS256'],
        audience=JWT_AUDIENCE,
    )
    # Validate required claims exist and are strings
    for claim in ('sub', 'email', 'entra_oid'):
        if claim not in payload or not isinstance(payload[claim], str):
            raise jwt.InvalidTokenError(f'Missing or invalid required claim: {claim}')
    return payload


async def validate_session_token(token: str, session: AsyncSession) -> dict:
    """Decode a JWT and check revocation status.

    Composes decode_session_token() with a revocation table lookup.
    Tokens without a jti claim (pre-Phase 2) skip the revocation check
    for backward compatibility.

    Raises jwt.InvalidTokenError if the token's jti has been revoked.
    """
    payload = decode_session_token(token)
    jti = payload.get('jti')
    if jti is not None:
        from apollosai.storage.services.token_revocation_service import (
            is_token_revoked,
        )

        if await is_token_revoked(session, jti):
            raise jwt.InvalidTokenError(f'Token has been revoked (jti={jti})')
    return payload
