import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from apollosai.storage.models.base import Base, TimestampMixin


class OrgMembership(TimestampMixin, Base):
    __tablename__ = 'org_membership'

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('organization.id'), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('user.id'), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey('role.id'))
    status: Mapped[str] = mapped_column(String, default='active')
