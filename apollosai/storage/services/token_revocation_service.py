"""Token revocation service for JWT invalidation.

Provides functions to revoke tokens by jti and check revocation status.
Uses the revoked_token table for O(1) lookup by jti primary key.
"""

import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from apollosai.storage.models.revoked_token import RevokedToken


async def revoke_token(
    session: AsyncSession,
    jti: str,
    expires_at: datetime.datetime,
) -> None:
    """Insert a revocation record. Idempotent — duplicate jti is ignored."""
    existing = await session.get(RevokedToken, jti)
    if existing is not None:
        return
    record = RevokedToken(
        jti=jti,
        revoked_at=datetime.datetime.now(tz=datetime.timezone.utc),
        expires_at=expires_at,
    )
    session.add(record)
    await session.commit()


async def is_token_revoked(session: AsyncSession, jti: str) -> bool:
    """Check if a token jti has been revoked. O(1) PK lookup."""
    row = await session.get(RevokedToken, jti)
    return row is not None
