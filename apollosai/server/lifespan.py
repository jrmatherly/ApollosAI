"""ApollosAI lifespan service — manages startup/shutdown for the enterprise server.

Review fixes incorporated:
- [H1]: Override __aenter__/__aexit__ to init engine on startup, dispose on shutdown
- [C1]: Module-level singleton for V0 store bridge (get_session_maker())
"""

import os

from sqlalchemy.ext.asyncio import async_sessionmaker

from openhands.app_server.app_lifespan.oss_app_lifespan_service import (
    OssAppLifespanService,
)

# Module-level singleton for V0 store bridge [C1]
# Populated by __aenter__, cleared by __aexit__
_session_maker: async_sessionmaker | None = None


def get_session_maker() -> async_sessionmaker | None:
    """Get the module-level session maker for V0 store bridge.

    Review fix [C1]: V0 stores instantiated via get_instance(config, user_id)
    have no path to receive a session_maker through the ABC interface.
    This module-level singleton is populated during lifespan startup
    and provides the bridge until stores are migrated to V1 DI.
    """
    return _session_maker


class ApollosAILifespanService(OssAppLifespanService):
    """Enterprise lifespan service.

    Extends OssAppLifespanService to:
    1. Skip OpenHands' SQLite Alembic migrations
    2. Initialize async PostgreSQL engine via ApollosAIDbSessionInjector
    3. Dispose engine on shutdown
    4. Expose session_maker via module-level singleton for V0 stores
    """

    run_alembic_on_startup: bool = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._db_injector = None

    @property
    def db_injector(self):
        """Lazy-init the DB session injector."""
        if self._db_injector is None:
            from apollosai.server.db_session import ApollosAIDbSessionInjector

            db_url = os.environ.get('DATABASE_URL', '')
            if db_url:
                self._db_injector = ApollosAIDbSessionInjector(database_url=db_url)
            else:
                self._db_injector = ApollosAIDbSessionInjector()
        return self._db_injector

    async def __aenter__(self):
        """Review fix [H1]: Eagerly init engine + expose session_maker."""
        global _session_maker
        await super().__aenter__()
        await self.db_injector.get_async_db_engine()
        _session_maker = await self.db_injector.get_async_session_maker()

        from apollosai.monitoring.otel import init_otel

        init_otel()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Review fix [H1]: Dispose engine to prevent connection leaks."""
        global _session_maker

        from apollosai.monitoring.otel import shutdown_otel

        shutdown_otel()
        _session_maker = None
        await self.db_injector.dispose()
        await super().__aexit__(exc_type, exc_value, traceback)
