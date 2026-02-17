import uuid

from sqlalchemy import JSON, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from apollosai.storage.models.base import Base, TimestampMixin


class IntegrationConversation(TimestampMixin, Base):
    __tablename__ = 'integration_conversation'
    __table_args__ = (
        UniqueConstraint(
            'integration_type',
            'external_id',
            'org_id',
            name='uq_integration_conversation_type_ext_org',
        ),
        Index('ix_integration_conversation_conv', 'conversation_id'),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('organization.id'))
    integration_type: Mapped[str] = mapped_column()
    external_id: Mapped[str] = mapped_column(Text)
    conversation_id: Mapped[str] = mapped_column(Text)
    external_url: Mapped[str | None] = mapped_column(Text, default=None)
    extra_metadata: Mapped[dict | None] = mapped_column(JSON, default=None)
