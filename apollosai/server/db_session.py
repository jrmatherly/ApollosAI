"""ApollosAI DbSessionInjector — async PostgreSQL session management.

Simplified version of openhands/app_server/services/db_session_injector.py
that uses DATABASE_URL directly instead of DB_HOST/DB_PORT/DB_NAME.
"""

import logging
from collections.abc import AsyncGenerator

from fastapi import Request
from pydantic import BaseModel, PrivateAttr
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from apollosai.storage.database import get_database_url
from openhands.app_server.services.injector import Injector, InjectorState

_logger = logging.getLogger(__name__)
APOLLOSAI_DB_SESSION_ATTR = 'apollosai_db_session'


class ApollosAIDbSessionInjector(BaseModel, Injector[AsyncSession]):
    """Injects async SQLAlchemy sessions backed by ApollosAI's PostgreSQL.

    Review fix [C8]: Generic param is AsyncSession (what inject() yields),
    NOT async_sessionmaker (upstream has same bug — don't propagate it).
    """

    database_url: str = ''
    pool_size: int = 5
    max_overflow: int = 10
    echo: bool = False

    _async_engine: AsyncEngine | None = PrivateAttr(default=None)
    _async_session_maker: async_sessionmaker | None = PrivateAttr(default=None)

    def model_post_init(self, __context) -> None:
        if not self.database_url:
            self.database_url = get_database_url()

    async def get_async_db_engine(self) -> AsyncEngine:
        if self._async_engine is None:
            if self.database_url.startswith('sqlite'):
                self._async_engine = create_async_engine(
                    self.database_url, poolclass=NullPool
                )
            else:
                self._async_engine = create_async_engine(
                    self.database_url,
                    pool_size=self.pool_size,
                    max_overflow=self.max_overflow,
                    pool_pre_ping=True,
                )
        return self._async_engine

    async def get_async_session_maker(self) -> async_sessionmaker:
        if self._async_session_maker is None:
            engine = await self.get_async_db_engine()
            self._async_session_maker = async_sessionmaker(
                engine, class_=AsyncSession, expire_on_commit=False
            )
        return self._async_session_maker

    async def dispose(self) -> None:
        """Dispose the engine — call on shutdown."""
        if self._async_engine is not None:
            await self._async_engine.dispose()
            self._async_engine = None
            self._async_session_maker = None

    async def inject(
        self, state: InjectorState, request: Request | None = None
    ) -> AsyncGenerator[AsyncSession, None]:
        """Inject an async session, caching on state for reuse within a request."""
        db_session = getattr(state, APOLLOSAI_DB_SESSION_ATTR, None)
        if db_session:
            yield db_session
        else:
            session_maker = await self.get_async_session_maker()
            db_session = session_maker()
            try:
                setattr(state, APOLLOSAI_DB_SESSION_ATTR, db_session)
                yield db_session
                await db_session.commit()
            except Exception:
                _logger.exception('Rolling back SQL due to error')
                await db_session.rollback()
                raise
            finally:
                if hasattr(state, APOLLOSAI_DB_SESSION_ATTR):
                    delattr(state, APOLLOSAI_DB_SESSION_ATTR)
                await db_session.close()
