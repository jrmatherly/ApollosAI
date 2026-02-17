"""Revoked JWT tracking for token invalidation."""

import datetime

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from apollosai.storage.models.base import Base


class RevokedToken(Base):
    __tablename__ = 'revoked_token'

    jti: Mapped[str] = mapped_column(Text, primary_key=True)
    revoked_at: Mapped[datetime.datetime] = mapped_column()
    expires_at: Mapped[datetime.datetime] = mapped_column()
