"""MSAL token cache persistence — encrypted at rest.

Stores the serialized MSAL SerializableTokenCache JSON blob in the
auth_token table, encrypted with AES-256-GCM using the user_id as AAD.
"""

import uuid as uuid_mod

from sqlalchemy.ext.asyncio import AsyncSession

from apollosai.storage.encrypt_utils import decrypt_value, encrypt_value
from apollosai.storage.models.auth_token import AuthToken


async def save_token_cache(
    session: AsyncSession, user_id: uuid_mod.UUID, cache_json: str
) -> None:
    """Encrypt and persist MSAL token cache for a user."""
    encrypted = encrypt_value(cache_json, aad=str(user_id))

    existing = await session.get(AuthToken, user_id)
    if existing is not None:
        existing.token_cache = encrypted
    else:
        token = AuthToken(
            id=user_id,
            user_id=user_id,
            token_cache=encrypted,
        )
        session.add(token)
    await session.commit()


async def load_token_cache(
    session: AsyncSession, user_id: uuid_mod.UUID
) -> str | None:
    """Load and decrypt MSAL token cache for a user. Returns None if not found."""
    token = await session.get(AuthToken, user_id)
    if token is None:
        return None
    return decrypt_value(token.token_cache, aad=str(user_id))
