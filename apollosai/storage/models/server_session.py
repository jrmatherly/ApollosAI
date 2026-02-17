"""Server-side session storage — replaces Starlette cookie sessions."""

import datetime

from sqlalchemy import JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from apollosai.storage.models.base import Base


class ServerSession(Base):
    __tablename__ = 'server_session'

    session_id: Mapped[str] = mapped_column(Text, primary_key=True)
    data: Mapped[dict | None] = mapped_column(JSON, default=None)
    # Review fix [L3]: Index on expires_at for efficient cleanup queries
    expires_at: Mapped[datetime.datetime] = mapped_column(index=True)
