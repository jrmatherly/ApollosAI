"""API key CRUD and HMAC-SHA256 verification.

Keys use format sk-aai-<random>. Only the HMAC hash and salt are stored —
the raw key is returned exactly once on creation. Verification extracts
the prefix, looks up the row, recomputes the HMAC, and uses
hmac.compare_digest() for timing-safe comparison.

Review fixes incorporated:
- [C3]: hmac.compare_digest() for ALL hash comparisons
- [H7]: is_active check during verification (revoked keys return None)
"""

import hmac as hmac_mod
import secrets
import uuid as uuid_mod

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apollosai.storage.models.api_key import ApiKey

# Prefix format: sk-aai-{8 chars of token for display}
_PREFIX_LEN = 8


async def create_api_key(
    session: AsyncSession,
    user_id: uuid_mod.UUID,
    org_id: uuid_mod.UUID,
    name: str,
) -> tuple[str, ApiKey]:
    """Create a new API key. Returns (raw_key, ApiKey record).

    The raw key is returned once — it cannot be recovered after this call.
    """
    token = secrets.token_urlsafe(32)
    raw_key = f'sk-aai-{token}'
    prefix = f'sk-aai-{token[:_PREFIX_LEN]}'
    salt = secrets.token_hex(32)
    key_hash = hmac_mod.new(salt.encode(), raw_key.encode(), 'sha256').hexdigest()

    record = ApiKey(
        id=uuid_mod.uuid4(),
        user_id=user_id,
        org_id=org_id,
        name=name,
        prefix=prefix,
        key_hash=key_hash,
        salt=salt,
        is_active=True,
    )
    session.add(record)
    await session.commit()
    return raw_key, record


async def verify_api_key(
    session: AsyncSession, raw_key: str
) -> ApiKey | None:
    """Verify an API key by HMAC. Returns ApiKey record or None.

    Review fix [C3]: Uses hmac.compare_digest() for timing-safe comparison.
    Review fix [H7]: Checks is_active — revoked keys return None.
    """
    if not raw_key.startswith('sk-aai-'):
        return None

    # Extract prefix: sk-aai- + first 8 chars of the token part
    token_part = raw_key[len('sk-aai-'):]
    prefix = f'sk-aai-{token_part[:_PREFIX_LEN]}'

    stmt = select(ApiKey).where(ApiKey.prefix == prefix, ApiKey.is_active.is_(True))
    result = await session.execute(stmt)
    candidates = result.scalars().all()

    for candidate in candidates:
        computed = hmac_mod.new(
            candidate.salt.encode(), raw_key.encode(), 'sha256'
        ).hexdigest()
        if hmac_mod.compare_digest(computed, candidate.key_hash):
            return candidate

    return None


async def list_api_keys(
    session: AsyncSession,
    user_id: uuid_mod.UUID,
    org_id: uuid_mod.UUID,
) -> list[ApiKey]:
    """List active API keys for a user+org. Returns prefix + name only."""
    stmt = select(ApiKey).where(
        ApiKey.user_id == user_id,
        ApiKey.org_id == org_id,
        ApiKey.is_active.is_(True),
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def revoke_api_key(
    session: AsyncSession,
    key_id: uuid_mod.UUID,
    user_id: uuid_mod.UUID,
) -> None:
    """Revoke an API key by setting is_active=False.

    Only the key owner can revoke it.
    """
    record = await session.get(ApiKey, key_id)
    if record is None:
        raise ValueError(f'API key {key_id} not found')
    if record.user_id != user_id:
        raise PermissionError('Cannot revoke another user\'s API key')
    record.is_active = False
    await session.commit()
