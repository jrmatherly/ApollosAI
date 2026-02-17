"""Shared fixtures for ApollosAI unit tests."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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
