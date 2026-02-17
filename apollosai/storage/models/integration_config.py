import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from apollosai.storage.models.base import Base, TimestampMixin


class IntegrationConfig(TimestampMixin, Base):
    __tablename__ = 'integration_config'
    __table_args__ = (
        UniqueConstraint(
            'org_id',
            'integration_type',
            name='uq_integration_config_org_type',
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('organization.id'))
    integration_type: Mapped[str] = mapped_column(String(50))
    enabled: Mapped[bool] = mapped_column(default=False)
    config_encrypted: Mapped[str | None] = mapped_column(Text, default=None)
    webhook_secret_encrypted: Mapped[str | None] = mapped_column(Text, default=None)
