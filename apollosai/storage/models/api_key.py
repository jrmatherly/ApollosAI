"""API key model for programmatic access.

Keys use the format sk-aai-<random> with HMAC-SHA256 hashing for storage:
- Salt: generated via secrets.token_hex(32) per key
- Hash: HMAC-SHA256(key=salt, msg=raw_api_key)
- Only the prefix (first 8 chars after sk-aai-) is stored in plaintext for
  identification in the UI (e.g., "sk-aai-a1b2c3d4...").
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from apollosai.storage.models.base import Base, TimestampMixin


class ApiKey(TimestampMixin, Base):
    __tablename__ = 'api_key'

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('user.id'))
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('organization.id'))
    name: Mapped[str] = mapped_column(String(255))
    prefix: Mapped[str] = mapped_column(String(20))
    key_hash: Mapped[str] = mapped_column(String(128))
    salt: Mapped[str] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
