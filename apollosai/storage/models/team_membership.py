import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from apollosai.storage.models.base import Base, TimestampMixin


class TeamMembership(TimestampMixin, Base):
    __tablename__ = 'team_membership'

    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('team.id'), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('user.id'), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey('role.id'))

    # Per-user LLM overrides
    _llm_api_key: Mapped[str | None] = mapped_column(String, default=None)
    llm_model: Mapped[str | None] = mapped_column(default=None)
    max_iterations: Mapped[int | None] = mapped_column(default=None)
