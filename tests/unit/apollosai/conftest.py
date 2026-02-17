"""Shared fixtures for ApollosAI unit tests."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Import all models so Base.metadata.create_all creates all tables.
# Without this, tables for models imported only inside test functions
# may not exist when the engine fixture runs.
import apollosai.storage.models.api_key  # noqa: F401
import apollosai.storage.models.audit_log  # noqa: F401
import apollosai.storage.models.auth_token  # noqa: F401
import apollosai.storage.models.conversation  # noqa: F401
import apollosai.storage.models.encrypted_secret  # noqa: F401
import apollosai.storage.models.org_membership  # noqa: F401
import apollosai.storage.models.organization  # noqa: F401
import apollosai.storage.models.revoked_token  # noqa: F401
import apollosai.storage.models.role  # noqa: F401
import apollosai.storage.models.server_session  # noqa: F401
import apollosai.storage.models.team  # noqa: F401
import apollosai.storage.models.team_membership  # noqa: F401
import apollosai.storage.models.user  # noqa: F401
from apollosai.storage.models.base import Base


@pytest.fixture
async def async_engine():
    """Create an in-memory SQLite async engine for testing."""
    engine = create_async_engine('sqlite+aiosqlite://', echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def async_session_maker(async_engine):
    """Create an async session maker from the test engine."""
    return async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def async_session(async_session_maker):
    """Create an async session for testing.

    Review fix [H6-test]: Uses try/finally for proper cleanup ordering.
    Session is closed before engine dispose (via fixture dependency chain).
    """
    session = async_session_maker()
    try:
        yield session
    finally:
        await session.close()
