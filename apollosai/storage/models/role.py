from sqlalchemy import Identity
from sqlalchemy.orm import Mapped, mapped_column

from apollosai.storage.models.base import Base, TimestampMixin


class Role(TimestampMixin, Base):
    __tablename__ = 'role'

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    rank: Mapped[int] = mapped_column()
