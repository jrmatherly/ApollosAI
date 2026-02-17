"""Async database connection for ApollosAI enterprise storage."""

import os

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def get_database_url() -> str:
    """Get database URL from environment, fixing scheme for asyncpg if needed."""
    url = os.environ.get('DATABASE_URL', '')
    if not url:
        raise ValueError('DATABASE_URL environment variable is required')
    # Heroku/Railway-style postgres:// -> SQLAlchemy asyncpg scheme
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql+asyncpg://', 1)
    elif url.startswith('postgresql://'):
        url = url.replace('postgresql://', 'postgresql+asyncpg://', 1)
    return url


def create_async_engine_from_url(
    url: str,
    pool_size: int = 5,
    max_overflow: int = 10,
    echo: bool = False,
) -> AsyncEngine:
    """Create an async SQLAlchemy engine."""
    return create_async_engine(
        url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        echo=echo,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to the given engine."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
