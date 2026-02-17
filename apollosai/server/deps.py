"""FastAPI dependency functions for ApollosAI server.

Review fix [C2]: RBAC and routes need DB sessions via Depends().
This module provides get_db_session() for use in route dependencies.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from apollosai.server.lifespan import get_session_maker


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session for use in route handlers and RBAC deps.

    Uses the module-level session maker from lifespan (populated on startup).
    """
    session_maker = get_session_maker()
    if session_maker is None:
        raise RuntimeError(
            'Database not initialized. Ensure ApollosAILifespanService has started.'
        )
    session = session_maker()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
