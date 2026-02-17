import enum
import uuid

from sqlalchemy import JSON, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from apollosai.storage.models.base import Base, TimestampMixin


class AuditAction(str, enum.Enum):
    MEMBER_INVITED = 'member_invited'
    MEMBER_REMOVED = 'member_removed'
    ROLE_CHANGED = 'role_changed'
    INTEGRATION_CONFIGURED = 'integration_configured'
    MCP_SERVER_ADDED = 'mcp_server_added'
    MCP_SERVER_REMOVED = 'mcp_server_removed'
    SETTINGS_UPDATED = 'settings_updated'
    API_KEY_CREATED = 'api_key_created'
    API_KEY_REVOKED = 'api_key_revoked'
    ORG_CREATED = 'org_created'
    ORG_UPDATED = 'org_updated'
    TEAM_CREATED = 'team_created'
    TEAM_UPDATED = 'team_updated'


class AuditLog(TimestampMixin, Base):
    __tablename__ = 'audit_log'
    __table_args__ = (
        Index(
            'ix_audit_log_org_created',
            'org_id',
            'created_at',
            postgresql_ops={'created_at': 'DESC'},
        ),
        Index('ix_audit_log_actor', 'actor_id'),
        Index('ix_audit_log_action', 'action'),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey('user.id'), default=None
    )
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('organization.id'))
    action: Mapped[str] = mapped_column(String(50))
    resource_type: Mapped[str] = mapped_column()
    resource_id: Mapped[str] = mapped_column()
    details: Mapped[dict | None] = mapped_column(JSON, default=None)
    ip_address: Mapped[str | None] = mapped_column(Text, default=None)
