import uuid

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from apollosai.storage.models.base import Base, TimestampMixin


class Organization(TimestampMixin, Base):
    __tablename__ = 'organization'

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(unique=True)

    # LLM defaults
    default_llm_model: Mapped[str | None] = mapped_column(default=None)
    default_llm_base_url: Mapped[str | None] = mapped_column(default=None)
    default_max_iterations: Mapped[int | None] = mapped_column(default=None)
    _default_llm_api_key: Mapped[str | None] = mapped_column(String, default=None)

    # Agent/sandbox config
    agent: Mapped[str | None] = mapped_column(default=None)
    sandbox_base_container_image: Mapped[str | None] = mapped_column(default=None)
    sandbox_runtime_container_image: Mapped[str | None] = mapped_column(default=None)
    mcp_config: Mapped[dict | None] = mapped_column(JSON, default=None)

    # Feature flags
    enable_default_condenser: Mapped[bool] = mapped_column(default=True)
    v1_enabled: Mapped[bool | None] = mapped_column(default=None)
