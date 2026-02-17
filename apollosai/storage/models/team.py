import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from apollosai.storage.models.base import Base, TimestampMixin


class Team(TimestampMixin, Base):
    __tablename__ = 'team'

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('organization.id'))
    name: Mapped[str] = mapped_column()

    # Team-level LLM overrides
    llm_model: Mapped[str | None] = mapped_column(default=None)
    llm_base_url: Mapped[str | None] = mapped_column(default=None)
    max_iterations: Mapped[int | None] = mapped_column(default=None)
    _llm_api_key: Mapped[str | None] = mapped_column(
        'llm_api_key', String, default=None
    )

    __table_args__ = (UniqueConstraint('org_id', 'name'),)
