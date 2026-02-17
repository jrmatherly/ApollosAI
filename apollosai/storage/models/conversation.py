"""Conversation metadata storage scoped to user + org."""

import datetime
import uuid

from sqlalchemy import JSON, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from apollosai.storage.models.base import Base, TimestampMixin


class Conversation(TimestampMixin, Base):
    __tablename__ = 'conversation'

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('user.id'))
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('organization.id'))
    title: Mapped[str | None] = mapped_column(Text, default=None)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(default=None)
