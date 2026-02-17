"""Persisted MSAL token cache per user.

Stores the serialized MSAL SerializableTokenCache blob (encrypted at rest)
so that access/refresh tokens survive server restarts and allow background
token refresh without user interaction.
"""

import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from apollosai.storage.models.base import Base, TimestampMixin


class AuthToken(TimestampMixin, Base):
    __tablename__ = 'auth_token'

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('user.id'), unique=True)
    # Encrypted MSAL SerializableTokenCache JSON blob
    token_cache: Mapped[str] = mapped_column(Text)
