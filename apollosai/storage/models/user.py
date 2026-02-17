import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from apollosai.storage.models.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = 'user'

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entra_oid: Mapped[str] = mapped_column(unique=True)
    email: Mapped[str | None] = mapped_column(default=None)
    display_name: Mapped[str | None] = mapped_column(default=None)
    current_org_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey('organization.id'), default=None
    )
    current_team_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey('team.id'), default=None
    )
