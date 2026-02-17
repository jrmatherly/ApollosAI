"""Encrypted secret storage per user/org."""

import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from apollosai.storage.models.base import Base, TimestampMixin


class EncryptedSecret(TimestampMixin, Base):
    __tablename__ = 'encrypted_secret'

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('user.id'))
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('organization.id'))
    key: Mapped[str] = mapped_column(String(255))
    encrypted_value: Mapped[str] = mapped_column(Text)

    __table_args__ = (UniqueConstraint('user_id', 'org_id', 'key'),)
