import enum
import uuid

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from apollosai.storage.models.base import Base, TimestampMixin


class MCPServerType(str, enum.Enum):
    STDIO = 'stdio'
    SSE = 'sse'
    SHTTP = 'shttp'


class UserMCPServer(TimestampMixin, Base):
    __tablename__ = 'user_mcp_server'
    __table_args__ = (
        Index('ix_user_mcp_server_user_org', 'user_id', 'org_id', 'enabled'),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('user.id'))
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('organization.id'))
    name: Mapped[str] = mapped_column()
    server_type: Mapped[str] = mapped_column(String(20))
    config_encrypted: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(default=True)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    approved: Mapped[bool] = mapped_column(default=False)
